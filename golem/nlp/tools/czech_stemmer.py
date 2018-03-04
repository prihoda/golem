#! /usr/bin/env python3.1
""" Czech stemmer
Copyright © 2010 Luís Gomes <luismsgomes@gmail.com>.
This code is released under a Creative Commons Attribution 3.0 Unported License.
https://creativecommons.org/licenses/by/3.0/

Ported from the Java implementation available at:
    http://members.unine.ch/jacques.savoy/clef/index.html

"""
import re
import sys


### FIXME VALIDATE SLOVAK CHARACTERS !!! ###

def cz_stem_all(words, aggressive=True):
    return [cz_stem(word, aggressive) for word in words]


def cz_stem(word, aggressive=False):
    if not re.match("^\\w+$", word):
        return word
    if not word.islower() and not word.istitle() and not word.isupper():
        print("warning: skipping word with mixed case: {}".format(word),
              file=sys.stderr)
        return word
    s = word.lower()  # all our pattern matching is done in lowercase
    s = _remove_case(s)
    s = _remove_possessives(s)
    if aggressive:
        s = _remove_comparative(s)
        s = _remove_diminutive(s)
        s = _remove_augmentative(s)
        s = _remove_derivational(s)
    if word.isupper():
        return s.upper()
    if word.istitle():
        return s.title()
    return s


def _remove_case(word):
    if len(word) > 7 and word.endswith("atech"):
        return word[:-5]
    if len(word) > 6:
        if word.endswith("ětem"):
            return _palatalise(word[:-3])
        if word.endswith("atům"):
            return word[:-4]
    if len(word) > 5:
        if word[-3:] in {"ech", "ich", "ích", "ého", "ěmi", "emi", "ému",
                         "ete", "eti", "iho", "ího", "ími", "imu"}:
            return _palatalise(word[:-2])
        if word[-3:] in {"ách", "ata", "aty", "ých", "ama", "ami",
                         "ové", "ovi", "ými"}:
            return word[:-3]
    if len(word) > 4:
        if word.endswith("em"):
            return _palatalise(word[:-1])
        if word[-2:] in {"es", "ém", "ím"}:
            return _palatalise(word[:-2])
        if word[-2:] in {"ům", "at", "ám", "os", "us", "ým", "mi", "ou"}:
            return word[:-2]
    if len(word) > 3:
        if word[-1] in "eiíě":
            return _palatalise(word)
        if word[-1] in "uyůaoáéý":
            return word[:-1]
    return word


def _remove_possessives(word):
    if len(word) > 5:
        if word[-2:] in {"ov", "ův"}:
            return word[:-2]
        if word.endswith("in"):
            return _palatalise(word[:-1])
    return word


def _remove_comparative(word):
    if len(word) > 5:
        if word[-3:] in {"ejš", "ějš"}:
            return _palatalise(word[:-2])
    return word


def _remove_diminutive(word):
    if len(word) > 7 and word.endswith("oušek"):
        return word[:-5]
    if len(word) > 6:
        if word[-4:] in {"eček", "éček", "iček", "íček", "enek", "ének",
                         "inek", "ínek"}:
            return _palatalise(word[:-3])
        if word[-4:] in {"áček", "aček", "oček", "uček", "anek", "onek",
                         "unek", "ánek"}:
            return _palatalise(word[:-4])
    if len(word) > 5:
        if word[-3:] in {"ečk", "éčk", "ičk", "íčk", "enk", "énk",
                         "ink", "ínk"}:
            return _palatalise(word[:-3])
        if word[-3:] in {"áčk", "ačk", "očk", "učk", "ank", "onk",
                         "unk", "átk", "ánk", "ušk"}:
            return word[:-3]
    if len(word) > 4:
        if word[-2:] in {"ek", "ék", "ík", "ik"}:
            return _palatalise(word[:-1])
        if word[-2:] in {"ák", "ak", "ok", "uk"}:
            return word[:-1]
    if len(word) > 3 and word[-1] == "k":
        return word[:-1]
    return word


def _remove_augmentative(word):
    if len(word) > 6 and word.endswith("ajzn"):
        return word[:-4]
    if len(word) > 5 and word[-3:] in {"izn", "isk"}:
        return _palatalise(word[:-2])
    if len(word) > 4 and word.endswith("ák"):
        return word[:-2]
    return word


def _remove_derivational(word):
    if len(word) > 8 and word.endswith("obinec"):
        return word[:-6]
    if len(word) > 7:
        if word.endswith("ionář"):
            return _palatalise(word[:-4])
        if word[-5:] in {"ovisk", "ovstv", "ovišt", "ovník"}:
            return word[:-5]
    if len(word) > 6:
        if word[-4:] in {"ásek", "loun", "nost", "teln", "ovec", "ovík",
                         "ovtv", "ovin", "štin"}:
            return word[:-4]
        if word[-4:] in {"enic", "inec", "itel"}:
            return _palatalise(word[:-3])
    if len(word) > 5:
        if word.endswith("árn"):
            return word[:-3]
        if word[-3:] in {"ěnk", "ián", "ist", "isk", "išt", "itb", "írn"}:
            return _palatalise(word[:-2])
        if word[-3:] in {"och", "ost", "ovn", "oun", "out", "ouš",
                         "ušk", "kyn", "čan", "kář", "néř", "ník",
                         "ctv", "stv"}:
            return word[:-3]
    if len(word) > 4:
        if word[-2:] in {"áč", "ač", "án", "an", "ář", "as"}:
            return word[:-2]
        if word[-2:] in {"ec", "en", "ěn", "éř", "íř", "ic", "in", "ín",
                         "it", "iv"}:
            return _palatalise(word[:-1])
        if word[-2:] in {"ob", "ot", "ov", "oň", "ul", "yn", "čk", "čn",
                         "dl", "nk", "tv", "tk", "vk"}:
            return word[:-2]
    if len(word) > 3 and word[-1] in "cčklnt":
        return word[:-1]
    return word


def _palatalise(word):
    if word[-2:] in {"ci", "ce", "či", "če"}:
        return word[:-2] + "k"

    if word[-2:] in {"zi", "ze", "ži", "že"}:
        return word[:-2] + "h"

    if word[-3:] in {"čtě", "čti", "čtí"}:
        return word[:-3] + "ck"

    if word[-3:] in {"ště", "šti", "ští"}:
        return word[:-3] + "sk"
    return word[:-1]
