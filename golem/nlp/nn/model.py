import json
from datetime import datetime

import os

import random
import tensorflow as tf
import numpy as np
from django.conf import settings


class Model:
    def __init__(self, entity, base_dir):
        if not base_dir or not entity:
            raise ValueError('Base dir and entity name must be set')
        self.base_dir = base_dir
        self.entity = entity
        self.graph = tf.Graph()
        self.session = tf.Session(graph=self.graph)  # , config=tf.ConfigProto(log_device_placement=True))
        self.file_writer = tf.summary.FileWriter(os.path.join(base_dir, entity, "tensorboard", str(datetime.now())))
        self.loaded = False
        self.label_cnt = None

    def destroy(self):
        self.session.close()

    def make_weights(self, shape, name=None):
        return tf.Variable(tf.truncated_normal(shape, stddev=0.1), name=name)

    def make_biases(self, shape, name=None):
        return tf.Variable(tf.constant(0.1, shape=shape), name=name)

    def loss_fn(self, labels, logits, weights, l2=True):
        loss = tf.reduce_mean(
            tf.nn.softmax_cross_entropy_with_logits(
                labels=labels, logits=logits
            )
        )
        if l2:
            loss += tf.nn.l2_loss(weights) * 0.5
        return loss

    def get_word_lengths(self, batch):
        nonzero = tf.sign(tf.reduce_max(tf.abs(batch), axis=2))  # number of filled features
        length = tf.cast(tf.reduce_sum(nonzero, axis=1), tf.int32)  # as int
        return length, tf.shape(batch)[1] - length + 1

    def get_last_component(self, lstm_output, length):
        batch_size = tf.shape(lstm_output)[0]
        max_length = tf.shape(lstm_output)[1]
        out_size = int(lstm_output.get_shape()[2])
        index = tf.range(0, batch_size) * max_length + (length - 1)
        flat = tf.reshape(lstm_output, [-1, out_size])
        relevant = tf.gather(flat, index)
        return relevant

    def get_shape(self, feature_cnt, label_cnt, max_word_cnt, batch_size=1):
        memory_size = int(feature_cnt)

        x = tf.placeholder(tf.float32, shape=[batch_size, max_word_cnt, feature_cnt], name='x')
        y = tf.placeholder(tf.float32, shape=[batch_size, label_cnt], name='y')

        # lengths, lengths_bw = self.get_word_lengths(x)
        lengths = tf.fill([batch_size], 10)

        with tf.name_scope("rnn"):

            fwd_lstm = tf.contrib.rnn.LSTMCell(memory_size)
            bwd_lstm = tf.contrib.rnn.LSTMCell(memory_size)

            rnn_1, state = tf.nn.bidirectional_dynamic_rnn(
                fwd_lstm,
                bwd_lstm,
                x,
                sequence_length=tf.fill([batch_size], 10),
                dtype=tf.float32
            )

            foo = self.get_last_component(rnn_1[0], lengths)
            bar = self.get_last_component(rnn_1[1], lengths)

            #tf.summary.histogram("lstm_forward", fwd_lstm.weights)
            #tf.summary.histogram("lstm_backward", bwd_lstm.weights)

        flat = tf.reshape(tf.stack([foo, bar], axis=2), [batch_size, memory_size * 2])

        with tf.name_scope("fc1"):
            W_1 = self.make_weights([memory_size * 2, label_cnt * 8], name="w")
            b_1 = self.make_biases([label_cnt * 8], name="b")
            dense_1 = tf.nn.relu(tf.matmul(flat, W_1) + b_1)
            tf.summary.histogram("W_fc1", W_1)

        with tf.name_scope("classifier"):
            W = self.make_weights([label_cnt * 8, label_cnt], name="w")
            b = self.make_biases([label_cnt], name="b")
            y_ = tf.matmul(dense_1, W) + b
            tf.summary.histogram("W_cls", W)

        return x, y, y_, W

    def train(self, features, labels, junk, num_iterations):
        if features is None or labels is None:
            raise ValueError('Features and labels must be set')

        features = np.array(features)
        labels_onehot = np.array(labels)

        with self.graph.as_default():

            feature_cnt = features.shape[2]
            word_cnt = features.shape[1]
            print('Shape:', labels_onehot.shape)
            label_cnt = labels_onehot.shape[1]

            batch_size = settings.NLP_CONFIG.get("batch_size", 32)
            initial_step = settings.NLP_CONFIG.get("initial_step", 1e-4)

            x, y, y_, W = self.get_shape(feature_cnt, label_cnt, word_cnt, batch_size=batch_size)

            loss = self.loss_fn(y, y_, W)
            loss_without_l2 = self.loss_fn(y, y_, W, l2=False)

            sample_cnt = features.shape[0]

            optimizer = tf.train.AdamOptimizer(initial_step).minimize(loss)
            accuracy = tf.reduce_mean(tf.metrics.accuracy(tf.argmax(tf.nn.softmax(y_), 1), tf.argmax(y, 1)))

            self.session.run(tf.global_variables_initializer())
            self.session.run(tf.local_variables_initializer())

            self.file_writer.add_graph(self.graph)
            tf.summary.scalar("loss", loss_without_l2)
            tf.summary.scalar("accuracy", accuracy)
            tensorboard_op = tf.summary.merge_all()

            for i in range(num_iterations):

                start_idx = random.randint(0, sample_cnt - batch_size - 1)
                end_idx = start_idx + batch_size

                _x_ = features[start_idx:end_idx]
                _y_ = labels_onehot[start_idx:end_idx]
                _junk_ = junk[start_idx:end_idx]

                if i % 100 == 0:
                    total_junk_idx = random.randint(0, batch_size - 1)
                    _x_[total_junk_idx] = [np.random.random(feature_cnt) for j in range(word_cnt)]
                    _y_[total_junk_idx] = np.zeros(label_cnt)

                # trashify
                for j in range(len(_x_)):
                    junks = _junk_[j]
                    for junk_pos in junks:
                        _x_[j][junk_pos] = np.random.random(feature_cnt)
                # print(_x_)

                zipped = list(zip(_x_, _y_))
                random.shuffle(zipped)
                _x_, _y_ = zip(*zipped)

                optimizer.run(feed_dict={x: _x_, y: _y_},
                              session=self.session)
                tensorboard_result = self.session.run(tensorboard_op, feed_dict={x: _x_, y: _y_})
                self.file_writer.add_summary(tensorboard_result, i)
                print('Generation ', i, '/', num_epochs,
                      'Xentropy:', self.session.run(loss_without_l2, feed_dict={x: _x_, y: _y_}),
                      'Accuracy:', self.session.run(accuracy, feed_dict={x: _x_, y: _y_}))

            # save model
            saver = tf.train.Saver()
            saver.save(self.session, os.path.join(self.base_dir, self.entity, 'tf_session'))
            with open(os.path.join(self.base_dir, self.entity, 'tf_metadata.json'), 'w') as f:
                json.dump({'feature_cnt': feature_cnt, 'label_cnt': label_cnt, 'word_cnt': word_cnt}, f)

    def load(self):
        with open(os.path.join(self.base_dir, self.entity, 'tf_metadata.json')) as f:
            metadata = json.load(f)
        feature_cnt, label_cnt = metadata['feature_cnt'], metadata['label_cnt']
        word_cnt = metadata['word_cnt']
        print('features:', feature_cnt, 'labels:', label_cnt)
        print('Restoring from {}'.format(self.base_dir))
        x, y, y_, W = self.get_shape(feature_cnt, label_cnt, word_cnt)
        self.x = x
        self.y = y
        self.logits = y_
        self.y_ = tf.nn.softmax(y_)
        self.W = W
        self.label_cnt = label_cnt
        saver = tf.train.Saver()
        saver.restore(self.session, os.path.join(self.base_dir, self.entity, 'tf_session'))

    def predict(self, features):
        with self.graph.as_default():
            if not self.loaded:
                self.load()
                self.loaded = True

            return self.session.run(self.y_, feed_dict={self.x: features})

    def test(self, x, y):
        with self.graph.as_default():
            if not self.loaded:
                self.load()
                self.loaded = True

            # accuracy = tf.metrics.accuracy(predictions=tf.argmax(self.y_, 1), labels=tf.argmax(self.y, 1))
            scores, predictions, losses = [], [], []
            output = []
            loss_fn = self.loss_fn(self.y, self.logits, self.W)
            for _x_, _y_ in zip(x, y):
                labels = np.zeros(self.label_cnt)
                if _y_ != -1:
                    labels[_y_] = 1.0

                y_ = self.session.run(self.y_, feed_dict={self.x: _x_})
                loss = self.session.run(loss_fn, feed_dict={self.x: _x_, self.y: [labels]})
                arg = np.argmax(y_)
                predictions.append(arg)
                losses.append(loss)
                maxscore = np.max(y_)
                mean = np.mean(y_)
                if (arg == _y_ and maxscore > 0.8) or (maxscore < 0.8 and _y_ == -1):
                    print("Correct {}".format(maxscore))
                    scores.append(maxscore)
                    output.append((True, maxscore, arg))
                else:
                    print("Incorrect {}".format(maxscore))
                    scores.append(0.0)
                    output.append((False, maxscore, arg))
            correct = sorted(scores, reverse=True).index(0.0) if 0.0 in scores else len(scores)
            print("[{}] Accuracy score: {}% or {}/{}".format(self.entity, np.mean(scores) * 100,
                                                             correct, len(scores)))
            print("[{}] Mean Cross Entropy Loss: {}".format(self.entity, np.mean(losses)))
            return output, predictions
