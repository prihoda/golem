import json
import logging
import time

import os
from django.conf import settings

from golem.core.chat_session import ChatSession
from golem.core.responses import LinkButton
from golem.core.responses.responses import TextMessage
from golem.tasks import accept_inactivity_callback, accept_schedule_callback
from .context import Context
from .flow import load_flows_from_definitions
from .logger import MessageLogging
from .persistence import get_redis
from .serialize import json_deserialize, json_serialize
from .tests import ConversationTestRecorder


class DialogManager:
    version = '1.34'

    def __init__(self, session: ChatSession):
        self.session = session
        self.uid = session.chat_id  # for backwards compatibility
        self.logger = MessageLogging(self)
        self.db = get_redis()
        self.log = logging.getLogger()
        self.context = None  # type: Context

        self.should_log_messages = settings.GOLEM_CONFIG.get('SHOULD_LOG_MESSAGES', False)
        self.error_message_text = settings.GOLEM_CONFIG.get('ERROR_MESSAGE_TEXT')

        context_dict = {}
        version = self.db.get('dialog_version')
        self.log.info('Initializing dialog for chat %s...' % session.chat_id)
        self.current_state_name = None
        self.init_flows()

        if version and version.decode('utf-8') == DialogManager.version and \
                self.db.hexists('session_context', self.session.chat_id):

            state = self.db.hget('session_state', self.session.chat_id).decode('utf-8')
            self.log.info('Session exists at state %s' % state)

            if not state:
                logging.error("State was NULL, sending user to default.root!")
                state = 'default.root'
            elif state.endswith(':'):
                state = state[:-1]  # to avoid infinite loop

            self.move_to(state, initializing=True)
            # self.log.info(entities_string)
            context_string = self.db.hget('session_context', self.session.chat_id)
            context_dict = json.loads(context_string.decode('utf-8'), object_hook=json_deserialize)
        else:
            self.current_state_name = 'default.root'
            self.log.info('Creating new session...')
            self.logger.log_user(self.session)


        self.context = Context.from_dict(dialog=self, data=context_dict)  # type: Context

    def init_flows(self):
        flow_definitions = self.create_flows()
        self.flows = load_flows_from_definitions(flow_definitions)
        self.current_state_name = 'default.root'

    def create_flows(self):
        import yaml
        flows = {}  # a dict with all the flows loaded from YAML
        BOTS = settings.GOLEM_CONFIG.get('BOTS', [])
        for filename in BOTS:
            try:
                with open(os.path.join(settings.BASE_DIR, filename)) as f:
                    file_flows = yaml.load(f)
                    for flow in file_flows:
                        if flow in flows:
                            raise Exception("Error: duplicate flow {}".format(flow))
                        flows[flow] = file_flows[flow]
                        flows[flow]['relpath'] = os.path.dirname(filename)  # directory of relative imports
            except OSError as e:
                raise ValueError("Unable to open definition {}".format(filename)) from e
        return flows

    @staticmethod
    def clear_chat(chat_id):
        db = get_redis()
        db.hdel('session_state', chat_id)
        db.hdel('session_context', chat_id)

    def move_by_entities(self, entities):
        self.log.warning("Not accepted, moving to default.root!")
        self.move_to('default.root:accept')
        # TODO instead of this, first check for states in this flow that accept the entity
        # TODO then check for states in default flow OR check for flows that accept it

    def process(self, message_type, entities):
        self.session.interface.processing_start(self.session)
        accepted_time = time.time()
        accepted_state = self.current_state_name
        # Only process messages and postbacks (not 'seen_by's, etc)
        if message_type not in ['message', 'postback', 'schedule']:
            return

        self.log.info('-- USER message ----------------------------------')

        # if message_type != 'schedule':
        # TODO don't increment when @ requires -> input and it's valid
        # TODO what to say and do on invalid requires -> input?
        self.context.counter += 1

        entities = self.context.add_entities(entities)

        if self.test_record_message(message_type, entities):
            return
        elif self.special_message(message_type, entities):
            return


        if message_type != 'schedule':
            self.save_inactivity_callback()

        self.log.info('++ PROCESSING ++++++++++++++++++++++++++++++++++++')

        if not self.check_state_transition() \
            and not self.check_intent_transition(entities) \
            and not self.check_entity_transition(entities):
                self.run_accept(save_identical=True)
                self.save_state()

                # FIXME remove this or integrate with check_entity_transition and new "unsupported" states
                # TODO should "unsupported" be states or just actions?

                # _TODO somebody might want _message_text and intent locked for freetext/human
                # acceptable_entities = list(filter(lambda e: e.startswith("_"), entities.keys()))
                # blame the dialog designer for bad postbacks ... but it's a good idea to prefix special entities with _
                #if message_type != 'message' or self.get_flow().accepts_message(acceptable_entities):  # _FIXME this won't work
                #    if self.get_state().is_temporary:
                #        # execute default action _TODO stay here, like fake root
                #        self.move_by_entities(entities)
                #        self.save_state()
                #    else:
                #        self.run_accept(save_identical=True)
                #        self.save_state()
                #else:
                #    self.log.debug("Unsupported entity, moving to default.root")
                #    self.move_by_entities(entities)
                #    self.save_state()

        self.session.interface.processing_end(self.session)

        # leave logging message to the end so that the user does not wait
        self.logger.log_user_message(message_type, entities, accepted_time, accepted_state)

    def schedule(self, callback_name, at=None, seconds=None):
        self.log.info('Scheduling callback "{}": at {} / seconds: {}'.format(callback_name, at, seconds))
        if at:
            if at.tzinfo is None or at.tzinfo.utcoffset(at) is None:
                raise Exception('Use datetime with timezone, e.g. "from django.utils import timezone"')
            accept_schedule_callback.apply_async((self.session.to_json(), callback_name), eta=at)
        elif seconds:
            accept_schedule_callback.apply_async((self.session.to_json(), callback_name), countdown=seconds)
        else:
            raise Exception('Specify either "at" or "seconds" parameter')

    def inactive(self, callback_name, seconds):
        self.log.info('Setting inactivity callback "{}" after {} seconds'.format(callback_name, seconds))
        accept_inactivity_callback.apply_async(
            (self.session.to_json(), self.context.counter, callback_name, seconds),
            countdown=seconds)

    def save_inactivity_callback(self):
        self.db.hset('session_active', self.session.chat_id, time.time())
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
            if record.value == 'start':
                self.send_response(ConversationTestRecorder.record_start())
            elif record.value == 'stop':
                self.send_response(ConversationTestRecorder.record_stop())
            else:
                self.send_response("Use /test_record/start/ or /test_record/stop/")
            self.save_state()
            return True
        if record == 'start':
            ConversationTestRecorder.record_user_message(message_type, entities)
            self.recording = True
        return False

    def special_message(self, type, entities):
        text = entities.get("_message_text")
        if not isinstance(text, str):
            return False
        elif text == '/areyougolem':
            self.send_response("Golem Framework Dialog Manager v{}".format(self.version))
            return True
        elif text.startswith('/intent/'):
            intent = text.replace('/intent/', '', count=1)
            self.context.set_value("intent", intent)
            return True
        return False

    def run_accept(self, save_identical=False):
        state = self.get_state()
        if self.current_state_name != 'default.root' and not state.check_requirements(self.context):
            # TODO should they be checked when moving or always?
            # TODO i would go with always as the user's code might depend on the entities being non-null
            requirement = state.get_first_requirement(self.context)
            # run the requirement
            retval = requirement.action(dialog=self)
            # send a response if given in return value
            if isinstance(retval, tuple):
                msg, next = retval
                self.send_response(msg, next)
        else:
            if not state.action:
                self.log.warning('State does not have an action.')
                return
            # run the action
            retval = state.action(dialog=self)
            # send a response if given in return value
            if isinstance(retval, tuple):
                msg, next = retval
                self.send_response(msg, next)

    def check_state_transition(self):
        new_state_name = self.context._state.current_v()  #get('_state', max_age=0)
        return self.move_to(new_state_name)

    def check_intent_transition(self, entities: dict):

        intent = self.context.intent.current_v()
        if not intent:
            return False

        if self.get_state().is_supported(entities.keys()):
            return False

        # FIXME Get custom intent transition
        new_state_name = None # self.get_state().get_intent_transition(intent)
        # If no custom intent transition present, move to the flow whose 'intent' field matches intent
        # Check accepted intent of the current flow's states
        if not new_state_name:
            flow = self.get_flow()
            new_state_name = flow.get_state_for_intent(intent)

        # Check accepted intent of all flows
        if not new_state_name:
            for flow in self.flows.values():
                if flow.matches_intent(intent):
                    new_state_name = flow.name + '.root'
                    break

        if not new_state_name:
            self.log.error('Error! Found intent "%s" but no flow present for it!' % intent)
            return False

        # new_state_name = new_state_name + ':accept'
        self.log.info('Moving based on intent %s...' % intent)
        return self.move_to(new_state_name + ":")  # : runs the action

    def check_entity_transition(self, entities: dict):
        # TODO first check if supported, if yes, abort
        # TODO then check if there is a flow that would accept the entity, if not ...
        # AND THEN? a) default.root don't understand b) remain in the same state
        # I'd say don't understand but still keep tuned for the entity in default.root (temporary root)
        # Even better: move to special (configurable) unsupported state that will be temporary too
        return False

    def get_flow(self, flow_name=None):
        if not flow_name:
            flow_name, _ = self.current_state_name.split('.', 1)
        return self.flows.get(flow_name)

    def get_state(self, flow_state_name=None):
        flow_name, state_name = (flow_state_name or self.current_state_name).split('.', 1)
        flow = self.get_flow(flow_name)
        return flow.get_state(state_name) if flow else None

    def move_to(self, new_state_name, initializing=False, save_identical=False):

        # TODO just run action without moving if the state is temporary

        # if flow prefix is not present, add the current one
        if isinstance(new_state_name, int):
            new_state = self.context.get_history_state(new_state_name - 1)
            new_state_name = new_state['name'] if new_state else None
        if not new_state_name:
            new_state_name = self.current_state_name

        if new_state_name.count(':'):
            new_state_name, action = new_state_name.split(':', 1)
            action = True
        else:
            action = False

        if ('.' not in new_state_name):
            new_state_name = self.current_state_name.split('.')[0] + '.' + new_state_name
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
            self.session.interface.state_change(self.current_state_name)
            # record change if recording tests
            if self.recording:
                ConversationTestRecorder.record_state_change(self.current_state_name)

            try:
                if previous_state != new_state_name and action:
                    logging.info("Moving from {} to {} and executing action".format(
                        previous_state, new_state_name
                    ))
                    self.run_accept()

            except Exception as e:
                logging.error('*****************************************************')
                logging.error('Exception occurred while running action {} of state {}'
                              .format(action, new_state_name))
                logging.error('Chat id: {}'.format(self.session.chat_id))
                try:
                    context_debug = self.get_state().dialog.context.debug()
                    logging.error('Context: {}'.format(context_debug))
                except:
                    pass
                logging.exception('Exception follows')
                if self.error_message_text:
                    self.send_response([self.error_message_text])

                # Raise the error if we are in a test
                if self.session.is_test:
                    raise e

        self.save_state()
        return True

    def save_state(self):
        if not self.context:
            return
        self.log.info('Saving state at %s' % (self.current_state_name))
        self.db.hset('session_state', self.session.chat_id, self.current_state_name)
        context_json = json.dumps(self.context.to_dict(), default=json_serialize)
        self.db.hset('session_context', self.session.chat_id, context_json)
        self.db.hset('session_interface', self.session.chat_id, self.session.interface.name)
        self.db.set('dialog_version', DialogManager.version)

        # save chat session to redis, TODO
        session = json.dumps(self.session.to_json())
        self.db.hset("chat_session", self.session.chat_id, session)

    def send_response(self, responses, next=None):
        if not responses:
            return
        self.log.info('-- CHATBOT message -------------------------------')

        if not (isinstance(responses, list) or isinstance(responses, tuple)):
            return self.send_response([responses], next)

        for response in responses:
            if isinstance(response, str):
                response = TextMessage(text=response)

            # Send the response
            self.session.interface.post_message(self.session, response)

            # Record if recording
            if self.recording:
                ConversationTestRecorder.record_bot_message(response)

        for response in responses:
            # Log the response
            #self.log.info('Message: {}'.format(response))
            self.logger.log_bot_message(response, self.current_state_name)

            # text = response.text if hasattr(response, 'text') else (response if isinstance(response, str) else None)
            # if text and self.should_log_messages:
            #     message_logger.on_message.delay(self.session, text, self, from_user=False)

        if next is not None:
            self.move_to(next)  # TODO we can either have ':init' or a bool parameter

    def dont_understand(self):
        # TODO log to chatbase
        # TODO work in progress
        from golem.core.parsing import golem_extractor
        utterance = self.context.get("_message_text", max_age=0)
        nlu = golem_extractor.GOLEM_NLU
        if not nlu or not utterance:
            print("NLU instance and message text can't be None")
            return
        intent = nlu.parse_entity(utterance, 'intent', threshold=0.5)
        if intent:
            text = "I'm not sure what you mean. Are you talking about \"{}\"?".format(intent[0]['value'])
            message = TextMessage(text).with_replies(['Yes', 'No'])
            self.send_response(message)
        else:
            text = "I'm not sure what you mean. Could you help me learn?"
            message = TextMessage(text).add_button(LinkButton("WebView", "http://zilinec.me/intent.html"))
            self.send_response(message)
            # TODO webview
