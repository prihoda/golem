import logging

import os
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render

from core.nlp.utils import get_entity_names, data_dir
import json


def nlp_view(request):
    context = {'entities': get_entity_names()}
    return render(request, 'nlp/nlp.html', context)


def training_view(request, entity):
    if not entity or not isinstance(entity, str):
        logging.warning("Invalid entity")
        return HttpResponseBadRequest()

    path = os.path.join(data_dir(), 'training_data', entity + '.json')
    with open(path) as f:
        js = json.load(f)
        strategy = js.get("strategy")
        if strategy == "trait":
            return trait_training_view(request, entity, js)
        elif strategy == "keywords":
            return keywords_training_view(request, entity, js)


def trait_training_view(request, entity, js):
    return HttpResponse()


def keywords_training_view(request, entity, js):
    data = js.get("data", [])
    return render(request, "nlp/keywords.html")
