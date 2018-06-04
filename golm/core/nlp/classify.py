import json
import pickle
import os

from django.conf import settings

from core.nlp.keywords import keyword_search
from core.nlp.nn.seq2seq import Seq2Seq

print('Will import GloVe and TF!')

import numpy as np
from core.nlp import duckling, cleanup
from core.nlp.nn.model import Model

from celery.app.log import get_logger

from core.nlp import utils

logging = get_logger(__name__)

glove = utils.get_glove()
logging.debug('GloVe and TF imported')

models = {}
imputers = {}

NLP_DATA_DIR = utils.data_dir()
MAX_WORD_COUNT = settings.NLP_CONFIG.get("MAX_WORD_COUNT", 10)


def get_model(entity, entity_dir) -> Model:
    """Lazy loads a tf model."""
    if entity not in models:
        models[entity] = Model(entity, entity_dir)
        imputers[entity] = utils.get_imputation_rules(entity)
    return models[entity]


def word2vec(text, entity):
    """
    Converts entity to a vector for tensorflow.
    :param text     Text to be converted to BOW.
    :returns    numpy array of features
    """
    features = [np.zeros(glove.get_dimension()) for x in range(10)]
    tokens = cleanup.tokenize(text, stemming=False, language="cz")
    clean_text = cleanup.imputer(tokens, imputers.get(entity))
    print("Tokens:", clean_text)
    for idx, word in enumerate(clean_text):
        if idx > MAX_WORD_COUNT:
            logging.warning('Message too long!')  # FIXME allow longer messages
        vec = glove.get_vector(word)
        if vec is not None:
            features[idx] = vec
    return np.array([features])


def classify_trait(text, entity, threshold):
    """
    Classifies entity with a neural network.
    :returns:   Predicted label from tensorflow.
    """
    entity_dir = os.path.join(NLP_DATA_DIR, 'model', entity)
    pickle_data = pickle.load(open(os.path.join(entity_dir, 'pickle.json'), 'rb'))
    labels = pickle_data['labels']

    model = get_model(entity, entity_dir)
    bow = word2vec(text, entity)
    y_pred = model.predict(bow)[0]
    logging.debug(y_pred)
    print(y_pred)
    y_pred = [[i, score] for i, score in enumerate(y_pred) if score > threshold]
    y_pred.sort(key=lambda x: x[1], reverse=True)

    if len(y_pred) > 0:
        value = labels[y_pred[0][0]]
        prob = y_pred[0][1]
        print('> Predicted {}: {} Prob: {}%'.format(entity, value, prob * 100))
        print('All scores > threshold are:', y_pred)
        if value is not None and value != 'none':
            return [{'value': value}]
    return None


def classify(text: str, current_state=None):
    """
    Classifies all entity values of a text input.
    :param text
    :param current_state    State of the conversation without the init/accept suffix.
    :returns:   Dict containing found entities.
    """
    output = {}
    model_dir = os.path.join(NLP_DATA_DIR, 'model')
    dirs = [i for i in os.scandir(model_dir) if i.is_dir()]

    from core.nlp import geneea
    try:
        text = geneea.get_correction(text)
        sentiment = geneea.get_sentiment(text)
    except:
        sentiment = 0.0

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
            import unidecode
            with open(os.path.join(entity_dir, "trie.json"), 'r') as g:
                trie = json.load(g)
            should_stem = metadata.get('stemming', False)
            language = metadata.get('language', utils.get_default_language())
            pred = keyword_search(unidecode.unidecode(text), trie, should_stem, language)
            if pred:
                output[entity] = pred
        elif metadata['strategy'] == 'seq2seq':
            model = models.setdefault(entity, Seq2Seq(entity, entity_dir))
            pred = model.predict(text)
            if pred:
                output[entity] = [{'value': pred}]
        else:
            logging.warning('Unknown search strategy {} for entity {}, skipping!'
                            .format(metadata['strategy'], entity))

    if sentiment:
        output['sentiment'] = [{"value": sentiment}]
    output.update(duckling.get(text))
    logging.debug(output)
    return output


def test_all():
    test_dir = os.path.join(NLP_DATA_DIR, 'testing_data')
    entities = []
    for f in os.scandir(test_dir):
        name, ext = os.path.splitext(f.name)
        if f.is_file() and ext == '.json':
            entities.append((name, f))
    for entity, filename in entities:
        with open(filename) as f:
            examples = json.load(f).items()
            model_dir = os.path.join(NLP_DATA_DIR, 'model', entity)
            model = get_model(entity, model_dir)
            pickle_data = pickle.load(open(os.path.join(model_dir, 'pickle.json'), 'rb'))
            classes = pickle_data['labels']
            x = [word2vec(text, entity) for text, label in examples]
            for text, label in examples:
                print(text, label)
            y = [classes.index(label) if label is not None else -1 for text, label in examples]
            scores, predictions = model.test(x, y)
            for example, score_vec in zip(examples, scores):
                is_ok, score, pred = score_vec
                if not is_ok:
                    prediction = classes[pred] if score > 0.5 else None
                    print("Wrong label for '{}': '{}' expected: '{}'".format(example[0], prediction, example[1]))
