import json

import os
from typing import List

import logging
from django.conf import settings

from core.nlp import cleanup
from core.nlp.data_model import Entity


def get_entity_names() -> List:
    training_dir = os.path.join(data_dir(), 'training_data')
    entities = []
    for f in os.scandir(training_dir):
        name, ext = os.path.splitext(f.name)
        if f.is_file() and ext == '.json':
            entities.append(Entity.fromFile(training_dir + '/' + f.name))
            # entities.append((name, f))
    return entities


_glove = None
_nlp = None


def get_glove():
    from core.nlp.glove import GloVe
    global _glove
    if _glove is None:
        glove_dir = settings.NLP_CONFIG.get('GLOVE_DIR')
        glove_prefix = settings.NLP_CONFIG.get('GLOVE_PREFIX')
        if glove_dir is None or glove_prefix is None:
            raise Exception('Please set django settings NLP_CONFIG.GLOVE_DIR and GLOVE_PREFIX to point '
                            'to your word embedding files to use the built-in NLP.')
        logging.debug('Using word embeddings at {} with prefix'.format(glove_dir, glove_prefix))
        _glove = GloVe(glove_dir, glove_prefix)
    return _glove


def data_dir():
    return settings.NLP_CONFIG.get("DATA_DIR", "data/nlp")


def get_default_language():
    return settings.NLP_CONFIG.get('LANGUAGE', 'en')


def get_training_data(entity):
    path = os.path.join(data_dir(), "training_data", entity + ".json")
    with open(path) as f:
        data = json.load(f)
    return data


def get_imputation_rules(entity):
    data = get_training_data(entity)
    imputation = data.get('imputation', [])
    return cleanup.build_imputation_rules(imputation)
