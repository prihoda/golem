from unittest import TestCase

from golem.core.chat_session import ChatSession
from golem.core.context import Context
from golem.core.dialog_manager import DialogManager
from golem.core.interfaces.test import TestInterface


# mock_redis = mockredis.mock_redis_client()


# def get_fake_redis():
#      return mock_redis


class TestContext(TestCase):

    #@patch('redis.Redis', mockredis.mock_redis_client)
    #@patch('redis.StrictRedis', mockredis.mock_strict_redis_client)
    def setUp(self):
        self.session = ChatSession(TestInterface, 'test_id')
        self.dialog = DialogManager(self.session)

    def test_context_get_set(self):
        context = Context(dialog=self.dialog, entities={}, history=[], counter=0)
        context.intent = "greeting"
        context.intent = "goodbye"
        intent = context.intent.current_v()
        self.assertEquals(intent, "goodbye")
        cnt = context.intent.count()
        self.assertEquals(cnt, 2)
