# TODO https://stackoverflow.com/questions/10572603/specifying-optional-dependencies-in-pypi-python-setup-py
import json
import os
import pickle

import numpy as np

from golem.nlp import cleanup
from golem.nlp import utils
from golem.nlp.keywords import prepare_keywords
from golem.nlp.model import Model

nlp = utils.get_spacy()


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
            # tokens = [str(x).lower() for x in nlp(sample)]
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
    x, y = [], []

    for doc in documents:
        pattern_words, value = doc
        labels = [0] * len(classes)
        labels[classes.index(value)] = 1
        features = [np.zeros(dim) for i in range(10)]
        for idx, word in enumerate(pattern_words):
            vector = glove.get_vector(word.lower())
            if vector is not None and idx < 10:
                features[idx] = vector * 1000
            else:
                print('Unknown word {} !!! Skipping !!!'.format(word))
        if len(features):
            x.append(features)
            y.append(labels)
        else:
            print('All words of sentence are unknown, skipping!')
            print('Sentence: {}'.format(doc))

    # append gibberish against false positives
    # there is still a tiny chance we'll hit a valid word
    # for i in range(10):
    #     x.append([np.random.random(dim) for i in range(10)])
    #     y.append(([0] * len(classes)))

    return x, y  # TODO shuffle data


def train_entity(x, y, entity_name, entity_dir):
    """
    Trains a model for recognizing entity based on x, y.
    """
    model = Model(entity_name, entity_dir)
    model.train(x, y)
    model.destroy()


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
                words, documents, classes = process(samples)
                x, y = make_tensors(words, documents, classes)
                entity_dir = os.path.join(utils.data_dir(), 'model', entity)
                train_entity(x, y, entity, entity_dir)
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
            else:
                print("Unknown training strategy {} for entity {}, skipping!".format(strategy, entity))

    print("All entities trained!")
