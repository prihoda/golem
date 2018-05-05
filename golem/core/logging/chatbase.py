import logging

import requests

from golem.core.logging.abs_logger import MessageLogger


class ChatbaseLogger(MessageLogger):
    def __init__(self, api_key):
        super().__init__()
        self.base_url = 'https://chatbase.com/api'
        self.api_key = api_key
        if self.api_key is None:
            logging.warning("Chatbase API key not provided, will not log!")

    def _interface_to_platform(self, interface: str):
        if interface is None:
            return None
        return interface  # TODO

    def log_user_message(self, dialog, accepted_time, state, message: dict, type, entities):
        payload = {
            "api_key": self.api_key,
            "type": "user",
            "user_id": dialog.session.chat_id,
            "time_stamp": int(accepted_time * 1000),
            "platform": self._interface_to_platform(dialog.session.interface.name),
            "message": str(message),
            "intent": dialog.context.get("intent", max_age=0),
            "session_id": state,
            "not_handled": False,  # TODO
            "version": "1.0",  # TODO
        }
        response = requests.post(self.base_url + "/message", params=payload)
        if not response.ok:
            logging.error("Chatbase request with code %d, reason: %s", response.status_code, response.reason)
        return response.ok

    def log_bot_message(self, dialog, accepted_time, state, message):
        payload = {
            "api_key": self.api_key,
            "type": "agent",
            "user_id": dialog.session.chat_id,
            "time_stamp": int(accepted_time * 1000),
            "platform": self._interface_to_platform(dialog.session.interface.name),
            "message": str(message),
            "intent": dialog.context.get("intent", max_age=0),
            "session_id": state,
            "not_handled": False,  # TODO
            "version": "1.0",  # TODO
        }
        response = requests.post(self.base_url + "/message", params=payload)
        if not response.ok:
            logging.error("Chatbase request with code %d, reason: %s", response.status_code, response.reason)
        return response.ok
