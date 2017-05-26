from .responses import MessageElement
import json
import time
from golem.core.persistence import get_elastic

class Logger:
    def __init__(self, uid, interface):
        self.uid = uid
        self.interface = interface

    def log_user_message(self, type_, entities, accepted_time, state):
        #es = get_elastic()
        entities = entities.copy()
        text = None
        if '_message_text' in entities:
            text = entities['_message_text'][0]['value']
            del(entities['_message_text'])

        message = {
            'uid' : self.uid,
            'created': accepted_time,
            'is_user' : True,
            'text' : text,
            'state' : state,
            'type' : type_,
            'entities' : entities
        }
        self.log_message(message)

    def log_bot_message(self, response, state):
        #es = get_elastic()
        text = response.text if hasattr(response, 'text') else None
        if isinstance(response, str):
            text = response
            response = None
        elif not isinstance(response, MessageElement):
            return

        message = {
            'uid' : self.uid,
            'created': time.time(),
            'is_user' : False,
            'text' : text,
            'state' : state,
            'type' : type(response).__name__ if response else 'TextMessage',
            'response' : json.loads(json.dumps(response, default=lambda obj: obj.__dict__ if hasattr(obj,'__dict__') else str(obj)))
        }
        self.log_message(message)

    def log_error(self, exception, state):
        message = {
            'uid' : self.uid,
            'created': time.time(),
            'is_user' : False,
            'text' : str(exception),
            'state' : state,
            'type' : 'error'
        }
        self.log_message(message)

    def log_message(self, message):
        es = get_elastic()
        if es:
            es.index(index="message-log", doc_type='message', body=message)

    def log_user(self, profile):
        user = {
            'uid' : self.uid,
            'profile': profile
        }
        es = get_elastic()
        if es:
           es.create(index="message-log", id=user['uid'], doc_type='user', body=user)

