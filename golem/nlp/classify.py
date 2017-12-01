import json
import os
import pickle

from golem.nlp.czech_stemmer import cz_stem
from golem.nlp.keywords import keyword_search

print('Will import SpaCy and TF!')

import numpy as np
from golem.nlp import duckling
from golem.nlp.model import Model

from celery.app.log import get_logger

from golem.nlp import utils

logging = get_logger(__name__)

# load stemming only
nlp = utils.get_spacy()
glove = utils.get_glove()
logging.debug('SpaCy and TF imported')

models = {}


def get_model(entity, entity_dir) -> Model:
    """Lazy loads a tf model."""
    if entity not in models:
        models[entity] = Model(entity, entity_dir)
    return models[entity]


def cleanup(text, stemming=False):
    """
    Tokenizes and stems a sentence.
    :param text     Text that needs to be tokenized
    :param stemming Words will be stemmed if true
    :returns:       List of tokens.
    """
    tokens = nlp.tokenizer(text)
    ignore_words = ['?', '.', '!']
    if stemming:
        # nlp.tagger(tokens)
        return [cz_stem(str(token), aggressive=True) for token in tokens]
    tokens = [str(token).lower() for token in tokens]
    return [t for t in tokens if t not in ignore_words]


def word2vec(text):
    """
    Converts entity to a vector for tensorflow.
    :param text     Text to be converted to BOW.
    :returns    numpy array of features
    """
    features = [np.zeros(glove.get_dimension()) for x in range(10)]
    for idx, word in enumerate(cleanup(text)):
        if idx > 10:
            logging.warning('Message too long!')  # FIXME allow longer messages
        vec = glove.get_vector(word)
        if vec is not None:
            features[idx] = vec * 1000
    return np.array([features])


def classify_trait(text, entity, threshold):
    """
    Classifies entity with a neural network.
    :returns:   Predicted label from tensorflow.
    """
    entity_dir = os.path.join(os.environ['NLP_DATA_DIR'], 'model', entity)
    pickle_data = pickle.load(open(os.path.join(entity_dir, 'pickle.json'), 'rb'))
    x, y = pickle_data['x'], pickle_data['y']
    words, classes = pickle_data['words'], pickle_data['classes']

    logging.info("classifying " + entity_dir + " " + entity + ' with feature count: ' + str(len(words)))
    model = get_model(entity, entity_dir)
    bow = word2vec(text)
    y_pred = model.predict(bow)[0]
    logging.debug(y_pred)
    print(y_pred)
    y_pred = [[i, score] for i, score in enumerate(y_pred) if score > threshold]
    y_pred.sort(key=lambda x: x[1], reverse=True)

    if len(y_pred) > 0:
        value = classes[y_pred[0][0]]
        prob = y_pred[0][1]
        print('> Predicted {}: {} Prob: {}%'.format(entity, value, prob * 100))
        print('All scores > threshold are:', y_pred)
        if value is not None and value != 'none':
            return [{'value': value}]
    return None


def classify_keywords(text, entity, should_stem=False):
    """
    Classifies entity using a list of keywords.
    :returns:   Predicted keyword.
    """
    # FIXME ADD METADATA !!!
    matches = []
    words = set(cleanup(text, should_stem))
    entity_dir = os.path.join(os.environ['NLP_DATA_DIR'], 'model', entity)
    with open(os.path.join(entity_dir, 'keywords.json'), 'r') as f:
        keywords = json.load(f)
    for idx, keyword in enumerate(keywords):
        kw = set(cleanup(keyword['value']))
        if words & kw == kw:
            data = {}
            if 'label' in keyword:
                data['value'] = keyword['label']
            else:
                data['value'] = keyword['value']
            if 'metadata' in keyword:
                data['metadata'] = keyword['metadata']
            matches.append(data)
    return matches


def classify(text: str, current_state=None):
    """
    Classifies all entity values of a text input.
    :param text
    :param current_state    State of the conversation without the init/accept suffix.
    :returns:   Dict containing found entities.
    """
    output = {}
    model_dir = os.path.join(os.environ['NLP_DATA_DIR'], 'model')
    dirs = [i for i in os.scandir(model_dir) if i.is_dir()]

    for dir in dirs:
        # search in text for each known entity
        entity = dir.name
        entity_dir = os.path.join(model_dir, entity)

        with open(os.path.join(entity_dir, 'metadata.json'), 'r') as f:
            metadata = json.load(f)

        # if the entity is limited by allowed states, check if we're in one of them before continuing
        if current_state and 'allowed_states' in metadata:
            if current_state not in metadata['allowed_states']:
                continue

        if metadata['strategy'] == 'trait':
            pred = classify_trait(text, entity, metadata.get('threshold', 0.7))
            if pred:
                output[entity] = pred
        elif metadata['strategy'] == 'keywords':
            with open(os.path.join(entity_dir, "trie.json"), 'r') as g:
                trie = json.load(g)
            should_stem = metadata.get('stemming', False)
            language = metadata.get('language', utils.get_default_language())
            pred = keyword_search(text, trie, should_stem, language)
            if pred:
                output[entity] = pred
        else:
            logging.warning('Unknown search strategy {} for entity {}, skipping!' \
                            .format(metadata['strategy'], entity))

    output.update(duckling.get(text))
    logging.debug(output)
    return output


def test_all():
    test_dir = os.path.join(os.environ['NLP_DATA_DIR'], 'testing_data')
    entities = []
    for f in os.scandir(test_dir):
        name, ext = os.path.splitext(f.name)
        if f.is_file() and ext == '.json':
            entities.append((name, f))
    for entity, filename in entities:
        with open(filename) as f:
            examples = json.load(f).items()
            model_dir = os.path.join(os.environ['NLP_DATA_DIR'], 'model', entity)
            model = get_model(entity, model_dir)
            pickle_data = pickle.load(open(os.path.join(model_dir, 'pickle.json'), 'rb'))
            classes = pickle_data['classes']
            x = [word2vec(text) for text, label in examples]
            y = [classes.index(label) for text, label in examples]
            scores, predictions = model.test(x, y)
            for example, score, pred in zip(examples, scores, predictions):
                if abs(score - 0.0) < 1e-4:
                    print("Wrong label for '{}': '{}' expected: '{}'".format(example[0], classes[pred], example[1]))
