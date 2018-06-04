# TODO https://stackoverflow.com/questions/10572603/specifying-optional-dependencies-in-pypi-python-setup-py
import json
import os
import pickle

import numpy as np
import random

from core.nlp import cleanup
from core.nlp import utils
from core.nlp.keywords import prepare_keywords
from core.nlp.nn.model import Model
from core.nlp.nn.seq2seq import Seq2Seq


def process(entities, imputation_rules):
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
            tokens = cleanup.imputer(tokens, imputation_rules)
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


class Batcher:
    def __init__(self, training, max_words=10):
        self.glove = utils.get_glove()
        self.dim = self.glove.get_dimension()
        self.max_words = max_words
        self.imputation_rules = cleanup.build_imputation_rules(training.get('imputation', []))
        data = training['data']
        self.keep_prob = training.get("dropout", 0.5)
        self.iterations = training.get("iterations", 3000)
        self.labels = [x['value'] for x in data]  # TODO what if some are duplicates?
        self.sentences = dict((x['value'], x['samples']) for x in data)
        self.sentences.setdefault(None, []).append([])
        self.unk = self.glove.get_vector("<unk>")
        if self.unk is None: self.unk = np.zeros([self.dim])
        self.oov = set()
        self.sentences = dict(  # converts sentences to embedded feature vectors
            (k, list(filter(None, [self.process_sentence(sent) for sent in v])))
            for k, v in self.sentences.items()
        )
        # TODO somehow distinguish PAD, END, START, UNK and NIL

        if len(self.oov) > 0:
            print("### [Warning] There are %d out-of-vocabulary words in training data! ###" % len(self.oov))
            print("OOV words: ", sorted(self.oov))

    def process_sentence(self, sentence):
        tokens = cleanup.imputer(cleanup.tokenize(sentence), self.imputation_rules)
        features = np.zeros([self.max_words, self.dim])
        random_positions, has_valid_token = [], False
        for i, token in enumerate(tokens):
            if token == "%":
                random_positions.append(i)
                has_valid_token = True  # well well, but it might get kinda fuzzy ...
            else:
                vec = self.glove.get_vector(token)
                if vec is None:
                    self.oov.add(token)
                    features[i] = self.unk
                else:
                    has_valid_token = True
                    features[i] = vec
        if not has_valid_token:
            print("### [Warning] Sentence \"{}\" has no valid words! Removing! ###".format(sentence))
        return (features, random_positions) if has_valid_token else None

    def next_batch(self, batch_size):
        # ensure proper stratification
        labels = [random.choice(self.labels) for _ in range(batch_size)]
        x, y = [], []
        for i, label in enumerate(labels):
            sentence, positions = random.choice(self.sentences[label])
            for pos in positions:
                sentence[pos] = np.random.random([self.dim])
            x.append(sentence)
            one_hot = [0.] * len(self.labels)
            if label not in [None, 'none', 'None']:
                one_hot[self.labels.index(label)] = 1.0
            y.append(one_hot)
        return x, y


def train_entity(batcher, entity_name, entity_dir, num_iterations):
    """
    Trains a model for recognizing entity based on x, y.
    """
    print("[Training entity {} for {} iterations]".format(entity_name, num_iterations))
    model = Model(entity_name, entity_dir)
    model.train(batcher, batcher.iterations, batcher.keep_prob)
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
                # samples = data['data']
                # imputation = data.get('imputation', [])
                num_iterations = data.get("iterations", 1000)
                # words, documents, classes = process(samples, rules)
                words, documents, classes = [], [], []
                entity_dir = os.path.join(utils.data_dir(), 'model', entity)
                batcher = Batcher(data, max_words=10)
                train_entity(batcher, entity, entity_dir, num_iterations)
                pickle_path = os.path.join(utils.data_dir(), 'model', entity, 'pickle.json')
                pickle.dump({'labels': batcher.labels},
                            open(pickle_path, 'wb'))
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
