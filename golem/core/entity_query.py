import re
import time


class EntityQuery:
    def __init__(self, context, name, items):
        self.context = context
        self.name = name
        self.items = items

    # TODO filter by roles

    def newer_than(self, messages=None, delta=None, abs_time=None):
        """
        Filter to all entities that are newer than ...
        :param messages
        :param delta
        :param abs_time
        :return: self
        """
        if (messages and (delta or abs_time)) or (delta and abs_time):
            raise ValueError("Please use either message count, timedelta or absolute time")
        if messages:
            counter_now = self.context.counter
            self.items = filter(lambda x: counter_now - x.counter < messages, self.items)
        elif delta:
            time_min = time.time() - delta.total_seconds()
            self.items = filter(lambda x: x.timestamp > time_min, self.items)
        elif abs_time:
            self.items = filter(lambda x: x.timestamp > abs_time, self.items)
        return self

    def older_than(self, messages=None, delta=None, abs_time=None):
        """
        Filter to all entities that are older than ...
        :param messages
        :param delta
        :param abs_time
        :return: self
        """
        if (messages and (delta or abs_time)) or (delta and abs_time):
            raise ValueError("Please use either message count, timedelta or absolute time")
        if messages:
            counter_now = self.context.counter
            self.items = filter(lambda x: counter_now - x.counter > messages, self.items)
        elif delta:
            time_max = time.time() - delta.total_seconds()
            self.items = filter(lambda x: x.timestamp < time_max, self.items)
        elif abs_time:
            self.items = filter(lambda x: x.timestamp < abs_time, self.items)
        return self

    def exactly(self, messages=None, delta=None, abs_time=None):
        """
        Filter to all entities that occurred exactly at ...
        :param messages
        :param delta
        :param abs_time
        :return: self
        """
        if (messages and (delta or abs_time)) or (delta and abs_time):
            raise ValueError("Please use either message count, timedelta or absolute time")
        if messages:
            counter_now = self.context.counter
            self.items = filter(lambda x: counter_now - x.counter == messages, self.items)
        elif delta:
            time_max = time.time() - delta.total_seconds()
            self.items = filter(lambda x: abs(x.timestamp - time_max) < 1.0, self.items)
        elif abs_time:
            self.items = filter(lambda x: abs(x.timestamp - abs_time) < 1.0, self.items)
        return self

    def include_flow(self, regex: str):
        """Include just entities that were set in a state that matches the regex."""
        self.items = filter(lambda x: re.match(regex, x.state_set), self.items)
        return self

    def exclude_flow(self, regex: str):
        """Exclude all entities that were set in a state that matches the regex."""
        self.items = filter(lambda x: re.match(regex, x.state_set) is None, self.items)
        return self

    def latest(self):
        self.items = sorted(self.items, key=lambda x: x.timestamp, reverse=True)
        return self.items[0] if len(self.items) > 0 else None

    def latest_v(self):
        item = self.latest()
        return item.value if item else None

    def current(self):
        item = self.latest()
        return item if item is not None and item.counter == self.context.counter else None

    def current_v(self):
        item = self.current()
        return item.value if item else None

    def all(self):
        return list(self.items)

    def all_v(self):
        return [x.value for x in self.all()]

    def count(self):
        self.items = list(self.items)
        return len(self.items)

    def __nonzero__(self):
        return self.count() > 0


class MockQuery(EntityQuery):
    pass  # TODO for testing
