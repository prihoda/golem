from wit import Wit
import dateutil.parser
import re
from datetime import timedelta
import datetime
import emoji
from .persistence import get_redis
import pickle
from django.conf import settings  
from dateutil.relativedelta import relativedelta
from django.utils import timezone
import json

def teach_wit(wit_token, entity, values, doc=""):
    import requests
    print('*** TEACHING WIT ***')
    params = {'v':'20170307'}
    print('Inserting values of {}'.format(entity))
    rsp = requests.request(
        'PUT',
        'https://api.wit.ai/entities/'+entity,
        headers={
            'authorization': 'Bearer ' + wit_token,
            'accept': 'application/json'
        },
        params=params,
        json={'doc':doc, 'values':values}
    )
    if rsp.status_code > 200:
        raise ValueError('Wit responded with status: ' + str(rsp.status_code) +
                       ' (' + rsp.reason + '): ' + rsp.text)
    json = rsp.json()
    if 'error' in json:
        raise ValueError('Wit responded with an error: ' + json['error'])

def clear_wit_cache():
    cache = settings.GOLEM_CONFIG.get('WIT_CACHE')
    if cache:
        print('Clearing Wit cache...')
        db = get_redis()    
        db.delete('wit_cache')
        
clear_wit_cache()

def parse_text_message(text, num_tries=1):
    wit_token = settings.GOLEM_CONFIG.get('WIT_TOKEN')
    if not wit_token:
        return {'type':'message','entities': {'_message_text' : {'value':text}}}

    cache_key = 'wit_cache'
    cache = settings.GOLEM_CONFIG.get('WIT_CACHE')

    if cache:
        db = get_redis()
        if db.hexists('wit_cache', text):
            parsed = pickle.loads(db.hget('wit_cache', text))
            print('Got cached wit key: "{}" = {}'.format(cache_key, parsed))
            return parsed

    try:
        wit_client = Wit(access_token=wit_token, actions={})
        wit_parsed = wit_client.message(text)
        #print(wit_parsed)
    except Exception as e:
        print('WIT ERROR: ', e)
        # try to parse again 5 times
        if num_tries > 5:
            raise
        else:
            return parse_text_message(text, num_tries=num_tries+1)

    entities = wit_parsed['entities']
    print('WIT ENTITIES:', entities)
    append = parse_additional_entities(text)
    for entity,values in entities.items():

        for value in values:
            # parse string metadata from Wit into a dict
            metadata = value.get('metadata')
            if metadata and isinstance(metadata, str):
                value['metadata'] = json.loads(metadata)

        # parse datetimes to date_intervals
        if entity == 'datetime':
            '''
            Output example:
                Q: next_week: (datetime.datetime(2016, 11, 21, 0, 0, tzinfo=tzoffset(None, 3600)), datetime.datetime(2016, 11, 28, 0, 0, tzinfo=tzoffset(None, 3600)))
                Q: tomorrow: (datetime.datetime(2016, 11, 18, 0, 0, tzinfo=tzoffset(None, 3600)), datetime.datetime(2016, 11, 19, 0, 0, tzinfo=tzoffset(None, 3600)))
                Q: tonight: (datetime.datetime(2016, 11, 17, 18, 0, tzinfo=tzoffset(None, 3600)), datetime.datetime(2016, 11, 18, 0, 0, tzinfo=tzoffset(None, 3600)))
                Q: at weekend: (datetime.datetime(2016, 11, 18, 18, 0, tzinfo=tzoffset(None, 3600)), datetime.datetime(2016, 11, 21, 0, 0, tzinfo=tzoffset(None, 3600)))
            '''
            append['date_interval'] = []
            for value in values:
                try:
                    if value['type'] == 'interval':
                        date_from = dateutil.parser.parse(value['from']['value'])
                        date_to = dateutil.parser.parse(value['to']['value'])
                        grain = value['from']['grain']
                    else:
                        grain = value['grain']
                        date_from = dateutil.parser.parse(value['value'])
                        if grain == 'week' and date_from == date_this_week(date_from.tzinfo):
                            # change "this week" to next 7 days
                            date_from = timezone.now()
                            date_to = date_from + timedelta(days=7)
                        date_to = date_from + timedelta_from_grain(grain)
                        if 'datetime' not in append:
                            append['datetime'] = []
                        append['datetime'].append({'value':date_from, 'grain':grain})
                    formatted = format_date_interval(date_from, date_to, grain)
                    append['date_interval'].append({'value':(date_from, date_to), 'grain':grain, 'formatted':formatted})
                except ValueError as e:
                    print('Error parsing date {}: {}', value, e)

    if 'datetime' in entities:
        del entities['datetime']

    for (entity, value) in re.findall(re.compile(r'/([^/]+)/([^/]+)/'), text):
        if not entity in append:
            append[entity] = []
        append[entity].append({'value': value})

    # add all new entity values
    for entity,values in append.items():
        if not entity in entities:
            entities[entity] = []
        entities[entity] += values

    entities['_message_text'] = [{'value':text}]

    parsed = {'entities':entities, 'type':'message'}
    
    if cache and 'date_interval' not in entities:
        print('Caching wit key: {} = {}'.format(text, parsed))
        db.hset('wit_cache', text, pickle.dumps(parsed))
    return parsed

