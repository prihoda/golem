from core.nlp.cleanup import tokenize


# TODO remove character accents

def prepare_keywords(data, should_stem=False, language='en') -> dict:
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
        words = tokenize(expression, should_stem, language=language)
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


def keyword_search(text, trie, should_stem=False, language='en') -> list:
    """
    Searches for keyword matches in text.
    :param text:        Text that should be searched
    :param trie:        Trie containing the keyword representation
    :param should_stem: Boolean, whether to compare stemmed words.
                        Default is false.
    :param language:    Language for stemming. Default is 'en'.
    :return: A list of extracted entities, or an empty list.
    """
    extracted = []
    words = tokenize(text, should_stem, language)
    for idx, word in enumerate(words):
        state = trie
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
                    extracted.append({
                        "value": output.get('label')
                    })
    return extracted
