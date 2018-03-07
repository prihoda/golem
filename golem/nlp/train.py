# TODO https://stackoverflow.com/questions/10572603/specifying-optional-dependencies-in-pypi-python-setup-py
import json
import os
import pickle

import numpy as np
import random

from golem.nlp import cleanup
from golem.nlp import utils
from golem.nlp.keywords import prepare_keywords
from golem.nlp.nn.model import Model
from golem.nlp.nn.seq2seq import Seq2Seq


def process(entities):
    """
    Processes entities to stemmed words with SpaCy.
    :returns:   tuple of words, documents, classes
    """

    ignore_words = ['?', '.', '!']
    words = []
    documents = []
    classes = []

    for entity in entities:
        # specific entity value with samples
        value = entity['value']

        if value not in classes:
            classes.append(value)

        for sample in entity['samples']:
            # a text pattern
            tokens = cleanup.tokenize(sample)
            words.extend(tokens)
            documents.append((tokens, value))

    words = sorted(list(set(words)))
    words = [w for w in words if w not in ignore_words]

    print(len(documents), 'documents')
    print(len(classes), 'classes')
    print(len(words), 'words', words)

    classes.append('none')
    documents.append(([], 'none'))  # empty sentence to prevent bias @ [0]

    return words, documents, classes


def make_tensors(words, documents, classes):
    """
    Processes words into tensors for model training.
    :returns:   tuple of x, y
    """
    glove = utils.get_glove()
    dim = glove.get_dimension()
    x, y, junk = [], [], []

    for doc in documents:
        pattern_words, value = doc
        labels = [0] * len(classes)
        if value is not None and value.lower() != 'none':
            labels[classes.index(value)] = 1

        features = [np.zeros(dim) for i in range(10)]
        for idx, word in enumerate(pattern_words):
            junks = []
            start_char = -1
            for i in range(word.count('%')):
                start_char = word.index("%", start_char + 1)
                junks.append(start_char)
            junk.append(junks)
            vector = glove.get_vector(word.lower())
            if vector is not None and idx < 10:
                features[idx] = vector
            else:
                print('Unknown word in training data: {} !!!'.format(word))
                # raise ValueError()
        if len(features):
            x.append(features)
            y.append(labels)
        else:
            print('All words of sentence are unknown, skipping!')
            print('Sentence: {}'.format(doc))

    return x, y, junk


def train_entity(x, y, junk, entity_name, entity_dir, num_iterations):
    """
    Trains a model for recognizing entity based on x, y.
    """
    print("[Training entity {} for {} iterations]".format(entity_name, num_iterations))
    model = Model(entity_name, entity_dir)
    model.train(x, y, junk, num_iterations)
    model.destroy()


def trashify(x):
    """Replace all wildcards in text by random trash words."""
    glove = utils.get_glove()
    while '%' in x:
        junk = None
        while not junk or '%' in junk:
            junk = glove.random_word()
        x = x.replace('%', junk, 1)
    return x


def train_all(included=None):
    """
    Trains all entity values from their JSON descriptions.
    See ./data/training_data/*.json
    """
    train_dir = os.path.join(utils.data_dir(), 'training_data')
    entities = []
    for f in os.scandir(train_dir):
        name, ext = os.path.splitext(f.name)
        if f.is_file() and ext == '.json':
            entities.append((name, f))

    for entity, filename in entities:
        if included and entity not in included:
            continue
        print('Training', entity)
        with open(filename) as f:
            data = json.load(f)
            entity_dir = os.path.join(utils.data_dir(), 'model', entity)
            if not os.path.exists(entity_dir):
                os.makedirs(entity_dir)

            strategy = data['strategy']
            with open(os.path.join(entity_dir, 'metadata.json'), 'w') as g:
                metadata = {'strategy': strategy}
                if strategy == 'trait':
                    metadata['threshold'] = data.get('threshold', 0.5)
                if strategy == 'keywords':
                    # metadata['ngrams'] = data.get('ngrams', 3)
                    metadata['stemming'] = data.get('stemming', False)
                    metadata['language'] = data.get('language', utils.get_default_language())
                json.dump(metadata, g)

            if strategy == 'trait':
                # train as neural network
                samples = data['data']
                num_iterations = data.get("iterations", 1000)
                words, documents, classes = process(samples)
                x, y, junk = make_tensors(words, documents, classes)
                entity_dir = os.path.join(utils.data_dir(), 'model', entity)
                train_entity(x, y, junk, entity, entity_dir, num_iterations)
                pickle_path = os.path.join(utils.data_dir(), 'model', entity, 'pickle.json')
                pickle.dump({'words': words, 'documents': documents, 'classes': classes,
                             'x': x, 'y': y}, open(pickle_path, 'wb'))
            elif strategy == 'keywords':
                # train as a list of fixed values (fuzzy matching)
                samples = data['data']
                should_stem = data.get('stemming', False)
                language = data.get('language', utils.get_default_language())
                trie = prepare_keywords(samples, should_stem, language)

                with open(os.path.join(entity_dir, 'trie.json'), 'w') as g:
                    json.dump(trie, g)
            elif strategy == 'seq2seq':
                samples = data['data'].items()
                x, y = [x for x, y in samples], [y for x, y in samples]
                model = Seq2Seq(entity, entity_dir)
                model.train(x, y)
                model.destroy()
            else:
                print("Unknown training strategy {} for entity {}, skipping!".format(strategy, entity))

    print("All entities trained!")
