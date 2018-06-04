import logging
import os

import numpy as np
import random

import time


class GloVe:
    def __init__(self, dir='.', prefix='glove.6B'):
        """
        Loads word embeddings from disk.
        This may take a few seconds, reuse this object.
        It will take a few minutes to cache the words on first run.
        """
        self.dir = dir
        self.prefix = prefix
        self.files = [os.path.join(dir, f) for f in os.listdir(dir) if f.startswith(prefix)]
        if not self.files:  # TODO remove support for horizontally joined files and change to vertical
            raise ValueError(
                'No GloVe files found at {} with prefix {}'.format(
                    dir, prefix))
        self.offsets = {}
        self.use_weights = False
        self.weights = []
        # self.reader = None
        if not self.load_from_cache():
            self.load()
            self.create_word_cache()

    def create_word_cache(self):
        logging.warning('Creating GloVe cache at {}'.format(self.dir))
        with open(os.path.join(self.dir, 'glove.cache'), 'w') as stream:
            words = sorted(self.offsets.keys())
            for word in words:
                stream.write('{} '.format(word))
                stream.write(' '.join([str(x) for x in self.offsets[word]]))
                stream.write('\n')
            logging.warning('Wrote {} GloVe words to cache'.format(len(words)))
        with open(os.path.join(self.dir, 'glove.weights'), 'w') as stream:
            stream.write(' '.join([str(x) for x in self.weights]))
            logging.warning('Wrote {} weights to cache'.format(len(self.weights)))

    def load_from_cache(self):
        logging.info('Loading GloVe cached info')
        fpath = os.path.join(self.dir, 'glove.cache')
        if not os.path.isfile(fpath):
            logging.warning('GloVe cache does not exist')
            return False
        with open(fpath, 'r') as stream:
            for line in stream:
                tokens = line.split()
                self.offsets[tokens[0]] = [int(x) for x in tokens[1:]]
        logging.info('Loaded {} GloVe words from cache'.format(len(self.offsets)))
        if self.use_weights:
            fpath = os.path.join(self.dir, 'glove.weights')
            if not os.path.isfile(fpath):
                return False
            with open(fpath, 'r') as stream:
                weights = []
                for weight in stream.read().split():
                    weights.append(float(weight))
                self.weights = weights
        return True

    def load(self):
        logging.info('Loading GloVe')

        with open(self.files[0], 'r') as stream:
            for idx, line in enumerate(stream):
                word = line.split()[0]
                self.offsets[word] = []
        for filename in self.files:
            with open(filename) as stream:
                line, offset = stream.readline(), 0
                while line:
                    word = line.split()[0]
                    self.offsets[word].append(offset)
                    offset = stream.tell()
                    line = stream.readline()

        # try:
        #     import simstring
        #     db = simstring.writer(os.path.join(self.dir, 'simstring.db'))
        #     for word in list(self.offsets.keys()):
        #         db.insert(word)
        #     db.close()
        # except:
        #     logging.warning("Simstring not found, approximate matching will not work.")

        word_cnt = len(self.offsets)
        self.weights = self.compute_variances()
        logging.debug('Loaded {} GloVe words'.format(word_cnt))

    def get_dimension(self):
        """Returns the dimension of the output word vectors."""
        dim = 0
        for file_idx, fn in enumerate(self.files):
            with open(fn, 'r') as stream:
                line = stream.readline()
                arr = line.split()
                dim += len(arr) - 1
        return dim

    def get_vector(self, word, nearest_match=False):
        """
        Loads vector representation of a word.
        Time complexity O(1) with respect to number of words.
        :param  word
        :returns:   numpy.array on success, None otherwise.
        """
        if word not in self.offsets and nearest_match:
            word = self.get_nearest_match(word)
        if word not in self.offsets:
            return None
            #word = '########'  # FIXME use <unk>, which I don't have in the embedding right now
        if word in self.offsets:
            vec = []
            for file_idx, filename in enumerate(self.files):
                with open(filename, 'r') as stream:
                    stream.seek(self.offsets[word][file_idx])
                    line = stream.readline()
                    arr = line.split()
                    if arr[0] == word:
                        vec += [float(x) for x in arr[1:]]
            if self.use_weights:
                return np.array(vec) / self.weights
            return np.array(vec)
        return None

    def compute_variances(self):
        """Computes relative weights of all data columns."""
        variances = []
        base = 0
        for filename in self.files:
            dim_cnt = 0
            with open(filename, 'r') as f:
                for line_idx, line in enumerate(f):
                    line = line.strip()
                    if line_idx == 0:
                        dim_cnt = len(line.split(' ')) - 1
                        if dim_cnt < 1:
                            continue  # empty line
                        for i in range(dim_cnt):
                            variances.append(0.0)
                    for i, x in enumerate(line.split(' ')[1:]):
                        variances[base + i] += float(x) * float(x)
            base += dim_cnt
        return np.sqrt(np.array(variances))

    def _cos(self, u, v):
        if u is not None and v is not None:
            dot = np.dot(u, v)
            du = np.dot(u, u)
            dv = np.dot(v, v)
            return dot / np.sqrt(du * dv)
        else:
            return 0.0

    def similarity(self, w1, w2):
        """
        Computes cosine similarity between two words.
        :params:    Words w1, w2
        :returns:   Cosine similarity (0;1)
                    Returns 0.0 if word(s) not found in GloVe.
        """
        u, v = self.get_vector(w1), self.get_vector(w2)
        return self._cos(u, v)

    def extract_keywords(self, text, keywords, threshold=0.3):
        """
        Looks for words similar to keywords in text.
        :param  text        An array of words.
        :param  keywords    An array of words.
        :returns:           np.array containing tuples (word, score)
        """
        kw_vec = np.array([self.get_vector(kw) for kw in keywords])
        scalars = np.array([np.sqrt(np.dot(x, x)) for x in kw_vec])

        matches = []

        for word in text:
            u = self.get_vector(word)
            if u is None:
                continue
            dots = np.dot(kw_vec, u.T)
            u_scalar = np.sqrt(np.dot(u, u))
            score = np.mean(dots / (scalars * u_scalar))
            print(word, ':', score)
            if score > threshold:
                matches.append((word, score))
                break
        return matches

    def get_centroid(self, words):
        vec = []
        for word in words:
            v = self.get_vector(word)
            if v is not None:
                vec.append(v)
        return np.mean(vec, axis=0)

    def random_word(self):
        """Returns a randomly chosen word from this embedding."""
        return random.choice(list(self.offsets.keys()))

    # def simstring_reader(self):
    #     if self.reader != None:
    #         return self.reader
    #     elif os.path.exists(os.path.join(self.dir, 'simstring.db')):
    #         try:
    #             logging.debug("Loading simstring reader")
    #             import simstring
    #             db = simstring.reader(os.path.join(self.dir, 'simstring.db'))
    #             db.measure = simstring.cosine
    #             db.threshold = 0.2
    #             self.reader = db
    #             return db
    #         except ImportError:
    #             logging.warning("Simstring not found, nearest match not available")
    #     return None

    def get_nearest_match(self, word):
        logging.warning("Using nearest match")

        if not word:
            return None

        t = time.time()
        from core.nlp.tools import correct
        match = correct.nearest_word(word, self)
        t = time.time() - t
        logging.warning("Nearest match: {} time: {} s".format(match, t))
        return match

    def contains(self, word):
        return self.offsets.get(word) != None
