import pickle

from golem.core.chat_session import ChatSession, Profile
from golem.core.message_parser import parse_text_message
from golem.core.persistence import get_redis
from golem.core.responses import TextMessage
from golem.tasks import accept_user_message


class GoogleActionsInterface():
    name = 'google_actions'
    prefix = 'goog'
    messages = []
    states = []

    response_cache = {}

    @staticmethod
    def clear():
        GoogleActionsInterface.messages = []
        GoogleActionsInterface.states = []

    @staticmethod
    def fill_session_profile(session: ChatSession):
        if not session:
            raise ValueError("Session is None")
        session.profile = Profile(first_name='Test', last_name='')
        return session

    @staticmethod
    def post_message(session, response):
        if not response:
            return
        GoogleActionsInterface.messages.append(response)
        # TODO clear on received message
        # TODO don't pickle it
        data = pickle.dumps(response)
        get_redis().lpush("response_for_{id}".format(id=session.chat_id), data)

    @staticmethod
    def convert_responses(session, responses):

        if responses is None:
            return {}

        json_response = {
            "conversationToken": session.meta.get("chat_id"),
            "expectUserResponse": True,
            "expectedInputs": [
                {
                    "inputPrompt": {
                        "richInitialPrompt": {
                            "items": [],
                            "suggestions": []
                        }
                    },
                    "possibleIntents": [
                        {
                            "intent": "actions.intent.TEXT"
                        }
                    ]
                }
            ]
        }

        for response in responses:
            if isinstance(response, TextMessage):
                resp = {
                    "simpleResponse": {
                        "textToSpeech": response.text,
                        "displayText": response.text
                    }
                }
                json_response['expectedInputs'][0]['inputPrompt']['richInitialPrompt']['items'].append(resp)

        return json_response
        # return json.dumps(json_response)

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
        if not GoogleActionsInterface.states or GoogleActionsInterface.states[-1] != state:
            GoogleActionsInterface.states.append(state)

    @staticmethod
    def accept_request(body):
        uid = body['user']['userId']
        chat_id = body['conversation']['conversationId']
        meta = {"uid": uid, "chat_id": chat_id}
        profile = Profile(uid, None, None)
        session = ChatSession(GoogleActionsInterface, chat_id, meta, profile)
        accept_user_message.delay(session.to_json(), body).get()
        # responses = GoogleActionsInterface.response_cache.get(session.chat_id)
        key = "response_for_{id}".format(id=session.chat_id)
        num_resp = get_redis().llen(key)
        responses = get_redis().lrange(key, 0, num_resp)
        responses = [pickle.loads(resp) for resp in responses]
        return GoogleActionsInterface.convert_responses(session, responses)

    @staticmethod
    def parse_message(msg, num_tries=1):
        # intent = msg['inputs']['intent']
        # if intent == "assistant.intent.action.MAIN":
        #     intent = 'default'
        text = msg['inputs'][0]['rawInputs'][0]['query']
        parsed = parse_text_message(text)
        return parsed
