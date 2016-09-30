import sys
import traceback
import json
import requests
from golem.message_queue import MessageQueue
from golem.serialize import json_serialize,json_deserialize
import datetime
from .responses import TextMessage,SenderActionMessage,MessageElement,ThreadSetting
from wit import Wit
import dateutil.parser
from datetime import timedelta
import re

timestamp2datetime = lambda t: datetime.datetime.fromtimestamp(int(t) / 1000)

class FacebookInterface():

    message_queue = None

    @staticmethod
    def init_queue(config):
        FacebookInterface.message_queue = MessageQueue(config=config)
        FacebookInterface.config = config

    # Post function to handle Facebook messages
    @staticmethod
    def accept_request(request):
        # Facebook recommends going through every entry since they might send
        # multiple messages in a single call during high load.
        for entry in request['entry']:
            for raw_message in entry['messaging']:
                ts_datetime = timestamp2datetime(raw_message['timestamp'])
                crr_datetime = datetime.datetime.now()
                diff = crr_datetime - ts_datetime
                if diff.total_seconds() < 30:
                    # print("MSG FB layer GET FB:")
                    print('INCOMING RAW FB MESSAGE:', raw_message)
                    uid = FacebookInterface.fbid_to_uid(raw_message['sender']['id'])
                    # Confirm accepted message
                    FacebookInterface.post_message(uid, SenderActionMessage('mark_seen'))
                    # Add it to the message queue
                    FacebookInterface.add_to_queue((uid, raw_message, FacebookInterface))
                elif raw_message.get('timestamp'):
                    print("Delay too big, ignoring message!")
                    print(raw_message)

    @staticmethod
    def add_to_queue(work):
        FacebookInterface.message_queue.queue.put(work)

    @staticmethod
    def uid_to_fbid(uid):
        return uid.split('_',maxsplit=1)[1] # uid has format fb_{number}

    @staticmethod
    def fbid_to_uid(fbid):
         return 'fb_'+fbid

    @staticmethod
    def post_message(uid, response):
        if isinstance(response, list):
            for resp in response:
                FacebookInterface.post_message(uid, resp)
            return

        try:
            if isinstance(response, str):
                response = TextMessage(text=response)

            # print(payload, type_)
            if isinstance(response, MessageElement):
                fbid = FacebookInterface.uid_to_fbid(uid)
                response_dict = response.to_message(fbid)
                graph_request_mode = "messages"
            elif isinstance(response, ThreadSetting):
                response_dict = response.to_response()
                print('SENDING SETTING:', response_dict)
                graph_request_mode = "thread_settings"
            else:
                raise ValueError('Error: Invalid message type: {}: {}'.format(type(response), response))
            
            prefix_post_message_url = 'https://graph.facebook.com/v2.6/me/'
            token = FacebookInterface.config['FB_PAGE_TOKEN']
            post_message_url = prefix_post_message_url+graph_request_mode+'?access_token='+token
            # print("POST", post_message_url)
            r = requests.post(post_message_url,
                                   headers={"Content-Type": "application/json"},
                                   data=json.dumps(response_dict, default=json_serialize))
            if r.status_code != 200:
                print('ERROR: MESSAGE REFUSED: ', response_dict)
                print('ERROR: ', r.text)
        except Exception as err:
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! EXCEPTION FB POST MESSAGE", err)
            traceback.print_exc(file=sys.stdout)

    @staticmethod
    def send_settings(settings):
        FacebookInterface.post_message(None, settings)

    @staticmethod
    def processing_start(uid):
        # Show typing animation
        FacebookInterface.post_message(uid, SenderActionMessage('typing_on'))

    @staticmethod
    def parse_message(raw_message, num_tries=1):
        if 'postback' in raw_message:
            payload = json.loads(raw_message['postback']['payload'], object_hook=json_deserialize)
            payload['_message_text'] = [{'value':None}]
            return {'entities': payload, 'type':'postback'}
        elif 'message' in raw_message:
            if 'attachments' in raw_message['message']:
                attachments = raw_message['message']['attachments']
                return FacebookInterface.parse_attachments(attachments)
            if 'quick_reply' in raw_message['message']:
                payload = json.loads(raw_message['message']['quick_reply'].get('payload'), object_hook=json_deserialize)
                if payload:
                    payload['_message_text'] = [{'value':raw_message['message']['text']}]
                    return {'entities': payload, 'type':'postback'}
            if 'text' in raw_message['message']:
                return FacebookInterface.parse_text_message(raw_message['message']['text'])
        return {'type':'undefined'}

    @staticmethod
    def parse_attachments(attachments):
        entities = {
            'current_location' : [],
            'attachment' : [],
            '_message_text' : [{'value':None}]
        }
        for attachment in attachments:
            if 'coordinates' in attachment['payload']:
                coordinates = attachment['payload']['coordinates']
                entities['current_location'].push({'value':coordinates})
            if 'url' in attachment['payload']:
                url = attachment['payload']['url']
                # TODO: add attachment type by extension
                entities['attachment'].append({'value':url})
        return {'entities' : entities, 'type':'message'}

    @staticmethod
    def parse_text_message(text, num_tries=1):
        try:
            wit_client = Wit(access_token=FacebookInterface.config['WIT_TOKEN'], actions={})
            wit_parsed = wit_client.message(text)
            print(wit_parsed)
        except Exception as e:
            print('WIT ERROR: ', e)
            # try to parse again 5 times
            if num_tries > 5:
                raise
            else:
                return FacebookInterface.parse_text_message(text, num_tries=num_tries+1)

        entities = wit_parsed['entities']
        append = {}
        for entity,values in entities.items():
            # parse datetimes to date_intervals
            if entity == 'datetime':
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
        return {'entities':entities, 'type':'message'}

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

def format_date_interval(from_date, to_date, grain):
    tzinfo = from_date.tzinfo
    now = date_now(tzinfo)
    today = date_today(tzinfo)
    this_week = date_this_week(tzinfo)
    next_week = this_week + timedelta(days=7)
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

    if diff_hours<=25: # (25 to incorporate possible time change)
        digit = from_date.day % 10
        date = 'the {}{}'.format(from_date.day, 'st' if digit==1 else ('nd' if digit==2 else 'th'))
        return date if from_date.month==now.month else date+' '+from_date.strftime('%B')
    return 'these dates'
