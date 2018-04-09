# Based on: http://norvig.com/spell-correct.html


def nearest_word(word, glove):
    corrections = known(word, glove)
    if corrections:
        return min(corrections, key=lambda x: distance(x, word))
    return None


def known(word, glove):
    edits_1 = edits(word)
    edits_2 = []  # (e2 for e1 in edits_1 for e2 in edits(e1))
    return set(w for w in edits_1.union(edits_2) if glove.contains(w))


def distance(m, n):  # TODO something more clever
    score = 0
    for i in range(min(len(m), len(n))):
        score += abs(ord(m[i]) - ord(n[i]))
    score += (len(m) - len(n)) ** 2
    return score


def edits(word):  # TODO something better
    letters = '1234567890aábcčdďeéěfghchiíjklmnňoópqrřsštťuúůvwxyýzž'
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    deletes = [L + R[1:] for L, R in splits if R]
    transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
    replaces = [L + c + R[1:] for L, R in splits if R for c in letters]
    inserts = [L + c + R for L, R in splits for c in letters]
    edited_1 = set(deletes + transposes + replaces + inserts)
    return edited_1


similar_letters = {
    "a": "ásdzxqw",
    "b": "vnfghj",
    "c": "čxdfv",
    "d": "ďswerfxc",
    "e": "éwsdfr",
    "f": "rdcvgt",
    "g": "tfvbht",
    "h": "ygbnju",
    "i": "íujklo",
    "j": "uhnmki",
    "k": "ijmlo",
    "l": "ĺľpokmů",
    "m": "njkl",
    "n": "ňmjhb",
    "o": "óôiklp",
    "p": "olúô",
    "q": "asw",
    "r": "ŕředfgt",
    "s": "šazxdewq",
    "t": "ťrfgy",
    "u": "úůhjki",
    "v": "cfgb",
    "w": "qasde",
    "x": "zsdc",
    "y": "ýtghuj",
    "z": "žasxcd"
}
