from .context import Context
from .serialize import json_deserialize,json_serialize
from .persistence import get_redis
from .responses import MessageElement
from .tests import ConversationTestRecorder
from .flow import Flow
from .responses import *
import json
import re
import importlib, logging
import time
from django.conf import settings  
from .logger import Logger
from golem.tasks import accept_inactivity_callback, accept_schedule_callback

class DialogManager:
    version = '1.28'

    def __init__(self, uid, interface, test_id=None):
        self.uid = uid
        self.test_id = test_id
        self.interface = interface
        self.logger = Logger(uid=uid, interface=interface, test_id=test_id)
        self.profile = interface.load_profile(uid)
        self.db = get_redis()
        self.log = logging.getLogger()
            
        entities = {}
        version = self.db.get('dialog_version')
        self.log.info('Initializing dialog for user %s...' % uid)
        self.current_state_name = None
        self.context = None
        if version and version.decode('utf-8')==DialogManager.version and self.db.hexists('session_entities', self.uid):
            entities_string = self.db.hget('session_entities', self.uid)
            history_string = self.db.hget('session_history', self.uid)
            self.init_flows()
            state = self.db.hget('session_state', self.uid).decode('utf-8')
            counter = int(self.db.hget('session_counter', self.uid))
            self.log.info('Session exists at state %s' % (state))
            self.move_to(state, initializing=True)
            #self.log.info(entities_string)
            entities = json.loads(entities_string.decode('utf-8'), object_hook=json_deserialize)
            history = json.loads(history_string.decode('utf-8'), object_hook=json_deserialize)
        else:
            self.current_state_name = 'default.root'
            self.log.info('Creating new session...')
            counter = 0
            history = []
            self.init_flows()
            self.logger.log_user(self.profile)
        self.context = Context(entities=entities, history=history, counter=counter, dialog=self)

    def init_flows(self):
        self.flows = {}
        flow_definitions = self.create_flows()
        for flow_name,flow_definition in flow_definitions.items():
            self.flows[flow_name] = Flow(flow_name, dialog=self, definition=flow_definition)
        self.current_state_name = 'default.root'

    def create_flows(self):
        flow = {}  
        BOTS = settings.GOLEM_CONFIG.get('BOTS')
        for module_name in BOTS:
            module = importlib.import_module(module_name)
            flow.update(module.flow)
        return flow

    @staticmethod
    def clear_uid(uid):
        db = get_redis()
        db.hdel('session_state', uid)
        db.hdel('session_entities', uid)

    def process(self, message_type, entities):
        self.interface.processing_start(self.uid)
        accepted_time = time.time()
        accepted_state = self.current_state_name
        # Only process messages and postbacks (not 'seen_by's, etc)
        if message_type not in ['message','postback','schedule']:
            return

        self.log.info('-- USER message ----------------------------------')

        if message_type != 'schedule':
            self.context.counter += 1

        entities = self.context.add_entities(entities)

        if self.test_record_message(message_type, entities):
            return

        if message_type != 'schedule':
            self.save_inactivity_callback()

        self.log.info('++ PROCESSING ++++++++++++++++++++++++++++++++++++')

        if not self.check_state_transition():
            if not self.check_intent_transition():
                # run the action
                self.run_accept(save_identical=True)
                self.save_state()

        self.interface.processing_end(self.uid)

        # leave logging message to the end so that the user does not wait
        self.logger.log_user_message(message_type, entities, accepted_time, accepted_state)

    def schedule(self, callback_name, at=None, seconds=None):
        self.log.info('Scheduling callback "{}": at {} / seconds: {}'.format(callback_name, at, seconds))
        if at:
            if at.tzinfo is None or at.tzinfo.utcoffset(at) is None:
                raise Exception('Use datetime with timezone, e.g. "from django.utils import timezone"')
            accept_schedule_callback.apply_async((self.interface.name, self.uid, callback_name), eta=at)
        elif seconds:
            accept_schedule_callback.apply_async((self.interface.name, self.uid, callback_name), countdown=seconds)
        else:
            raise Exception('Specify either "at" or "seconds" parameter')

    def inactive(self, callback_name, seconds):
        self.log.info('Setting inactivity callback "{}" after {} seconds'.format(callback_name, seconds))
        accept_inactivity_callback.apply_async((self.interface.name, self.uid, self.context.counter, callback_name, seconds), countdown=seconds)

    def save_inactivity_callback(self):
        self.db.hset('session_active', self.uid, time.time())
        callbacks = settings.GOLEM_CONFIG.get('INACTIVE_CALLBACKS')
        if not callbacks:
            return
        for name in callbacks:
            seconds = callbacks[name]
            self.inactive(name, seconds)


    def test_record_message(self, message_type, entities):
        record, record_age = self.context.get_age('test_record')
        self.recording = False
        if not record:
            return False
        if record_age == 0:
            if record == 'start':
                self.send_response(ConversationTestRecorder.record_start())
            elif record == 'stop':
                self.send_response(ConversationTestRecorder.record_stop())
            else:
                self.send_response("Use /test_record/start/ or /test_record/stop/")
            self.save_state()
            return True
        if record == 'start':
            ConversationTestRecorder.record_user_message(message_type, entities)
            self.recording = True
        return False

    def run_accept(self, save_identical=False):
        self.log.warn('Running ACCEPT action of {}'.format(self.current_state_name))
        state = self.get_state()
        if not state.accept:
            self.log.warn('State does not have an ACCEPT action, we are done.')
            return
        response, new_state_name = state.accept(state=state)
        self.send_response(response)
        self.move_to(new_state_name, save_identical=save_identical)

    def run_init(self):
        self.log.warn('Running INIT action of {}'.format(self.current_state_name))
        state = self.get_state()
        if not state.init:
            self.log.warn('State does not have an INIT action, we are done.')
            return
        response, new_state_name = state.init(state=state)
        self.send_response(response)
        self.move_to(new_state_name)

    def check_state_transition(self):
        new_state_name = self.context.get('_state', max_age=0)
        return self.move_to(new_state_name)

    def check_intent_transition(self):
        intent = self.context.get('intent', max_age=0)
        if not intent:
            return False
        # Get custom intent transition
        new_state_name = self.get_state().get_intent_transition(intent)
        # If no custom intent transition present, move to the flow whose 'intent' field matches intent
        # Check accepted intent of the current flow's states
        if not new_state_name:
            for state in self.get_flow().states.values():
                if state.intent and re.match(state.intent, intent):
                    new_state_name = state.name
                    break
        # Check accepted intent of all flows
        if not new_state_name:                
            for flow in self.flows.values():
                if re.match(flow.intent, intent):
                    new_state_name = flow.name+'.root'
                    break

        if not new_state_name:
            self.log.error('Error! Found intent "%s" but no flow present for it!' % intent)
            return False

        new_state_name = new_state_name+':accept'
        self.log.info('Moving based on intent %s...' % (intent))
        return self.move_to(new_state_name)

    def get_flow(self, flow_name=None):
        if not flow_name:
            flow_name,_ = self.current_state_name.split('.', 1)
        return self.flows.get(flow_name)

    def get_state(self, flow_state_name=None):
        flow_name,state_name = (flow_state_name or self.current_state_name).split('.', 1)
        flow = self.get_flow(flow_name)
        return flow.get_state(state_name) if flow else None

    def move_to(self, new_state_name, initializing=False, save_identical=False):
        # if flow prefix is not present, add the current one
        action = 'init'
        if isinstance(new_state_name, int):
            new_state = self.context.get_history_state(new_state_name-1)
            new_state_name = new_state['name'] if new_state else None
            action = None
        if not new_state_name:
            new_state_name = self.current_state_name
        if new_state_name.count(':'):
            new_state_name,action = new_state_name.split(':',1)
        if ('.' not in new_state_name):
            new_state_name = self.current_state_name.split('.')[0]+'.'+new_state_name
        if not self.get_state(new_state_name):
            self.log.info('Error: State %s does not exist! Staying at %s.' % (new_state_name, self.current_state_name))
            return False
        identical = new_state_name == self.current_state_name
        if not initializing and (not identical or save_identical):
            self.context.add_state(new_state_name)
        if not new_state_name or identical:
            return False
        previous_state = self.current_state_name
        self.current_state_name = new_state_name
        if not initializing:
            self.log.info('MOVING %s -> %s %s' % (previous_state, new_state_name, action))

            # notify the interface that the state was changed
            self.interface.state_change(self.current_state_name)
            # record change if recording test
            if self.recording:
                ConversationTestRecorder.record_state_change(self.current_state_name)

            if action=='init':
                self.run_init()
            elif action=='accept':
                self.run_accept()

        self.save_state()
        return True

    def save_state(self):
        if not self.context:
            return
        self.log.info('Saving state at %s' % (self.current_state_name))
        self.db.hset('session_state', self.uid, self.current_state_name)
        self.db.hset('session_history', self.uid, json.dumps(self.context.history, default=json_serialize))
        self.db.hset('session_entities', self.uid, json.dumps(self.context.entities, default=json_serialize))
        self.db.hset('session_counter', self.uid, self.context.counter)
        self.db.hset('session_interface', self.uid, self.interface.name)
        self.db.set('dialog_version', DialogManager.version)


    def send_response(self, responses):
        if not responses:
            return
        self.log.info('-- CHATBOT message -------------------------------')

        if not isinstance(responses, list):
            return self.send_response([responses])

        for response in responses:
            if isinstance(response, str):
                response = TextMessage(text=response)

            # Send the response
            self.interface.post_message(self.uid, response)

            # Record if recording
            if self.recording:
                ConversationTestRecorder.record_bot_message(response)

        for response in responses:
            # Log the response
            self.log.info('Message: {}'.format(response))
            self.logger.log_bot_message(response, self.current_state_name)

