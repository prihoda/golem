import re
from .templates import Templates

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

def require_one_of(entities=[]):
    def decorator_wrapper(func):
        def func_wrapper(state):
            all_entities = entities + ['intent','_state']
            if not state.dialog.context.has_any(all_entities, max_age=0):
                print('No required entities present, moving to default.root: {}'.format(all_entities))
                return None, 'default.root:accept'
            return func(state)
        return func_wrapper
    return decorator_wrapper