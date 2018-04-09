import json
import logging
import os
from typing import Optional
from urllib.request import Request, urlopen

import requests

GENEEA_HEADERS = {
    'content-type': 'application/json',
    'Authorization': 'user_key ' + os.environ.get('GENEEA_API_KEY', "")
}


def extract_tags(title: Optional[str], text: Optional[str]):
    """
    Extracts tags from text using Geneea web service.
    """
    if 'GENEEA_API_KEY' not in os.environ:
        return []

    message = {
        'returnTextInfo': False,
        "domain": os.environ.get("GENEEA_DOMAIN"),
        "correction": "aggressive",
        "diacritization": "yes"
    }
    if title:
        message['title'] = title.strip()
    if text:
        message['text'] = text.strip()
    content = json.dumps(message).encode('utf-8')
    req = Request('https://api.geneea.com/s2/tags', headers=GENEEA_HEADERS, data=content)
    resp_conn = urlopen(req)
    response = json.loads(resp_conn.read().decode('utf-8'))
    return response['tags']


def get_sentiment(text: str, full=False):
    """
    Gets sentiment (positive/negative) of a text using Geneea web service.
    """
    if 'GENEEA_API_KEY' not in os.environ:
        return None

    if type(text) is not str:
        raise Exception('Illegal argument, text not str')
    message = {'returnTextInfo': False, 'text': text}
    content = json.dumps(message).encode('utf8')
    req = Request('https://api.geneea.com/s2/sentiment', headers=GENEEA_HEADERS, data=content)
    conn = urlopen(req)
    resp = json.loads(conn.read().decode('utf8'))
    return resp if full else float(resp['sentiment'])


def get_correction(text: str):
    if 'GENEEA_API_KEY' not in os.environ:
        return text

    data = {
        "text": text,
        "correction": "basic",
        "diacritization": "auto",
        "language": "cs"
    }
    req = requests.post(url="https://api.geneea.com/s2/correction", headers=GENEEA_HEADERS, data=json.dumps(data))
    if req.ok:
        return req.json().get("text", "")
    logging.warning("Geneea request for correction failed with code {} reason {}".format(req.status_code, req.reason))
    return text
