import json
import logging
import time

import random

from core.chat_session import ChatSession
from core.message_parser import parse_text_message
from core.responses.buttons import PayloadButton
from core.responses.quick_reply import LocationQuickReply
from core.tasks import accept_user_message
from .models import Message, Button, Element


class WebGuiInterface:
    name = 'golm_webgui'
    prefix = 'web'
    messages = []
    states = []

    @staticmethod
    def clear():
        WebGuiInterface.messages = []
        WebGuiInterface.states = []

    @staticmethod
    def load_profile(uid):
        return {'first_name': 'Tests', 'last_name': ''}

    @staticmethod
    def post_message(session, response):
        uid = session.meta.get("uid")
        WebGuiInterface.messages.append(response)
        message = Message()
        message.uid = uid
        message.timestamp = time.time()
        message.is_response = True
        try:
            message.text = response.text
        except AttributeError:
            pass
        message.save()
        if hasattr(response, 'buttons'):
            for btn in response.buttons:
                b = Button()
                b.message_id = message.id
                b.text = btn.title
                if hasattr(btn, 'url'):
                    b.action = 'link'
                    b.url = btn.url
                elif isinstance(btn, PayloadButton):
                    b.action = "postback"
                    b.url = btn.payload
                # todo parse stuff
                b.save()

        try:
            for q in response.quick_replies:
                b = Button()
                b.message_id = message.id
                if isinstance(q, LocationQuickReply):
                    b.text = 'My location\n(unsupported in web gui)'
                    b.action = 'null'  # TODO support sending location
                else:
                    b.text = q.title
                    b.action = 'reply'
                b.save()
        except AttributeError:
            pass
        try:
            for element in response.elements:
                e = Element()
                e.message_id = message.id
                e.title = element.title
                e.image_url = element.image_url
                e.subtitle = element.subtitle
                e.save()
                # todo buttons in elements etc.
                # todo quick replies
        except AttributeError:
            pass

    @staticmethod
    def send_settings(settings):
        pass

    @staticmethod
    def processing_start(session):
        pass

    @staticmethod
    def processing_end(session):
        pass

    @staticmethod
    def state_change(state):
        if not WebGuiInterface.states or WebGuiInterface.states[-1] != state:
            WebGuiInterface.states.append(state)

    @staticmethod
    def parse_message(user_message, num_tries=1):
        logging.info('[WEBGUI] @ parse_message')
        if user_message.get('text'):
            return parse_text_message(user_message.get('text'))
        elif user_message.get("payload"):
            data = user_message.get("payload")
            logging.info("Payload is: {}".format(data))
            if isinstance(data, dict):
                return {'entities': data, 'type': 'postback'}
            else:
                from core.serialize import json_deserialize
                payload = json.loads(data, object_hook=json_deserialize)
                payload['_message_text'] = [{'value': None}]
                return {'entities': payload, 'type': 'postback'}

    @staticmethod
    def accept_request(msg: Message):
        uid = str(msg.uid)
        logging.info('[WEBGUI] Received message from {}'.format(uid))
        session = ChatSession(WebGuiInterface, uid, meta={"uid": uid})
        accept_user_message.delay(session.to_json(), {"text": msg.text})

    @staticmethod
    def accept_postback(msg: Message, data):
        uid = str(msg.uid)
        logging.info('[WEBGUI] Received postback from {}'.format(uid))
        session = ChatSession(WebGuiInterface, uid, meta={"uid": uid})
        accept_user_message.delay(session.to_json(), {"payload": data})

    @staticmethod
    def make_uid(username) -> str:
        uid = None
        tries = 0
        while (not uid or len(Message.objects.filter(uid__exact=uid)) != 0) or tries < 100:
            uid = '_'.join([str(username), str(random.randint(1000, 99999))])
            tries += 1
        # delete messages for old session with this uid, if there was one
        # FIXME invalidate the previous user's session!
        try:
            Message.objects.get(uid__exact=uid).delete()
        except Exception:
            pass  # first user, there is no such table yet
        return uid

    @staticmethod
    def destroy_uid(uid):
        Message.objects.filter(uid__exact=uid).delete()
