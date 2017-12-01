import os
from typing import List

import logging
import spacy
from django.conf import settings

from golem.nlp.data_model import Entity
from golem.nlp.glove import GloVe


def get_entity_names() -> List:
    training_dir = os.path.join(os.environ.get('NLP_DATA_DIR'), 'training_data')
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
    global _glove
    if _glove is None:
        glove_dir = os.environ.get('GLOVE_DIR')
        glove_prefix = os.environ.get('GLOVE_PREFIX')
        if glove_dir is None or glove_prefix is None:
            raise Exception('Please set the environment variables GLOVE_DIR and GLOVE_PREFIX to point '
                            'to your word embedding files to use the built-in NLP.')
        logging.debug('Using word embeddings at {} with prefix'.format(glove_dir, glove_prefix))
        _glove = GloVe(glove_dir, glove_prefix)
    return _glove


def get_spacy(language='en'):
    global _nlp
    if not _nlp:
        _nlp = spacy.load(language, disable=['ner'])
    return _nlp


def data_dir():
    return os.environ['NLP_DATA_DIR']


def get_default_language():
    return settings.GOLEM_CONFIG.get('NLP_LANGUAGE', 'en')
