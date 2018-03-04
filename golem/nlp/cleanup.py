from golem.nlp.tools.czech_stemmer import cz_stem_all
from golem.nlp.tools.porter2 import Stemmer
from golem.nlp.tools.toktok import ToktokTokenizer

tokenizer = ToktokTokenizer()

stemmers = {
    "en": Stemmer("en").stemWords,
    "cz": cz_stem_all
}


def tokenize(text: str, stemming=False, language='en'):
    """
    Tokenizes text, optionally stemming the tokens.
    :param text:        Text to be tokenized.
    :param stemming:    Boolean, enables stemming.
                        Default is false.
    :param language:    Stemming language. Default is 'en'.
    :return:
    """
    tokens = tokenizer.tokenize(text)
    if stemming:
        stemmer = stemmers.get(language)
        if not stemmer:
            raise Exception("No known stemmer for language {}!".format(language))
        tokens = [s.lower() for s in stemmer(tokens)]
    return [str(token).lower() for token in tokens]
