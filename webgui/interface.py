import logging
import random
import time

from django.db import OperationalError

from golem.core.message_parser import parse_text_message
from golem.tasks import accept_user_message
from .models import Message, Button, Element


class WebGuiInterface:
    name = 'webgui'
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
    def post_message(uid, response):
        uid = uid.split('_')[1]
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
                # TODO postbacks
                # todo parse stuff
                b.save()

        try:
            for q in response.quick_replies:
                b = Button()
                b.message_id = message.id
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
    def processing_start(uid):
        pass

    @staticmethod
    def processing_end(uid):
        pass

    @staticmethod
    def state_change(state):
        if not WebGuiInterface.states or WebGuiInterface.states[-1] != state:
            WebGuiInterface.states.append(state)

    @staticmethod
    def parse_message(user_message, num_tries=1):
        return parse_text_message(user_message)

    @staticmethod
    def accept_request(msg: Message):
        logging.critical('Got message')
        accept_user_message.delay('webgui', 'web_' + str(msg.uid), msg.text)

    @staticmethod
    def make_uid(username) -> str:
        # FIXME ensure uid doesn't exist or is expired
        uid = '_'.join([str(username), str(random.randint(1000, 9999))])
        # delete messages for old session with this uid, if there was one
        try:
            Message.objects.get(uid__exact=uid).delete()
        except OperationalError:
            pass  # first user, there is no such table yet
        return uid

    @staticmethod
    def destroy_uid(uid):
        Message.objects.get(uid__exact=uid).delete()
