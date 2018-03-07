import logging
import os

import requests
from django.conf import settings

duckling_url = settings.NLP_CONFIG.get('DUCKLING_URL')
language = settings.NLP_CONFIG.get('DUCKLING_LANGUAGE', 'en_US')

def get(text):
    """
    Makes a duckling request for text entities.
    :param text: Text to be parsed by Duckling.
    :return: Json returned by Duckling. Empty on error.
    """
    if duckling_url:
        logging.info('Duckling request')
        payload = {
            'locale': language,
            'text': text
        }
        try:
            resp = requests.post(duckling_url + "/parse", data=payload)
            if resp.status_code == 200:
                js = resp.json()
                print('Duckling:', js)
                if js is not None:
                    return to_entities(js)
            else:
                resp.raise_for_status()
        except Exception as ex:
            logging.exception('Exception @ Duckling')
    return {}


def to_entities(js):
    """Converts duckling output to the correct format."""
    entities = {}
    for entity in js:
        key, value = entity['dim'], entity['value']
        if key == 'time': key = 'datetime'
        if key not in entities:
            entities[key] = []
        entities[key].append(value)
    return entities
