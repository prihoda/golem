
class Templates:
    @staticmethod
    def message(text, next=None):
        def action(state):
            return text, next
        return action
    
    @staticmethod
    def input(entity, missing_message=None, max_age=0, next=None):
        def action(state):
            value = state.dialog.context.get(entity, max_age=max_age)
            if not value:
                return missing_message, None
            return None, next
        return action

    @staticmethod
    def value_transition(entity, transitions, missing_transition=None, next=None):
        def action(state):
            value = state.dialog.context.get(entity)
            if not value:
                return None, missing_transition
            if value in transitions.keys():
                return None, transitions[value]
            return None, next
        return action

        