import json
import os
import tensorflow as tf
import numpy as np


class Model:
    def __init__(self, entity, base_dir):
        if not base_dir or not entity:
            raise ValueError('Base dir and entity name must be set')
        self.base_dir = base_dir
        self.entity = entity
        self.graph = tf.Graph()
        self.session = tf.Session(graph=self.graph)
        self.loaded = False
        self.label_cnt = None

    def destroy(self):
        self.session.close()

    def make_weights(self, shape):
        return tf.Variable(tf.truncated_normal(shape, stddev=0.1))

    def make_biases(self, shape):
        return tf.Variable(tf.constant(0.1, shape=shape))

    def loss_fn(self, labels, logits, weights):
        return tf.reduce_mean(
            tf.nn.softmax_cross_entropy_with_logits(
                labels=labels, logits=logits
            ) + tf.nn.l2_loss(weights) * 0.5
        )

    def get_word_lengths(self, batch):
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

    def get_shape(self, feature_cnt, label_cnt, max_word_cnt, batch_size=1):
        memory_size = int(feature_cnt * 2)

        x = tf.placeholder(tf.float32, shape=[batch_size, max_word_cnt, feature_cnt], name='x')
        y = tf.placeholder(tf.float32, shape=[batch_size, label_cnt], name='y')

        lstm = tf.contrib.rnn.LSTMCell(memory_size, use_peepholes=False, forget_bias=1.0)

        init_state = tf.zeros([batch_size, memory_size])
        hidden_state = tf.zeros([batch_size, memory_size])
        state = tf.contrib.rnn.LSTMStateTuple(init_state, hidden_state)

        lengths = self.get_word_lengths(x)

        rnn_1, state = tf.nn.dynamic_rnn(
            lstm, x, sequence_length=lengths,
            initial_state=state, dtype=tf.float32
        )

        foo = self.get_last_component(rnn_1, lengths)

        W_1 = self.make_weights([memory_size, label_cnt * 8])
        b_1 = self.make_biases([label_cnt * 8])

        dense_1 = tf.nn.relu(tf.matmul(foo, W_1) + b_1)

        W = self.make_weights([label_cnt * 8, label_cnt])
        b = self.make_biases([label_cnt])

        y_ = tf.matmul(dense_1, W) + b
        return x, y, y_, W

    def train(self, features, labels, num_epochs=2000):
        if features is None or labels is None:
            raise ValueError('Features and labels must be set')

        features = np.array(features)
        labels_onehot = np.array(labels)

        with self.graph.as_default():

            feature_cnt = features.shape[2]
            word_cnt = features.shape[1]
            print('Shape:', labels_onehot.shape)
            label_cnt = labels_onehot.shape[1]

            batch_size = 50

            x, y, y_, W = self.get_shape(feature_cnt, label_cnt, word_cnt, batch_size=batch_size)

            loss = self.loss_fn(y, y_, W)

            sample_cnt = features.shape[0]

            optimizer = tf.train.AdamOptimizer(1e-3).minimize(loss)
            accuracy = tf.metrics.accuracy(tf.argmax(tf.nn.softmax(y_), 1), tf.argmax(y, 1))

            self.session.run(tf.global_variables_initializer())
            self.session.run(tf.local_variables_initializer())
            for i in range(num_epochs):
                start_idx = i % (sample_cnt - batch_size)
                end_idx = start_idx + batch_size

                _x_ = features[start_idx:end_idx]
                _y_ = labels_onehot[start_idx:end_idx]

                optimizer.run(feed_dict={x: _x_, y: _y_},
                              session=self.session)
                print('Generation ', i, '/', num_epochs,
                      'Xentropy:', self.session.run(loss, feed_dict={x: _x_, y: _y_}),
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
