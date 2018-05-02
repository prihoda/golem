import pickle

import numpy as np
import keras.layers as L
import os
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

        if not is_training:
            self.load_model()

    def init_model(self):
        # TODO how about hinge and no softmax
        self.model = Sequential()
        self.model.add(L.Dense(512, input_dim=len(self.vocab)))
        self.model.add(L.Activation('relu'))
        self.model.add(L.Dense(512))
        self.model.add(L.Activation('relu'))
        self.model.add(L.Dense(len(self.labels)))
        self.model.add(L.Activation('softmax'))
        self.model.compile(
            loss='categorical_crossentropy',
            optimizer='sgd',
            metrics=['accuracy']
        )

    def create_vocab(self, sentences):
        vocab = set()
        for list_ in sentences:
            for sent in list_:
                tokens = cleanup.tokenize(sent)
                vocab = vocab.union(tokens)
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
            if token in self.vocab:
                bow[self.vocab.index(token)] += 1.0
            else:
                print("Not in vocab")
        return bow

    def train(self, data):
        print("Training BOW model ...")
        self.labels = list(set([x['value'] for x in data]))
        sentences = dict((x['value'], x['samples']) for x in data)
        sentences.setdefault(None, []).append([])

        self.vocab = self.create_vocab(sentences.values())
        print("Vocabulary: ", self.vocab)

        self.init_model()
        x, y = [], []

        for value, samples in sentences.items():
            if value is None: continue
            for sample in samples:
                x.append(self.encode_sentence(sample))
                y.append(value)

        x, y = shuffle(x, y)

        self.onehot = LabelBinarizer()
        self.onehot.fit(self.labels)

        self.model.fit(
            np.array(x), self.onehot.transform(y),
            epochs=1000, batch_size=32,
            callbacks=[
                EarlyStopping(monitor='loss', min_delta=0.001, verbose=1),
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