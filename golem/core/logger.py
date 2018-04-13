import json
import logging
import time

from django.conf import settings

from golem.core.abs_logger import MessageLogger
from golem.core.chat_session import ChatSession, Profile
from golem.core.persistence import get_elastic
from .responses.responses import MessageElement


class ElasticsearchLogger(MessageLogger):
    def __init__(self):
        super().__init__()
        self.enabled = bool(get_elastic())

    def log_user_message(self, dialog, time, state, message, type_, entities):
        #es = get_elastic()
        entities = entities.copy()
        text = None
        if '_message_text' in entities:
            text = entities['_message_text'][0]['value']
            del(entities['_message_text'])

        message = {
            'uid' : dialog.session.chat_id,
            'test_id' : -1,  # TODO
            'created': time,
            'is_user' : True,
            'text' : text,
            'state' : state,
            'type' : type_,
            'entities' : entities
        }
        self.log_message(message)

    def log_bot_message(self, dialog, time, state, message):
        #es = get_elastic()
        # text = response.text if hasattr(response, 'text') else None
        # if isinstance(response, str):
        #     text = response
        #     response = None
        # elif not isinstance(response, MessageElement):
        #     return

        message = {
            'uid' : dialog.session.chat_id,
            'test_id' : -1,  # TODO
            'created': time,
            'is_user' : False,
            'text' : message,
            'state' : state,
            'type' : None,  # TODO 'type(response).__name__ if response else 'TextMessage',
            'response' : None, # TODO json.loads(json.dumps(response, default=lambda obj: obj.__dict__ if hasattr(obj,'__dict__') else str(obj)))
        }
        self.log_message(message)

    def log_error(self, exception, state):
        message = {
            'uid' : self.uid,
            'test_id' : self.test_id,
            'created': time.time(),
            'is_user' : False,
            'text' : str(exception),
            'state' : state,
            'type' : 'error'
        }
        self.log_message(message)

    def log_message(self, message):
        if not self.enabled:
            return
        es = get_elastic()
        if not es:
            return
        try:
            es.index(index="message-log", doc_type='message', body=message)
        except:
            print('Unable to log message to Elasticsearch.')

    def log_user(self, profile: Profile):
        if not self.enabled:
            return
        user = {
            'uid' : self.uid,
            'profile': profile.to_json()
        }
        es = get_elastic()
        if not es:
            return
        try:
            es.create(index="message-log", id=user['uid'], doc_type='user', body=user)
        except:
            print('Unable to log user profile to Elasticsearch.')


class MessageLogging:

    def __init__(self, dialog):
        self.loggers = []
        self.dialog = dialog

    def log_user_message(self, type, entities, accepted_time, accepted_state):
        """
        Log user message to all registered loggers.
        :param type:            One of: message, postback, schedule
        :param entities:        A dict containing all the message entities
        :param accepted_time:   Unix timestamp - when was the message processed
        :param accepted_state:  Conversation state after processing the message
        :return:
        """
        # TODO this has to be called async
        message_text = entities.get("_message_text", "<POSTBACK/SCHEDULE>")
        for logger in MESSAGE_LOGGERS:
            logger.log_user_message(self.dialog, accepted_time, accepted_state, message_text)

    def log_bot_message(self, message, state):
        for logger in MESSAGE_LOGGERS:
            logger.log_bot_message(self.dialog, int(time.time()), state, message)


MESSAGE_LOGGERS = []


def register_logger(logger):
    if isinstance(logger, MessageLogger):
        logging.debug("Registering logger %s", logger.__class__.__name__)
        MESSAGE_LOGGERS.append(logger)
    else:
        raise ValueError("Error: Must be an instance of golem.core.abs_logger.MessageLogger")


try:
    for item in settings.GOLEM_CONFIG.get("MESSAGE_LOGGERS", []):
        register_logger(item)
except Exception as ex:
    raise ValueError("Error registering message loggers, is your configuration correct?") from ex
