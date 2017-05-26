import json
import requests
from golem.core.message_parser import parse_text_message
from golem.core.serialize import json_serialize,json_deserialize
import hashlib
from golem.core.responses import *
from pprint import pprint
from golem.core.persistence import get_redis
from django.conf import settings  

class TelegramInterface():
    name = 'telegram'
    # Post function to handle Telegram messages
    @staticmethod
    def accept_request(request):
        pprint(request)
        if 'callback_query' in request:
            message = request['callback_query']['message']
        elif 'message' in request:
            message = request['message']
        else:
            raise KeyError("Not supported message type {}".format(request))

        raw_message = request

        if True:#diff.total_seconds() < 30:
            print('INCOMING RAW TELEGRAM MESSAGE:', raw_message)
            uid = TelegramInterface.tid_to_uid(message['chat']['id'])
            # Confirm accepted message
            TelegramInterface.post_message(uid, SenderActionMessage('typing'))
            # Add it to the message queue
            TelegramInterface.tasks.add('input_msg', (uid, raw_message, TelegramInterface))
        elif message.get('date'):
            print("Delay too big, ignoring message!")
            print(raw_message)

    @staticmethod
    def uid_to_tid(uid):
        return uid.split('_',maxsplit=1)[1] # uid has format t_{number}

    @staticmethod
    def tid_to_uid(tid):
         return 't_'+str(tid)

    @staticmethod
    def load_profile(uid):
        return {}

    @staticmethod
    def post_message(uid, response):

        if isinstance(response, GenericTemplateMessage):
            for element in response.elements[:3]:
                TelegramInterface.post_message(uid, element)
            return
        elif isinstance(response, MessageElement):
            tid = TelegramInterface.uid_to_tid(uid)
            response_method, response_dict = TelegramInterface.to_message(response)
            response_dict['chat_id'] = tid
        elif isinstance(response, ThreadSetting):
            print('Ignoring Telegram setting', response)
            return
        else:
            raise ValueError('Error: Invalid message type: {} == {}: {}'.format(type(response), MessageElement, response))

        config = settings.GOLEM_CONFIG
        post_message_url = config.get('TELEGRAM_HOSTNAME')+config.get('TELEGRAM_TOKEN')+response_method

        # print("POST", post_message_url)
        print("RESPONSE")
        pprint(post_message_url)
        pprint(response_dict)
        r = requests.post(post_message_url,
                               headers={"Content-Type": "application/json"},
                               data=json.dumps(response_dict, default=json_serialize))
        if r.status_code != 200:
            print('ERROR: MESSAGE REFUSED: ', response_dict)
            print('ERROR: ', r.text)
            raise Exception(r.json()['error']['message'])

    @staticmethod
    def to_message(response):
        if isinstance(response, TextMessage):
            message = {'text': response.text}
            if response.buttons:
                message["reply_markup"] = {'inline_keyboard': [TelegramInterface.to_message_element(button) for button in response.buttons]}
            elif response.quick_replies:
                message["reply_markup"] = {'inline_keyboard': [TelegramInterface.to_message_element(quick_reply) for quick_reply in response.quick_replies if quick_reply.title]}
               
            return "sendMessage", message

        elif isinstance(response, SenderActionMessage):
            return "sendChatAction", {'action': response.action}

        elif isinstance(response, AttachmentMessage):
            return "sendMessage", { "text":response.url }  # TODO telegram attachments

        elif isinstance(response, GenericTemplateElement):
            desc = response.title if response.title else ''
            desc += '\n'+response.subtitle if response.subtitle else ''
            message = {
                "caption": desc,
                "photo": response.image_url if response.image_url else '',
            }
            if response.buttons:
                message["reply_markup"] = json.dumps({'inline_keyboard': [TelegramInterface.to_message_element(button) for button in response.buttons]})
            return "sendPhoto", message

        
            
        raise ValueError('Error: Invalid message type: {}: {}'.format(type(response), response))
    
    @staticmethod
    def to_message_element(response):
        if isinstance(response, QuickReply):
            message = {"text": response.title}
            payload = json.dumps(response.payload if response.payload else response.title, default=json_serialize)
            key = 'callback_'+ hashlib.md5(payload).hexdigest()
            db = get_redis()
            db.set(key, payload, ex=3600*24*7)
            message['callback_data'] = json.dumps(key)
            return [message]

        elif isinstance(response, Button):
            message = {"text": response.title}
            if response.payload:
                payload = json.dumps(response.payload, default=json_serialize)
                key = 'callback_'+ hashlib.md5(payload).hexdigest()
                db = get_redis()
                db.set(key, payload, ex=3600*24*7)
                message['callback_data'] = json.dumps(key)
                return [message]
            elif response.url:
                message['url'] = response.url
                return [message]
            return []
        return None

    @staticmethod
    def send_settings(settings):
        TelegramInterface.post_message(None, settings)

    @staticmethod
    def processing_start(uid):
        # Show typing animation
        TelegramInterface.post_message(uid, SenderActionMessage('typing'))

    @staticmethod
    def processing_end(uid):
        pass

    @staticmethod
    def state_change(state):
        pass

    @staticmethod
    def parse_message(raw_message, num_tries=1):
        print(raw_message)
        db = get_redis()
        if 'callback_query' in raw_message:
            key = json.loads(raw_message['callback_query']['data'], object_hook=json_deserialize)
            if not db.exists(key):
                return {'entities': None, 'type':'postback'}
            payload = json.loads(db.get(key).decode(encoding='UTF-8'))
            print("PAYLOAD", payload)
            payload['_message_text'] = [{'value':None}]
            return {'entities': payload, 'type':'postback'}
        elif 'message' in raw_message:
            if 'sticker_id' in raw_message['message']:
                return TelegramInterface.parse_sticker(raw_message['message']['sticker_id'])
            if 'attachments' in raw_message['message']:
                attachments = raw_message['message']['attachments']
                return TelegramInterface.parse_attachments(attachments)
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
