import json

import os
from django.db import models

strategies = ["trait", "keywords"]
languages = ["en", "cz"]


class Entity:  # (models.Model):
    name = models.CharField(max_length=100)
    strategy = models.CharField(max_length=100, choices=strategies)
    stemming = models.BooleanField(default=False)
    language = models.CharField(max_length=10, choices=languages, default="en")
    threshold = models.FloatField(default=0.7)

    @staticmethod
    def fromFile(path):
        with open(path) as f:
            data = json.load(f)  # type: dict
        filename = os.path.split(path)[-1]
        name, ext = os.path.splitext(filename)
        e = Entity()
        e.name = name
        e.strategy = data["strategy"]
        e.stemming = data.get("stemming", False)
        e.language = data.get("language", "en")
        e.threshold = data.get("threshold", 0.7)
        values = data.get("data", [])
        e.values = []
        for value in values:
            v = EntityValue()
            v.name = value.get('label', value.get('value'))
            e.values.append(v)
        return e

    def get_values(self):
        if hasattr(self, 'values'):
            return self.values
        return []

    def __str__(self):
        return self.name


class EntityValue:  # (models.Model):
    name = models.CharField(max_length=100)
