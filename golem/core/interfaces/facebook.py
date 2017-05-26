import json
import requests
from golem.core.message_parser import parse_text_message
from golem.core.serialize import json_serialize,json_deserialize
import datetime
from golem.core.responses import *
from golem.core.persistence import get_redis
from django.conf import settings  
from golem.tasks import accept_user_message

class FacebookInterface():
    name = 'facebook'
    TEXT_LENGTH_LIMIT = 320

    # Post function to handle Facebook messages
    @staticmethod
    def accept_request(request):
        # Facebook recommends going through every entry since they might send
        # multiple messages in a single call during high load.
        for entry in request['entry']:
            for raw_message in entry['messaging']:
                ts_datetime = datetime.datetime.fromtimestamp(int(raw_message['timestamp']) / 1000)
                crr_datetime = datetime.datetime.utcnow()
                diff = crr_datetime - ts_datetime
                if diff.total_seconds() < settings.GOLEM_CONFIG.get('MSG_LIMIT_SECONDS'):
                    # print("MSG FB layer GET FB:")
                    print('INCOMING RAW FB MESSAGE: {}'.format(raw_message))
                    uid = FacebookInterface.fbid_to_uid(raw_message['sender']['id'])
                    # Confirm accepted message
                    FacebookInterface.post_message(uid, SenderActionMessage('mark_seen'))
                    # Add it to the message queue
                    accept_user_message.delay('facebook', uid, raw_message)
                elif raw_message.get('timestamp'):
                    print("Delay {} too big, ignoring message!".format(diff))
                    print(raw_message)

    @staticmethod
    def uid_to_fbid(uid):
        return uid.split('_',maxsplit=1)[1] # uid has format fb_{number}

    @staticmethod
    def load_profile(uid, cache=True):
        fbid = FacebookInterface.uid_to_fbid(uid)

        db = get_redis()
        key = 'fb_profile_'+fbid

        if not cache or not db.exists(key):
            print('Loading fb profile...')

            url = "https://graph.facebook.com/v2.6/"+fbid
            params = {
                'fields': 'first_name,last_name,profile_pic,locale,timezone,gender',
                'access_token': settings.GOLEM_CONFIG.get('FB_PAGE_TOKEN')
            }
            res = requests.get(url, params=params)
            if not res.status_code == requests.codes.ok:
                print("!!!!!!!!!!!!!!!!!!!!!!! ERROR load_profile "+res.status_code)
                return None

            db.set(key, json.dumps(res.json()), ex=3600*24*14) # save value, expire in 14 days

        return json.loads(db.get(key).decode('utf-8'))

    @staticmethod
    def fbid_to_uid(fbid):
         return 'fb_'+fbid

    @staticmethod
    def post_message(uid, response):

        # print(payload, type_)
        if isinstance(response, SenderActionMessage):
            request_mode = "messages"
            fbid = FacebookInterface.uid_to_fbid(uid)
            response_dict = {'sender_action':response.action, 'recipient':{"id": fbid}}
        elif isinstance(response, MessageElement):
            message = FacebookInterface.to_message(response)
            fbid = FacebookInterface.uid_to_fbid(uid)
            response_dict = {"recipient": {"id": fbid}, "message": message}
            request_mode = "messages"
        elif isinstance(response, ThreadSetting):
            request_mode = "thread_settings"
            response_dict = FacebookInterface.to_setting(response)
            print('SENDING SETTING:', response_dict)
        else:
            raise ValueError('Error: Invalid message type: {}: {}'.format(type(response), response))

        prefix_post_message_url = 'https://graph.facebook.com/v2.6/me/'
        token = settings.GOLEM_CONFIG.get('FB_PAGE_TOKEN')
        post_message_url = prefix_post_message_url+request_mode+'?access_token='+token
        # print("POST", post_message_url)
        r = requests.post(post_message_url,
                               headers={"Content-Type": "application/json"},
                               data=json.dumps(response_dict, default=json_serialize))
        if r.status_code != 200:
            print('ERROR: MESSAGE REFUSED: ', response_dict)
            print('ERROR: ', r.text)
            raise Exception(r.json()['error']['message'])

    @staticmethod
    def to_setting(response):
        if isinstance(response, GreetingSetting):
            return {
                "greeting": {'text' : response.message},
                "setting_type": "greeting"
            }
        elif isinstance(response, GetStartedSetting):
            return {
                "call_to_actions": [{'payload' : json.dumps(response.payload, default=json_serialize)}],
                "setting_type": "call_to_actions",
                "thread_state": "new_thread"
            }
        elif isinstance(response, MenuSetting):
            return {
                "call_to_actions": [FacebookInterface.to_setting(element) for element in response.elements[:10]],
                "setting_type": "call_to_actions",
                "thread_state": "existing_thread"
            }
        elif isinstance(response, MenuElement):
            r = {
                "title": response.title,
                "type": response.type,
            }
            if response.payload:
                r['payload'] = json.dumps(response.payload, default=json_serialize)
            if response.url:
                r['url'] = response.url
            return r
        raise ValueError('Error: Invalid setting type: {}: {}'.format(type(response), response))

    @staticmethod
    def to_message(response):
        if isinstance(response, TextMessage):
            if response.buttons:
                return {
                    "attachment":{
                       "type":"template",
                       "payload":{
                         "template_type":"button",
                         "text": response.text[:FacebookInterface.TEXT_LENGTH_LIMIT],
                         "buttons": [FacebookInterface.to_message(button) for button in response.buttons]
                       }
                    }
                  }
            message = {'text' : response.text[:FacebookInterface.TEXT_LENGTH_LIMIT]}
            if response.quick_replies:
                message["quick_replies"] = [FacebookInterface.to_message(reply) for reply in response.quick_replies]
            return message

        elif isinstance(response, GenericTemplateMessage):
            return {
                "attachment":{
                   "type":"template",
                   "payload":{
                     "template_type":"generic",
                     "elements": [FacebookInterface.to_message(element) for element in response.elements[:10]]
                   }
                }
            }

        elif isinstance(response, AttachmentMessage):
            return {
                "attachment":{
                    "type": response.attachment_type,
                    "payload":{
                      "url":response.url
                    }
                }
            }

        elif isinstance(response, GenericTemplateElement):
            message = {
                "title": response.title,
                "image_url": response.image_url,
                "subtitle": response.subtitle,
                "item_url": response.item_url
            }
            if response.buttons:
                message["buttons"] = [FacebookInterface.to_message(button) for button in response.buttons]
            return message

        elif isinstance(response, QuickReply):
            message = {
                "content_type": response.content_type
            }
            if response.content_type=='text':
                message['title'] = response.title[:20]
                message['payload'] = json.dumps(response.payload if response.payload else {}, default=json_serialize)
            return message

        elif isinstance(response, Button):
            message = {"title": response.title}
            if response.payload:
                message['type'] = 'postback'
                if not response.payload: response.payload = {}
                response.payload['_log_text'] = response.title
                message['payload'] = json.dumps(response.payload, default=json_serialize)
            if response.url:
                message['type'] = 'web_url'
                message['url'] = response.url
            if response.phone_number:
                message['type'] = 'phone_number'
                message['payload'] = response.url
                message['webview_height_ratio'] = response.webview_height_ratio
            return message

        raise ValueError('Error: Invalid message type: {}: {}'.format(type(response), response))

    @staticmethod
    def send_settings(settings):
        for setting in settings:
            FacebookInterface.post_message(None, setting)

    @staticmethod
    def processing_start(uid):
        # Show typing animation
        FacebookInterface.post_message(uid, SenderActionMessage('typing_on'))

    @staticmethod
    def processing_end(uid):
        pass

    @staticmethod
    def state_change(state):
        pass

    @staticmethod
    def parse_message(raw_message, num_tries=1):
        if 'postback' in raw_message:
            payload = json.loads(raw_message['postback']['payload'], object_hook=json_deserialize)
            payload['_message_text'] = [{'value':None}]
            return {'entities': payload, 'type':'postback'}
        elif 'message' in raw_message:
            if 'sticker_id' in raw_message['message']:
                return FacebookInterface.parse_sticker(raw_message['message']['sticker_id'])
            if 'attachments' in raw_message['message']:
                attachments = raw_message['message']['attachments']
                return FacebookInterface.parse_attachments(attachments)
            if 'quick_reply' in raw_message['message']:
                payload = json.loads(raw_message['message']['quick_reply'].get('payload'), object_hook=json_deserialize)
                if payload:
                    payload['_message_text'] = [{'value':raw_message['message']['text']}]
                    return {'entities': payload, 'type':'postback'}
            if 'text' in raw_message['message']:
                return parse_text_message(raw_message['message']['text'])
        return {'type':'undefined'}

    @staticmethod
    def parse_sticker(sticker_id):
        if sticker_id in [369239383222810,369239343222814,369239263222822]:
            return {'entities':{'emoji':'thumbs_up_sign', '_message_text':None}, 'type':'message'}

        return {'entities':{'sticker_id':sticker_id, '_message_text':None}, 'type':'message'}

    @staticmethod
    def parse_attachments(attachments):
        entities = {
            'intent':[],
            'current_location' : [],
            'attachment' : [],
            '_message_text' : [{'value':None}]
        }
        for attachment in attachments:
            if 'coordinates' in attachment['payload']:
                coordinates = attachment['payload']['coordinates']
                entities['current_location'].append({'value':attachment['title'], 'name':attachment['title'], 'coordinates':coordinates})
            if 'url' in attachment['payload']:
                url = attachment['payload']['url']
                # TODO: add attachment type by extension
                entities['attachment'].append({'value':url})
                entities['intent'].append({'value':'attachment'})
        return {'entities' : entities, 'type':'message'}
