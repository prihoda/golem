import pickle

import os
from keras.callbacks import EarlyStopping
from keras.layers import *
from keras.models import Sequential, load_model
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import LabelBinarizer
from sklearn.utils import shuffle

from golem.nlp import cleanup


class ContextualModel:
    def __init__(self, entity, base_dir, is_training=False):
        if not base_dir or not entity:
            raise ValueError('Base dir and entity name must be set')

        self.base_dir = base_dir
        self.entity = entity

        if not is_training:
            self._load_model()

    def _save_model(self):
        print("Saving model ...")
        with open(os.path.join(self.base_dir, "vocab.pkl"), "wb") as f:
            pickle.dump((self.vocab, self.labels, self.word_enc, self.label_enc), f)
        self.model.save(os.path.join(self.base_dir, "model.h5"))

    def _load_model(self):
        with open(os.path.join(self.base_dir, "vocab.pkl"), "rb") as f:
            self.vocab, self.labels, self.word_enc, self.label_enc = pickle.load(f)
        self.model = load_model(os.path.join(self.base_dir, "model.h5"))

    def _get_features(self, token, abs_idx, tokens):
        sentence_pos = 0  # abs_idx / len(tokens)  # [0;1]

        lwindow = tokens[max(0, abs_idx - 3): abs_idx]  # yes I know, 3 left, 2 right
        rwindow = tokens[abs_idx + 1: min(len(tokens), abs_idx + 3)]
        lcontext = np.sum(self.word_enc.transform(lwindow), axis=0)
        rcontext = np.sum(self.word_enc.transform(rwindow), axis=0)

        lcontext = np.asarray(lcontext)[0]
        rcontext = np.asarray(rcontext)[0]

        features = np.concatenate([[sentence_pos], lcontext, rcontext])
        #     print("Context:", lcontext, rcontext)

        return features

    def _make_xy(self, training_data):
        x, y = [], []
        for example in training_data:
            tokens = cleanup.tokenize(example[0])
            # take each entity for prediction
            # everything else will be negative samples
            idx = 0
            for abs_idx, token in enumerate(tokens):
                if token == '%':
                    idx += 1
                    label = example[idx]
                else:
                    label = 'none'

                features = self._get_features(token, abs_idx, tokens)
                label_encoded = self.label_enc.transform([label])

                x.append(features)
                y.append(label_encoded[0])

        return np.array(x), np.array(y)

    def train(self, training_data):
        # with open("data/nlp/training_data/context_test.yaml") as f:
        #     training_file = yaml.load(f)
        # training_data = ['data']

        self.vocab = set()
        self.labels = set()

        for example in training_data:
            tokens = cleanup.tokenize(example[0])
            self.vocab = self.vocab.union(tokens)
            self.labels = self.labels.union(example[1:])

        self.labels.add("none")

        self.word_enc = CountVectorizer()
        self.word_enc.fit(self.vocab)

        self.label_enc = LabelBinarizer()
        self.label_enc.fit(list(self.labels))

        print("Vocab:", self.vocab)
        print("Labels:", self.labels)

        x, y = self._make_xy(training_data)

        self.model = Sequential()
        self.model.add(Dense(256, input_shape=[x.shape[1]]))
        self.model.add(Activation('relu'))
        self.model.add(Dense(256))
        self.model.add(Activation('relu'))
        self.model.add(Dense(3))
        self.model.add(Activation('softmax'))

        x, y = shuffle(x, y)

        # TODO (1) try embeddings
        # TODO (2) try RNN, not MLP

        self.model.compile(
            optimizer='adam',
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        self.model.fit(x, y, epochs=1000, callbacks=[EarlyStopping('loss', 0.001)])

        self._save_model()

    def test(self):
        pass  # TODO

    def predict(self, utterance):
        tokens = cleanup.tokenize(utterance)
        results = []
        current_entity = []
        current_label = None
        for idx, token in enumerate(tokens):
            features = self._get_features(token, idx, tokens)
            pred = self.model.predict(np.array([features]))
            label = self.label_enc.inverse_transform(pred)[0]
            if label == 'none':
                label = None

            if label:
                print("{} is {}".format(token, label))

            # TODO is this correct?

            if label and (not current_label or label == current_label):
                current_entity.append((label, idx, token))
                current_label = label
            elif current_entity:
                entity_text = ' '.join([x[2] for x in current_entity])
                start_idx = current_entity[0][1]
                end_idx = current_entity[-1][1]
                role = current_entity[0][0]
                result = {
                    "value": entity_text, "role": role,
                    "start_pos": start_idx, "end_pos": end_idx,
                }
                results.append(result)
                current_entity = []
                current_label = None
                if label:
                    current_entity.append((label, idx, token))
                    current_label = label

        if current_entity:
            entity_text = ' '.join([x[2] for x in current_entity])
            start_idx = current_entity[0][1]
            end_idx = current_entity[-1][1]
            role = current_entity[0][0]
            result = {
                "value": entity_text, "role": role,
                "start_pos": start_idx, "end_pos": end_idx,
            }
            results.append(result)

        return results
