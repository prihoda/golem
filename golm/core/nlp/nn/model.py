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

    def loss_fn(self):
        loss = tf.reduce_mean(
            tf.nn.softmax_cross_entropy_with_logits(
                labels=self.y, logits=self.y_
            )
        )
        return loss

    def get_last_component(self, lstm_output, length):
        batch_size = tf.shape(lstm_output)[0]
        max_length = tf.shape(lstm_output)[1]
        out_size = int(lstm_output.get_shape()[2])
        index = tf.range(0, batch_size) * max_length + (length - 1)
        flat = tf.reshape(lstm_output, [-1, out_size])
        relevant = tf.gather(flat, index)
        return relevant

    def init_network(self, feature_cnt, label_cnt, max_word_cnt, batch_size=1):
        memory_size = int(feature_cnt)

        self.x = tf.placeholder(tf.float32, shape=[None, max_word_cnt, feature_cnt], name='x')
        self.y = tf.placeholder(tf.float32, shape=[None, label_cnt], name='y')
        self.keep_prob = tf.placeholder_with_default(tf.cast(1.0, tf.float32), [], "keep_prob")
        self.lengths = tf.placeholder_with_default(tf.fill([batch_size], max_word_cnt), [batch_size], "lengths")

        with tf.name_scope("rnn"):

            fwd_lstm = tf.nn.rnn_cell.DropoutWrapper(
                tf.contrib.rnn.LSTMCell(memory_size),
                input_keep_prob=self.keep_prob,
                output_keep_prob=self.keep_prob,
                state_keep_prob=self.keep_prob
            )
            bwd_lstm = tf.nn.rnn_cell.DropoutWrapper(
                tf.contrib.rnn.LSTMCell(memory_size),
                input_keep_prob=self.keep_prob,
                output_keep_prob=self.keep_prob,
                state_keep_prob=self.keep_prob
            )

            rnn_1, state = tf.nn.bidirectional_dynamic_rnn(
                cell_fw=fwd_lstm,
                cell_bw=bwd_lstm,
                inputs=self.x,
                sequence_length=self.lengths,
                dtype=tf.float32
            )

            foo = self.get_last_component(rnn_1[0], self.lengths)
            bar = self.get_last_component(rnn_1[1], self.lengths)

        flat = tf.reshape(tf.stack([foo, bar], axis=2), [-1, memory_size * 2])

        dense_1 = tf.layers.dense(flat, label_cnt * 8, tf.nn.leaky_relu, name="dense_1")
        drop = tf.layers.dropout(dense_1, self.keep_prob)
        self.y_ = tf.layers.dense(drop, label_cnt, name="classifier")
        self.preds = tf.nn.softmax(self.y_)

    def train(self, batcher, num_iterations, keep_prob):

        with self.graph.as_default():

            feature_cnt = batcher.dim
            label_cnt = len(batcher.labels)
            max_word_cnt = batcher.max_words

            batch_size = settings.NLP_CONFIG.get("BATCH_SIZE", 32)
            initial_step = settings.NLP_CONFIG.get("INITIAL_STEP", 1e-3)
            use_tensorboard = settings.NLP_CONFIG.get("USE_TENSORBOARD", False)

            self.init_network(feature_cnt, label_cnt, max_word_cnt, batch_size=batch_size)
            loss = self.loss_fn()
            optimizer = tf.train.AdamOptimizer(initial_step).minimize(loss)
            accuracy = tf.reduce_mean(tf.metrics.accuracy(tf.argmax(self.preds, 1), tf.argmax(self.y, 1)))

            self.session.run(tf.global_variables_initializer())
            self.session.run(tf.local_variables_initializer())

            self.file_writer.add_graph(self.graph)
            tf.summary.scalar("loss", loss)
            tf.summary.scalar("accuracy", accuracy)
            tensorboard_op = tf.summary.merge_all() if use_tensorboard else None

            past_losses = [1.] * 25

            for i in range(num_iterations):

                # start_idx = random.randint(0, sample_cnt - batch_size - 1)
                # end_idx = start_idx + batch_size

                # _x_ = features[start_idx:end_idx]
                # _y_ = labels_onehot[start_idx:end_idx]
                # _junk_ = junk[start_idx:end_idx]

                # if i % 100 == 0:  TODO should this stay ?!
                #     total_junk_idx = random.randint(0, batch_size - 1)
                #     _x_[total_junk_idx] = [np.random.random(feature_cnt) for j in range(word_cnt)]
                #     _y_[total_junk_idx] = np.zeros(label_cnt)

                # trashify TODO already done in batcher
                # for j in range(len(_x_)):
                #     junks = _junk_[j]
                #     for junk_pos in junks:
                #         _x_[j][junk_pos] = np.random.random(feature_cnt)
                # print(_x_)

                # zipped = list(zip(_x_, _y_))
                # random.shuffle(zipped)
                # _x_, _y_ = zip(*zipped)

                _x_, _y_ = batcher.next_batch(batch_size)

                optimizer.run(feed_dict={self.x: _x_, self.y: _y_, self.keep_prob: keep_prob},
                              session=self.session)
                if use_tensorboard:
                    tensorboard_result = self.session.run(tensorboard_op, feed_dict={self.x: _x_, self.y: _y_})
                    self.file_writer.add_summary(tensorboard_result, i)

                xe = self.session.run(loss, feed_dict={self.x: _x_, self.y: _y_})

                print('Iteration ', i, '/', num_iterations,
                      'Xentropy:', xe,
                      'Accuracy:', self.session.run(accuracy, feed_dict={self.x: _x_, self.y: _y_}))

                past_losses.insert(0, xe)
                past_losses = past_losses[:25]
                if np.max(past_losses) < 0.05:
                    print("Early stopping, loss < 0.05")
                    break

            # save model
            saver = tf.train.Saver()
            saver.save(self.session, os.path.join(self.base_dir, self.entity, 'tf_session'))
            with open(os.path.join(self.base_dir, self.entity, 'tf_metadata.json'), 'w') as f:
                json.dump({'feature_cnt': feature_cnt, 'label_cnt': label_cnt, 'word_cnt': max_word_cnt}, f)

    def load(self):
        with open(os.path.join(self.base_dir, self.entity, 'tf_metadata.json')) as f:
            metadata = json.load(f)
        feature_cnt, label_cnt = metadata['feature_cnt'], metadata['label_cnt']
        word_cnt = metadata['word_cnt']
        print('features:', feature_cnt, 'labels:', label_cnt)
        print('Restoring from {}'.format(self.base_dir))
        self.init_network(feature_cnt, label_cnt, word_cnt)
        self.label_cnt = label_cnt
        saver = tf.train.Saver()
        saver.restore(self.session, os.path.join(self.base_dir, self.entity, 'tf_session'))

    def predict(self, features):
        with self.graph.as_default():
            if not self.loaded:
                self.load()
                self.loaded = True

            return self.session.run(self.preds, feed_dict={self.x: features})

    def test(self, x, y):
        with self.graph.as_default():
            if not self.loaded:
                self.load()
                self.loaded = True

            # accuracy = tf.metrics.accuracy(predictions=tf.argmax(self.y_, 1), labels=tf.argmax(self.y, 1))
            scores, predictions, losses = [], [], []
            output = []
            loss_fn = self.loss_fn()
            for _x_, _y_ in zip(x, y):
                labels = np.zeros(self.label_cnt)
                if _y_ != -1:
                    labels[_y_] = 1.0

                y_ = self.session.run(self.preds, feed_dict={self.x: _x_})
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
