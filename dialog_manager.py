from .context import Context
from .templates import Templates
from .serialize import json_deserialize,json_serialize
import json
import re
import importlib, logging

class DialogManager:
    version = '1.21'

    def __init__(self, config, uid, interface):
        self.uid = uid
        self.interface = interface
        self.config = config
        self.db = config['GET_STORAGE']()
        if config.get('GET_LOGGER'):
            self.log = config['GET_LOGGER'](uid)
        if not self.log:
            self.log = logging.getLogger()
        chatbot_module = importlib.import_module(config['CHATBOT_MODULE'])
        self.create_flows = chatbot_module.create_flows
        entities = {}
        version = self.db.get('dialog_version')
        self.log.info('Initializing dialog for user %s...' % uid)
        self.chatbot_version = 'default'
        self.current_state_name = 'default.root'
        self.context = None
        if version and version.decode('utf-8')==DialogManager.version and self.db.hexists('session_entities', self.uid):
            entities_string = self.db.hget('session_entities', self.uid)
            self.chatbot_version = self.db.hget('session_chatbot_version', self.uid).decode('utf-8')
            self.init_flows()
            state = self.db.hget('session_state', self.uid).decode('utf-8')
            counter = int(self.db.hget('session_counter', self.uid))
            self.log.info('Session exists at state %s (version %s)' % (state, self.chatbot_version))
            self.move_to(state, initializing=True)
            #self.log.info(entities_string)
            entities = json.loads(entities_string.decode('utf-8'), object_hook=json_deserialize)
        else:
            self.log.info('Creating new session...')
            counter = 0
            self.init_flows()
        self.context = Context(counter=counter, entities=entities, dialog=self)

    def init_flows(self):
        self.flows = {}
        flow_definitions = self.create_flows(version=self.chatbot_version)
        for flow_name,flow_definition in flow_definitions.items():
            self.flows[flow_name] = Flow(flow_name, dialog=self, definition=flow_definition)
        self.current_state_name = 'default.root'


    def process(self, raw_message):
        self.log.info('MARKING PROCESSED MESSAGE FOR {}'.format(self.uid))
        self.interface.processing_start(self.uid)

        self.log.info('PROCESSING MESSAGE: {}'.format(raw_message))
        # Parse new message and add entities to context
        parsed = self.interface.parse_message(raw_message)

        self.log.info('PARSED MESSAGE: {}'.format(parsed))

        # Only process messages and postbacks (not 'seen_by's, etc)
        if parsed['type'] not in ['message','postback']:
            return

        debug_entities = self.context.get('debug_entities')
        if debug_entities and bool(int(debug_entities)):
            for entity,values in parsed['entities'].items():
                self.send_response("{}: {}".format(entity, values))

        self.log.info('-- USER message ----------------------------------')

        self.context.add(parsed['entities'])

        self.log.info('++ PROCESSING ++++++++++++++++++++++++++++++++++++')

        self.check_version_transition()
        if not self.check_state_transition():
            self.check_intent_transition()

        self.log.info('** RUNNING ACTION ********************************')
        self.run_accept()

    def run_accept(self):
        self.log.info('Running ACCEPT action of {}'.format(self.current_state_name))
        state = self.get_state()
        if not state.accept:
            return
        response, new_state_name = state.accept(state=state)
        self.send_response(response)
        self.move_to(new_state_name)

    def run_init(self):
        self.log.info('Running INIT action of {}'.format(self.current_state_name))
        state = self.get_state()
        if not state.init:
            return
        response, new_state_name = state.init(state=state)
        self.send_response(response)
        self.move_to(new_state_name)

    def check_version_transition(self):
        new_version = self.context.get('version', max_age=0)
        if new_version:
            self.chatbot_version = new_version
            self.init_flows()
            self.send_response('Sure, moving to %s ;)' % new_version)
            self.log.info('Moving to custom chatbot version: %s' % new_version)
            return True
        return False

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
        if not new_state_name:
            for state in self.get_flow().states.values():
                if state.intent and re.match(state.intent, intent):
                    new_state_name = state.name
                    break
            for flow in self.flows.values():
                if re.match(flow.intent, intent):
                    new_state_name = flow.name+'.root'
                    break

        if not new_state_name:
            print('Error! Found intent "%s" but no flow present for it!' % intent)
            return False

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

    def move_to(self, new_state_name, initializing=False):
        # if flow prefix is not present, add the current one
        action = 'init'
        if new_state_name and new_state_name.count(':'):
            new_state_name,action = new_state_name.split(':',1)
        if new_state_name and ('.' not in new_state_name):
            new_state_name = self.current_state_name.split('.')[0]+'.'+new_state_name
        if not new_state_name or new_state_name == self.current_state_name:
            self.save_state()
            return
        if not self.get_state(new_state_name):
            self.log.info('Error: State %s does not exist! Staying at %s.' % (new_state_name, self.current_state_name))
            self.save_state()
            return
        self.log.info('Moving from %s to %s %s' % (self.current_state_name, new_state_name, action))
        self.current_state_name = new_state_name
        self.save_state()
        if not initializing:
            if action=='init':
                self.run_init()
            elif action=='accept':
                self.run_accept()
        return True

    def save_state(self):
        if not self.context:
            return
        self.log.info('Saving new state %s (%s)' % (self.current_state_name, self.chatbot_version))
        self.db.hset('session_state', self.uid, self.current_state_name)
        self.db.hset('session_entities', self.uid, json.dumps(self.context.entities, default=json_serialize))
        self.db.hset('session_counter', self.uid, self.context.counter)
        self.db.hset('session_chatbot_version', self.uid, self.chatbot_version)
        self.db.set('dialog_version', DialogManager.version)

    def send_response(self, response):
        if not response:
            return
        self.log.info('-- CHATBOT message -------------------------------')
        if not isinstance(response, list):
            response = [response]
        for resp in response:
            self.log.info('Message: {}'.format(resp))

        # Send the response
        self.interface.post_message(self.uid, response)

class Flow:
    def __init__(self, name, dialog, definition):
        self.name = name
        self.dialog = dialog
        self.states = {}
        self.current_state_name = 'root'
        self.intent = definition.get('intent') or name
        for state_name,state_definition in definition['states'].items():
            self.states[state_name] = State(name+'.'+state_name, dialog=dialog, definition=state_definition)

    def get_state(self, state_name):
        return self.states.get(state_name)

    def __str__(self):
        return self.name + ":flow"

class State:
    def __init__(self, name, dialog, definition):
        self.name = name
        self.dialog = dialog
        self.intent_transitions = definition.get('intent_transitions') or {}
        self.intent = definition.get('intent')
        self.init = self.create_action(definition.get('init'))
        self.accept = self.create_action(definition.get('accept'))

    def create_action(self, definition):
        if not definition:
            return None
        if callable(definition):
            return definition
        template = definition.get('template')
        params = definition.get('params') or None
        if hasattr(Templates, template):
            fn = getattr(Templates, template)
        else:
            raise ValueError('Template %s not found, create a static method Templates.%s' % (template))
        
        return fn(**params)

    def get_intent_transition(self, intent):
        for key,state_name in self.intent_transitions.items():
            if re.match(key, intent): return state_name
        return None

    def __str__(self):
        return self.name + ":state"

    def __repr__(self):
        return str(self)