def parse_additional_entities(text):
    entities = {}
    chars = {':)':':slightly_smiling_face:', '(y)':':thumbs_up_sign:', ':(':':disappointed_face:',':*':':kissing_face:',':O':':face_with_open_mouth:',':D':':grinning_face:','<3':':heavy_black_heart:️',':P':':face_with_stuck-out_tongue:'}
    demojized = emoji.demojize(text)
    char_emojis = re.compile(r'(' + '|'.join(chars.keys()).replace('(','\(').replace(')','\)').replace('*','\*') + r')')
    demojized = char_emojis.sub(lambda x: chars[x.group()], demojized)
    if demojized != text:
        match = re.compile(r':([a-zA-Z_0-9]+):')
        for emoji_name in re.findall(match, demojized):
            if 'emoji' not in entities:
                entities['emoji'] = []
            entities['emoji'].append({'value':emoji_name})
        #if re.match(match, demojized):
        #    entities['intent'].append({'value':'emoji'})
    return entities

def timedelta_from_grain(grain):
    if grain=='second':
        return timedelta(seconds=1)
    if grain=='minute':
        return timedelta(minutes=1)
    if grain=='hour':
        return timedelta(hours=1)
    if grain=='day':
        return timedelta(days=1)
    if grain=='week':
        return timedelta(days=7)
    if grain=='month':
        return timedelta(days=31)
    if grain=='year':
        return timedelta(days=365)
    return timedelta(days=1)

def date_now(tzinfo):
    return datetime.datetime.now(tzinfo)

def date_today(tzinfo):
    return date_now(tzinfo).replace(hour=0, minute=0, second=0, microsecond=0)

def date_this_week(tzinfo):
    today = date_today(tzinfo)
    return today - timedelta(days=today.weekday())

def date_this_month(tzinfo):
    today = date_today(tzinfo)
    return today - timedelta(days=today.day-1)

def format_date_interval(from_date, to_date, grain):
    tzinfo = from_date.tzinfo
    now = date_now(tzinfo)
    today = date_today(tzinfo)
    this_week = date_this_week(tzinfo)
    next_week = this_week + timedelta(days=7)
    this_month = date_this_month(tzinfo)
    next_month = date_this_month(tzinfo) + relativedelta(months=1)
    print('This month: ', this_month)
    print('Next month: ', next_month)

    diff_hours = (to_date-from_date).total_seconds() / 3600
    print('Diff hours: %s' % diff_hours)

    if grain in ['second','minute'] and (now-from_date).total_seconds() < 60*5:
        return 'now'

    for i in range(0,6):
        # if the dates are within the i-th day
        if from_date >= today+timedelta(days=i) and to_date <= today+timedelta(days=i+1):
            if i==0:
                day = 'today'
            elif i==1:
                day = 'tomorrow'
            else:
                day = '%s' % from_date.strftime("%A")
            if from_date.hour >= 17:
                return 'this evening' if i==0 else day+' evening'
            if from_date.hour >= 12:
                return 'this afternoon' if i==0 else day+' afternoon'
            if to_date.hour >= 0 and to_date.hour < 13 and to_date.hour>0:
                return 'this morning' if i==0 else day+' morning'
            return day

    if from_date == this_week and to_date == next_week:
        return 'this week'

    if from_date == next_week and to_date == next_week+timedelta(days=7):
        return 'next week'

    if from_date == this_month and to_date == next_month:
        return 'this month'

    if diff_hours<=25: # (25 to incorporate possible time change)
        digit = from_date.day % 10
        date = 'the {}{}'.format(from_date.day, 'st' if digit==1 else ('nd' if digit==2 else 'th'))
        return date if from_date.month==now.month else date+' '+from_date.strftime('%B')
    return 'these dates'
