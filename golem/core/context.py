import time

from golem.core.entities import Entity


class Context(object):

    # inside class context on purpose!
    class Query:
        def __init__(self, context, key, candidates):
            self.context = context
            self.key = key
            self.candidates = candidates or []

        def last(self):
            return self.candidates[0].value if self.candidates else None

        def first(self):
            return self.candidates[-1].value if self.candidates else None

        def all(self):
            return self.candidates

        def get(self):
            newest = self.candidates[0] if self.candidates else None
            if newest and newest.get_age(self.context.counter) == 0:
                return newest.value
            return None

        def count(self):
            return len(self.candidates)

        def __nonzero__(self):
            return self.count() > 0

        def _age_filter(self, min=None, max=None):
            now = self.context.counter
            self.candidates = list(filter(
                lambda x: (min is None or min <= x.get_age(now)) and (max is None or x.get_age(now) <= max),
                self.candidates
            ))

        def where(self, **kwargs):
            for k, v in kwargs.items():
                property, operation = k.rsplit('__', maxsplit=1)
                if property == "age":
                    v = int(v)
                    if operation == "lt":
                        self._age_filter(max=v-1)
                    elif operation == "lte":
                        self._age_filter(max=v)
                    elif operation == "eq":
                        self._age_filter(min=v, max=v)
                    elif operation == "gte":
                        self._age_filter(min=v)
                    elif operation == "gt":
                        self._age_filter(min=v+1)
                else:
                    raise NotImplementedError()

            return self

    class MockQuery(Query):
        pass  # TODO for testing

    def __init__(self, dialog, entities, history, counter, max_depth=30, history_restart_minutes=30):
        self.counter = counter
        self.entities = entities
        self.history = history
        self.max_depth = max_depth
        self.dialog = dialog
        self.history_restart_minutes = history_restart_minutes

    def __getattr__(self, item):
        if item in ['counter', 'entities', 'history', 'max_depth', 'dialog', 'history_restart_minutes']:
            return super.__getattribute__(super, item)
        return Context.Query(self, item, self.entities.get(item))

    def __contains__(self, entity):
        return entity in self.entities

    def to_dict(self):
        return {
            'history': self.history,
            'entities': self.entities,
            'counter': self.counter,
        }

    @staticmethod
    def from_dict(dialog, data):
        history = data.get("history", [])
        counter = int(data.get("counter", 0))
        entities = data.get("entities", {})
        return Context(dialog=dialog, entities=entities, history=history, counter=counter)

    def add_entities(self, new_entities):
        if new_entities is None:
            return {}

        current_state = self.get_history_state(0)
        # add all new entities
        for entity_name, values in new_entities.items():
            # allow also direct passing of {'entity' : 'value'}
            if not isinstance(values, dict) and not isinstance(values, list):
                values = {'value': values}
            if not isinstance(values, list):
                values = [values]
            
            # prepend each value to start of the list with 0 age
            for value in values:
                # FIXME use a factory to build the correct subclass with right arguments
                entity = Entity(
                    name=entity_name,
                    value=value.get('value'),
                    raw=value,
                    counter=self.counter,
                    scope=None,
                    state=current_state,
                    )
                self.entities.setdefault(entity_name, []).insert(0, entity)
        self.debug()
        return new_entities

    def add_state(self, state_name):
        timestamp = int(time.time())
        if len(self.history) > 20:
            self.history = self.history[-20:]

        state = {
            'name': state_name,
            'timestamp': timestamp
        }
        self.history.append(state)

    def clear(self, entities):
        for entity in entities:
            if entity in self.entities:
                del self.entities[entity]

    def get_min_entity_age(self, entities):
        ages = [self.get_age(entity)[1] for entity in entities]
        ages = filter(lambda x: x is not None, ages)
        return min(ages) if ages else None

    def get_history_state(self, index):
        return self.history[index] if len(self.history) > abs(index) else None

    def get_all(self, entity, max_age=None, limit=None, ignored_values=tuple()) -> list:
        values = []
        if entity not in self.entities:
            return values
        for entity_obj in self.entities[entity]: # type: Entity
            age = entity_obj.get_age(self.counter)
            # if I found a too old value, stop looking
            if max_age is not None and age > max_age:
                break
            v = entity_obj.value
            if v in ignored_values:
                self.dialog.log.info('Skipping ignored entity value: {} == {}'.format(entity, v))
                continue

            values.append(entity)
            # if I already have enough values, stop looking
            if limit is not None and len(values) >= limit:
                break
        return values
    
    def debug(self, max_age=5):
        self.dialog.log.info('-- HEAD of Context (max age {}): --'.format(max_age))
        for entity in self.entities:
            entities = self.get_all_first(entity, max_age=max_age)
            if entities:
                vs = [entity.value for entity in entities]
                self.dialog.log.info('{} (age {}): {}'.format(entity, entities[0].get_age(self.counter), vs if len(vs) > 1 else vs[0]))
        self.dialog.log.info('----------------------------------')

    def get(self, entity, max_age=None, ignored_values=tuple()) -> Entity or None:
        values = self.get_all(entity, max_age=max_age, limit=1, ignored_values=ignored_values)
        if not values:
            return None
        return values[0]

    def get_value(self, entity, max_age=None, ignored_values=tuple()) -> object:
        values = self.get_all(entity, max_age, ignored_values)
        if not values:
            return None
        return values[0].value

    def get_age(self, entity, max_age=None, ignored_values=tuple()):
        ents = self.get_all(entity, max_age=max_age, limit=1, ignored_values=ignored_values)
        if not ents:
            return None, None
        return ents[0], ents[0].get_age(self.counter)

    def get_all_first(self, entity_name, max_age=None):
        values = []
        if entity_name not in self.entities:
            return values
        found_age = None
        existing = []
        for entity_obj in self.entities[entity_name]:  # type: Entity
            age = entity_obj.get_age(self.counter)
            # if I found a too old value, stop looking
            if max_age is not None and age > max_age:
                break
            if found_age is not None and age > found_age:
                break
            found_age = age
            if entity_obj.value in existing:
                # skip duplicates
                continue
            existing.append(entity_obj.value)
            values.append(entity_obj)
        return values[::-1]

    def set(self, entity, value_dict):
        if not isinstance(value_dict, dict):
            raise ValueError('Use a dict to set a context value, e.g. {"value":"foo"}. Call multiple times to add more.')
        if entity not in self.entities:
            self.entities[entity] = []
        value_dict['counter'] = self.counter
        self.entities[entity] = [value_dict] + self.entities[entity][:self.max_depth-1]

    def set_value(self, entity_name, value):
        if entity_name not in self.entities:
            self.entities[entity_name] = []
        entity_obj = Entity(
            name=entity_name,
            value=value,
            raw={"value": value},
            counter=self.counter
        )
        self.entities[entity_name].insert(0, entity_obj)
        self.entities[entity_name] = self.entities[entity_name][:self.max_depth - 1]

    def has_any(self, entities, max_age=None):
        for entity in entities:
            if self.get(entity, max_age=max_age):
                return True
        return False

    def has_all(self, entities, max_age=None):
        for entity in entities:
            if not self.get(entity, max_age=max_age):
                return False
        return True
