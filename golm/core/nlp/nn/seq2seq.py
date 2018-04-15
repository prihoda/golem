import json
import os
import string

import random
import tensorflow as tf
import numpy as np


class Seq2Seq:
    def __init__(self, entity, base_dir):
        if not base_dir or not entity:
            raise ValueError('Base dir and entity name must be set')
        self.base_dir = base_dir
        self.entity = entity
        self.graph = tf.Graph()
        self.session = tf.Session(graph=self.graph)
        self.loaded = False
        self.label_cnt = None
        self.alphabet = list(string.ascii_lowercase + string.digits + ' ')

    def destroy(self):
        self.session.close()

    def make_weights(self, shape):
        return tf.Variable(tf.truncated_normal(shape, stddev=0.1))

    def make_biases(self, shape):
        return tf.Variable(tf.constant(0.1, shape=shape))

    def loss_fn(self, labels, logits):
        return tf.contrib.seq2seq.sequence_loss(
            logits=logits,
            targets=tf.cast(tf.argmax(labels, axis=2), tf.int32),
            weights=tf.ones([logits.shape[0], logits.shape[1]])
        )

    def get_word_lengths(self, batch):
        raise Exception('dont use me')
        nonzero = tf.sign(tf.reduce_max(tf.abs(batch), axis=2))  # number of filled features
        length = tf.cast(tf.reduce_sum(nonzero, axis=1), tf.int32)  # as int
        return length

    def get_last_component(self, lstm_output, length):
        batch_size = tf.shape(lstm_output)[0]
        max_length = tf.shape(lstm_output)[1]
        out_size = int(lstm_output.get_shape()[2])
        index = tf.range(0, batch_size) * max_length + (length - 1)
        flat = tf.reshape(lstm_output, [-1, out_size])
        relevant = tf.gather(flat, index)
        return relevant

    def encode_to_alphabet(self, text, length, alphabet) -> np.array:
        alphabet_size = len(alphabet)
        text = text[0:length].lower()
        encoded_chars = [np.zeros(alphabet_size) for i in range(length)]
        for i in range(length):
            encoded_chars[i][alphabet.index(' ')] = 1.0
        for char_off, char in enumerate(text):
            if char in alphabet:
                idx = alphabet.index(char)
                encoded = np.zeros(alphabet_size)
                encoded[idx] = 1.0
                encoded_chars[char_off] = encoded
                # encoded_chars[char_off][idx] = 1.0
        return np.array(encoded_chars)

    def decode_from_alphabet(self, characters, alphabet) -> str:
        text = ""
        for char in characters:
            val = np.max(char)
            if val > 0.8:
                idx = np.argmax(char)
                text += alphabet[idx]
            else:
                text += '_'
        return text

    def get_shape(self, max_length, alphabet_size, batch_size=1):
        memory_size = int(alphabet_size * 2)

        x = tf.placeholder(tf.float32, shape=[batch_size, max_length, alphabet_size], name='x')
        y = tf.placeholder(tf.float32, shape=[batch_size, max_length, alphabet_size], name='y')

        with tf.variable_scope('encoder') as scope:
            encoder_out, state = tf.nn.dynamic_rnn(
                tf.contrib.rnn.LSTMCell(alphabet_size * 5, forget_bias=0.9),
                x,
                scope=scope,
                dtype=tf.float32
            )

        with tf.variable_scope('decoder') as scope:
            decoder_out, state = tf.nn.dynamic_rnn(
                tf.contrib.rnn.LSTMCell(alphabet_size, forget_bias=0.9, activation=tf.nn.relu),
                encoder_out,
                scope=scope,
                dtype=tf.float32
            )

        y_ = decoder_out

        return x, y, y_

    def randomize(self, features, labels):
        x_out, y_out = [], []
        for x, y in zip(features, labels):
            length = random.randint(1, 10)
            s = ''.join([random.choice(string.ascii_lowercase + string.digits + ' ') for i in range(length)])
            x_out.append(x.replace('%', s))
            y_out.append(y.replace('%', s))
        return x_out, y_out

    def train(self, features, labels, num_epochs=50000, max_length=25):  # FIXME more than 25 chars
        if features is None or labels is None:
            raise ValueError('Features and labels must be set')

        features = np.array(features)
        labels = np.array(labels)

        with self.graph.as_default():

            batch_size = 1

            x, y, y_ = self.get_shape(max_length, len(self.alphabet), batch_size=batch_size)

            loss = self.loss_fn(y, y_)

            sample_cnt = features.shape[0]

            optimizer = tf.train.AdamOptimizer(0.001).minimize(loss)
            accuracy = tf.metrics.accuracy(tf.argmax(tf.nn.softmax(y_), 1), tf.argmax(y, 1))

            self.session.run(tf.global_variables_initializer())
            self.session.run(tf.local_variables_initializer())
            for i in range(num_epochs):
                start_idx = i % (sample_cnt - batch_size)
                end_idx = start_idx + batch_size

                _x_, _y_ = self.randomize(features[start_idx:end_idx], labels[start_idx:end_idx])
                _x_ = [self.encode_to_alphabet(x, max_length, self.alphabet) for x in _x_]
                _y_ = [self.encode_to_alphabet(y, max_length, self.alphabet) for y in _y_]

                optimizer.run(feed_dict={x: _x_, y: _y_},
                              session=self.session)
                print('Generation ', i, '/', num_epochs,
                      'Xentropy:', self.session.run(loss, feed_dict={x: _x_, y: _y_}),
                      'Accuracy:', self.session.run(accuracy, feed_dict={x: _x_, y: _y_}))
                output = self.session.run(y_, feed_dict={x: _x_, y: _y_})
                print(
                    self.decode_from_alphabet(output[0], self.alphabet)
                    + "\t"
                    + self.decode_from_alphabet(_y_[0], self.alphabet)
                )  # it's a batch

            # save model
            saver = tf.train.Saver()
            saver.save(self.session, os.path.join(self.base_dir, self.entity, 'tf_session'))
            with open(os.path.join(self.base_dir, self.entity, 'tf_metadata.json'), 'w') as f:
                json.dump({'max_length': max_length}, f)

    def load(self):
        with open(os.path.join(self.base_dir, self.entity, 'tf_metadata.json')) as f:
            metadata = json.load(f)
        # feature_cnt, label_cnt = metadata['feature_cnt'], metadata['label_cnt']
        # word_cnt = metadata['word_cnt']
        # print('features:', feature_cnt, 'labels:', label_cnt)
        print('Restoring from {}'.format(self.base_dir))
        x, y, y_ = self.get_shape(25, len(self.alphabet))  # FIXME
        self.x = x
        self.y = y
        self.logits = y_
        self.y_ = tf.nn.softmax(y_)
        # self.W = W
        # self.label_cnt = label_cnt
        saver = tf.train.Saver()
        saver.restore(self.session, os.path.join(self.base_dir, self.entity, 'tf_session'))

    def predict(self, text):
        with self.graph.as_default():
            if not self.loaded:
                self.load()
                self.loaded = True

            _x_ = self.encode_to_alphabet(text, 25, self.alphabet)  # FIXME max_length
            pred = self.session.run(self.logits, feed_dict={self.x: [_x_]})
            s = self.decode_from_alphabet(pred[0], self.alphabet)
            print(s)
            return s.lstrip().rstrip()

    def test(self, x, y):
        raise NotImplementedError()
        with self.graph.as_default():
            if not self.loaded:
                self.load()
                self.loaded = True

            # accuracy = tf.metrics.accuracy(predictions=tf.argmax(self.y_, 1), labels=tf.argmax(self.y, 1))
            scores, predictions, losses = [], [], []
            loss_fn = self.loss_fn(self.y, self.logits, self.W)
            for _x_, _y_ in zip(x, y):
                labels = np.zeros(self.label_cnt)
                labels[_y_] = 1.0

                y_ = self.session.run(self.y_, feed_dict={self.x: _x_})
                loss = self.session.run(loss_fn, feed_dict={self.x: _x_, self.y: [labels]})
                y_ = np.argmax(y_)
                predictions.append(y_)
                losses.append(loss)
                if y_ == _y_:
                    scores.append(1.0)
                else:
                    scores.append(0.0)
            print("[{}] Accuracy score: {}% or {}/{}".format(self.entity, np.mean(scores) * 100, scores.count(1.0),
                                                             len(scores)))
            print("[{}] Mean Cross Entropy Loss: {}".format(self.entity, np.mean(losses)))
            return scores, predictions
