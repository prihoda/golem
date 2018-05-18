import os
import unidecode
import yaml

from golem.nlp import utils
from golem.nlp.cleanup import tokenize
# TODO remove character accents
from golem.nlp.nn.abs_model import NLUModel


class TrieKeywordModel(NLUModel):

    def __init__(self, entity, base_dir, is_training=False):
        self.entity = entity
        self.base_dir = base_dir

        if not is_training:
            with open(os.path.join(base_dir, "trie.json"), 'r') as f:
                self.trie = yaml.load(f)
            with open(os.path.join(base_dir, "metadata.json"), 'r') as f:
                metadata = yaml.load(f)
                self.should_stem = metadata.get('stemming', False)
                self.language = metadata.get('language', utils.get_default_language())

    def predict(self, utterance: str, threshold=None):
        return self.keyword_search(utterance)

    def prepare(self, examples, metadata):

        self.should_stem = metadata.get('stemming', False)
        self.language = metadata.get('language', utils.get_default_language())

        trie = self.prepare_keywords(examples)

        with open(os.path.join(self.base_dir, "trie.json"), "w") as f:
            yaml.dump(trie, f)

    def prepare_keywords(self, data) -> dict:
        """
        Prepares keywords for fast search.
        First words of each expression are processed into a trie.
        :param data:            A dict containing keyword data
        :param should_stem:     Boolean, whether to use stemmed keywords
                                for comparison. Default is false.
        :param language:        Stemming language. Default is 'en'.
        :return: trie ( dict )
        """
        # construct a trie from all chars of the keywords
        # may be thought of as finite state machine as well
        keywords = []
        root_state = {}
        for item in data:
            value = item.get('value')
            expressions = item.get('expressions', [])
            examples = item.get('examples', [])
            expressions += examples

            if not (value or expressions):
                raise ValueError("Keyword doesn't have any expressions")

            label = item.get('label', value)
            if not label:
                raise ValueError("Keyword doesn't have a label")

            if value:
                expressions.append(value)

            for expr in expressions:
                keywords.append((expr, label))

        for expression, label in keywords:
            expression = unidecode.unidecode(expression)
            words = tokenize(expression, self.should_stem, language=self.language)
            words = [str(word) for word in words]
            print(words)
            first_word = words[0]
            chars = list(first_word)
            state = root_state
            for idx, char in enumerate(chars):
                transitions = state.setdefault('transitions', {})
                state = transitions.setdefault(str(char), {})

            outputs = state.setdefault('outputs', [])
            outputs.append({
                "requires": words[1:],
                "label": label
            })

        return root_state

    def keyword_search(self, text) -> list:
        """
        Searches for keyword matches in text.
        :param text:        Text that should be searched
        :param should_stem: Boolean, whether to compare stemmed words.
                            Default is false.
        :param language:    Language for stemming. Default is 'en'.
        :return: A list of extracted entities, or an empty list.
        """
        extracted = set()
        text = unidecode.unidecode(text)
        words = tokenize(text, self.should_stem, self.language)  # TODO avoid repeating
        for idx, word in enumerate(words):
            state = self.trie
            chars = list(word)
            for char in chars:
                state = state.get('transitions', {}).get(char)
                if not state:
                    break  # unknown word
            if state:
                outputs = state.get('outputs', [])
                outputs.sort(key=lambda x: len(x.get('requires', [])), reverse=True)
                following = set(words[idx + 1:])
                for output in outputs:
                    required = set(output.get('requires', []))
                    if required & following == required:
                        extracted.add(output.get('label'))

        return [{"value": label} for label in extracted]
