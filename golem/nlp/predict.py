import logging

import os
import yaml

from golem.nlp import utils


class GolemNLU:

    def __init__(self):
        self.nlp_data_dir = utils.data_dir()
        self.model_dir = os.path.join(self.nlp_data_dir, 'model')

        self.entities = {}

        entity_names = [i for i in os.scandir(self.model_dir) if i.is_dir()]
        for dir in entity_names:
            self.load_entity(dir.name)

    def load_entity(self, name):

        base_dir = os.path.join(self.model_dir, name)

        with open(os.path.join(base_dir, 'metadata.json'), 'r') as f:
            metadata = yaml.load(f)

        strategy = metadata['strategy']

        model = None

        if strategy == 'bow':
            from golem.nlp.nn.bow_model import BowModel
            model = BowModel(name, base_dir)
        elif metadata['strategy'] == 'context':
            from golem.nlp.nn.contextual import ContextualModel
            model = ContextualModel(name, base_dir)
        elif metadata['strategy'] == 'trait':
            from golem.nlp.nn.rnn_intent_model import RecurrentIntentModel
            model = RecurrentIntentModel(name, base_dir)
        elif metadata['strategy'] == 'keywords':
            from golem.nlp.keywords import TrieKeywordModel
            model = TrieKeywordModel(name, base_dir)
        else:
            logging.warning(
                'Unknown search strategy {} for entity {}, not training!'
                    .format(metadata['strategy'], name)
            )

        if model is not None:
            self.entities[name] = model

        logging.info("Loaded entity {name}".format(name=name))

    def parse(self, utterance):

        output = {}

        for entity in self.entities:

            model = self.entities[entity]
            result = model.predict(utterance)

            if result is None:
                continue
            elif isinstance(result, list):
                output.setdefault(entity, []).extend(result)
            elif isinstance(result, dict):
                output.setdefault(entity, []).append(result)
            else:
                logging.error("Invalid NLU response of type {}".format(type(result)))

        return output

    def parse_entity(self, utterance, entity, threshold=None):
        model = self.entities.get(entity, None)
        if model is not None:
            if threshold:
                return model.predict(utterance, threshold)
            else:
                return model.predict(utterance)
        return None
