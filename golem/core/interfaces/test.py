class TestInterface():
    name = 'test'
    prefix = 'test'
    messages = []
    states = []

    @staticmethod
    def clear():
        TestInterface.messages = []
        TestInterface.states = []

    @staticmethod
    def load_profile(uid):
        return {'first_name': 'Tests', 'last_name': ''}

    @staticmethod
    def post_message(uid, chat_id, response):
        TestInterface.messages.append(response)

    @staticmethod
    def send_settings(settings):
        pass

    @staticmethod
    def processing_start(uid, chat_id):
        pass

    @staticmethod
    def processing_end(uid, chat_id):
        pass

    @staticmethod
    def state_change(state):
        if not TestInterface.states or TestInterface.states[-1] != state:
            TestInterface.states.append(state)

    @staticmethod
    def parse_message(user_message, num_tries=1):
        return user_message
