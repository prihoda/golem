import pickle

import keras.layers as L
import numpy as np
import os
import re
from keras.callbacks import EarlyStopping
from keras.models import Sequential, load_model
from sklearn.preprocessing import LabelBinarizer
from sklearn.utils import shuffle

from golem.nlp import cleanup


class BowModel:
    def __init__(self, entity, base_dir, is_training=False):
        if not base_dir or not entity:
            raise ValueError('Base dir and entity name must be set')
        self.base_dir = base_dir
        self.entity = entity
        self.stopwords = {"i", "you", "do", "?", "!", ".", ","}

        if not is_training:
            self.load_model()

    def init_model(self):
        self.model = Sequential()
        self.model.add(L.Dense(512, input_dim=len(self.vocab)))
        self.model.add(L.Activation('relu'))
        self.model.add(L.Dense(len(self.labels) * 5))
        self.model.add(L.Activation('relu'))
        self.model.add(L.Dense(len(self.labels)))
        self.model.add(L.Activation('softmax'))
        self.model.compile(
            loss='categorical_crossentropy',  # TODO or crossentropy :-P
            optimizer='sgd',
            metrics=['accuracy']
        )

    def create_vocab(self, sentences):
        vocab = set()
        for list_ in sentences:
            for sent in list_:
                tokens = cleanup.tokenize(sent)
                vocab = vocab.union(tokens)
        vocab = vocab.difference(self.stopwords)
        vocab.add("[NUM]")
        return list(vocab)

    def load_model(self):
        with open(os.path.join(self.base_dir, self.entity, "vocab.pkl"), "rb") as f:
            self.vocab, self.labels, self.onehot = pickle.load(f)
        self.model = load_model(os.path.join(self.base_dir, self.entity, "model.h5"))
        # self.init_model(len(self.vocab))

    def encode_sentence(self, sentence):
        bow = [0.] * len(self.vocab)
        tokens = cleanup.tokenize(sentence)
        for token in tokens:
            if re.match("[0-9]+", token):
              bow[self.vocab.index("[NUM]")] = 1.0
            elif token in self.vocab:
                bow[self.vocab.index(token)] = 1.0
            else:
                print("Not in vocab")
        # print(bow)
        return bow

    def train(self, data):
        print("Training BOW model ...")
        self.labels = list(set([x['value'] for x in data]))

        if "none" not in self.labels:
            # negative samples (this is a hack)
            self.labels.insert(0, "none")

        sentences = dict((x['value'], x['samples']) for x in data)
        sentences.setdefault(None, []).append([])

        self.vocab = self.create_vocab(sentences.values())
        print("Vocabulary: ", self.vocab)

        self.init_model()
        x, y = [], []

        for value, samples in sentences.items():
            if value is None:
                value = 'none'
            for sample in samples:
                x.append(self.encode_sentence(sample))
                y.append(value)

        for _ in range(10):
            # close your eyes please
            x.append([0] * len(self.vocab))
            y.append('none')

        x, y = shuffle(x, y)

        self.onehot = LabelBinarizer()
        self.onehot.fit(self.labels)

        self.model.fit(
            np.array(x), self.onehot.transform(y),
            epochs=1000, batch_size=32,
            callbacks=[
                EarlyStopping(monitor='loss', min_delta=0.00001, verbose=1),
            ]
        )
        print("Saving model ...")
        self.model.save(os.path.join(self.base_dir, self.entity, "model.h5"))
        with open(os.path.join(self.base_dir, self.entity, "vocab.pkl"), "wb") as f:
            pickle.dump((self.vocab, self.labels, self.onehot), f)
        print("Done.")

    def predict(self, utterance, threshold=0.7):
        x = self.encode_sentence(utterance)
        pred = self.model.predict(np.array([x]), batch_size=1)
        return self.onehot.inverse_transform(pred, threshold=threshold)[0]
