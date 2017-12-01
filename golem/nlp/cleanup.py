from golem.nlp import utils
from golem.nlp.czech_stemmer import cz_stem


def tokenize(text: str, stemming=False, language='en'):
    """
    Tokenizes text, optionally stemming the tokens.
    :param text:        Text to be tokenized.
    :param stemming:    Boolean, enables stemming.
                        Default is false.
    :param language:    Stemming language. Default is cz.
    :return:
    """
    tokens = utils.get_spacy().tokenizer(text)
    if stemming:
        if language == 'cz':
            return [cz_stem(str(token), aggressive=True).lower() for token in tokens]
        elif language == 'en':
            utils.get_spacy().tagger(tokens)
            return [str(token.lemma_).lower() for token in tokens]
    return [str(token).lower() for token in tokens]
