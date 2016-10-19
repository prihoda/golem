import sys
import traceback
import json
import requests
from golem.message_queue import MessageQueue
from golem.message_parser import parse_text_message
from golem.serialize import json_serialize,json_deserialize
import datetime
from .responses import TextMessage,SenderActionMessage,MessageElement,ThreadSetting


class FacebookInterface():

    message_queue = None

    @staticmethod
    def init_queue(config):
        FacebookInterface.message_queue = MessageQueue(config=config)
        FacebookInterface.config = config

    # Post function to handle Facebook messages
    @staticmethod
    def accept_request(request):
        # Facebook recommends going through every entry since they might send
        # multiple messages in a single call during high load.
        for entry in request['entry']:
            for raw_message in entry['messaging']:
                ts_datetime = datetime.datetime.fromtimestamp(int(raw_message['timestamp']) / 1000)
                crr_datetime = datetime.datetime.now()
                diff = crr_datetime - ts_datetime
                if diff.total_seconds() < 30:
                    # print("MSG FB layer GET FB:")
                    print('INCOMING RAW FB MESSAGE:', raw_message)
                    uid = FacebookInterface.fbid_to_uid(raw_message['sender']['id'])
                    # Confirm accepted message
                    FacebookInterface.post_message(uid, SenderActionMessage('mark_seen'))
                    # Add it to the message queue
                    FacebookInterface.add_to_queue((uid, raw_message, FacebookInterface))
                elif raw_message.get('timestamp'):
                    print("Delay too big, ignoring message!")
                    print(raw_message)

    @staticmethod
    def add_to_queue(work):
        FacebookInterface.message_queue.queue.put(work)

    @staticmethod
    def uid_to_fbid(uid):
        return uid.split('_',maxsplit=1)[1] # uid has format fb_{number}

    @staticmethod
    def fbid_to_uid(fbid):
         return 'fb_'+fbid

    @staticmethod
    def post_message(uid, response):
        if isinstance(response, list):
            for resp in response:
                FacebookInterface.post_message(uid, resp)
            return

        try:
            if isinstance(response, str):
                response = TextMessage(text=response)

            # print(payload, type_)
            if isinstance(response, MessageElement):
                fbid = FacebookInterface.uid_to_fbid(uid)
                response_dict = response.to_message(fbid)
                graph_request_mode = "messages"
            elif isinstance(response, ThreadSetting):
                response_dict = response.to_response()
                print('SENDING SETTING:', response_dict)
                graph_request_mode = "thread_settings"
            else:
                raise ValueError('Error: Invalid message type: {}: {}'.format(type(response), response))

            prefix_post_message_url = 'https://graph.facebook.com/v2.6/me/'
            token = FacebookInterface.config['FB_PAGE_TOKEN']
            post_message_url = prefix_post_message_url+graph_request_mode+'?access_token='+token
            # print("POST", post_message_url)
            r = requests.post(post_message_url,
                                   headers={"Content-Type": "application/json"},
                                   data=json.dumps(response_dict, default=json_serialize))
            if r.status_code != 200:
                print('ERROR: MESSAGE REFUSED: ', response_dict)
                print('ERROR: ', r.text)
        except Exception as err:
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! EXCEPTION FB POST MESSAGE", err)
            traceback.print_exc(file=sys.stdout)

    @staticmethod
    def send_settings(settings):
        FacebookInterface.post_message(None, settings)

    @staticmethod
    def processing_start(uid):
        # Show typing animation
        FacebookInterface.post_message(uid, SenderActionMessage('typing_on'))

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
                return parse_text_message(FacebookInterface.config, raw_message['message']['text'])
        return {'type':'undefined'}

    @staticmethod
    def parse_sticker(sticker_id):
        if sticker_id in [369239383222810,369239343222814,369239263222822]:
            return {'entities':{'emoji':'thumbs_up_sign', '_message_text':None}, 'type':'message'}

        return {'entities':{'sticker_id':sticker_id, '_message_text':None}, 'type':'message'}

    @staticmethod
    def parse_attachments(attachments):
        entities = {
            'current_location' : [],
            'attachment' : [],
            '_message_text' : [{'value':None}]
        }
        for attachment in attachments:
            if 'coordinates' in attachment['payload']:
                coordinates = attachment['payload']['coordinates']
                entities['current_location'].push({'value':coordinates})
            if 'url' in attachment['payload']:
                url = attachment['payload']['url']
                # TODO: add attachment type by extension
                entities['attachment'].append({'value':url})
        return {'entities' : entities, 'type':'message'}
