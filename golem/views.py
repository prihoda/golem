from django.http.response import HttpResponse, JsonResponse
from django.template import loader
from golem.core.persistence import get_redis,get_elastic
from golem.core.tests import ConversationTest, ConversationTestRecorder, ConversationTestException, TestLog, UserTextMessage
import json
import time
import traceback
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import generic
from django.conf import settings  
from golem.core.interfaces.telegram import TelegramInterface
from golem.core.interfaces.facebook import FacebookInterface

class FacebookView(generic.View):

    def get(self, request, *args, **kwargs):
        if self.request.GET.get('hub.verify_token') == settings.GOLEM_CONFIG.get('WEBHOOK_VERIFY_TOKEN'):
            return HttpResponse(self.request.GET['hub.challenge'])
        else:
            return HttpResponse('Error, invalid token')

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return generic.View.dispatch(self, request, *args, **kwargs)

    # Post function to handle Facebook messages
    def post(self, request, *args, **kwargs):
        # Converts the text payload into a python dictionary
        request_body = json.loads(self.request.body.decode('utf-8'))
        FacebookInterface.accept_request(request_body)
        return HttpResponse()


class TelegramView(generic.View):

    def get(self, request, *args, **kwargs):
        request_body = json.loads(self.request.body.decode('utf-8'))
        from pprint import pprint
        pprint(request_body)
        return HttpResponse()

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return generic.View.dispatch(self, request, *args, **kwargs)

    # Post function to handle Telegram messages
    def post(self, request, *args, **kwargs):
        # Converts the text payload into a python dictionary
        request_body = json.loads(self.request.body.decode('utf-8'))
        TelegramInterface.accept_request(request_body)
        return HttpResponse()



def test(request):

    with open('test/results.json') as infile:
        tests = json.load(infile)

    status = 'passed'
    avg = {'duration':0, 'total':0, 'init':0, 'parsing':0, 'processing':0}
    passed = 0
    for test in tests:
        result = test['result']
        if result['status'] == 'passed':
            passed += 1
            avg['duration'] += result['duration']
            avg['total'] += result['report']['avg']['total']
            avg['init'] += result['report']['avg']['init']
            avg['parsing'] += result['report']['avg']['parsing']
            avg['processing'] += result['report']['avg']['processing']
        elif status != 'exception':
            status = result['status']

    if passed > 0:
        for key in avg:
            avg[key] = avg[key] / passed

    context = {'tests':tests, 'avg':avg, 'status':status}
    template = loader.get_template('golem/test.html')
    return HttpResponse(template.render(context, request))


def run_test(request, name):
    import importlib
    import imp

    module = importlib.import_module('test.tests.'+name)
    imp.reload(module)
    return _run_test_actions(module.actions)

def run_test_message(request, message):
    return _run_test_actions([UserTextMessage(message)])


def _run_test_actions(actions):
    test = ConversationTest()
    start_time = time.time()
    report = None
    try:
      report = test.run(actions)
    except Exception as e:
      log = TestLog.get()
      fatal = not isinstance(e, ConversationTestException)
      if fatal:
        trace = traceback.format_exc()
        print(trace)
        log.append(trace)
      return JsonResponse(data={'status': 'exception' if fatal else 'failed', 'log':log, 'message':str(e), 'report':report})

    elapsed_time = time.time() - start_time
    return JsonResponse(data={'status': 'passed', 'log':TestLog.get(), 'duration':elapsed_time, 'report':report})

def test_record(request):
    response = ConversationTestRecorder.get_result()

    response = HttpResponse(content_type='application/force-download', content=response) #
    response['Content-Disposition'] = 'attachment; filename=mytest.py'
    return response

def log(request, user_limit):

    user_limit = int(user_limit) if user_limit else 100
    es = get_elastic()
    if not es:
        return HttpResponse('not able to connect to elasticsearch')

    res = es.search(index="message-log", doc_type='message', body={
       "size": 0,
       "aggs": {
          "uids": {
             "terms": {
                "field": "uid",
                "size": 1000
             },
             "aggs": {
                "created": {
                   "max": {
                      "field": "created"
                   }
                }
             }
          }
       }
    })
    uids = []
    for bucket in res['aggregations']['uids']['buckets']:
        uid = bucket['key']
        last_time = bucket['created']['value']
        uids.append({'uid':uid, 'last_time':last_time})

    uids = sorted(uids, key=lambda uid: -uid['last_time'])[:user_limit]


    res = es.search(index="message-log", doc_type='user', body={
       "size" : user_limit,
       "query": {
            "bool" : {
                "filter" : {
                    "terms" : { "uid" : [u['uid'] for u in uids] }
                }
            }
        }
    })

    user_map = {user['_source']['uid']: user['_source'] for user in res['hits']['hits']}
    users = [user_map[u['uid']] if u['uid'] in user_map else {'uid':u['uid']} for u in uids]

    context = {
        'users': users
    }

    print(users)
    template = loader.get_template('golem/log.html')
    return HttpResponse(template.render(context,request))

def log_user(request, uid, page=1):
    page = int(page) if page else 1
    es = get_elastic()
    if not es:
        return HttpResponse()

    res = es.search(index="message-log", doc_type='message', body={
       "size": 50,
       "from" : 50*(page-1),
       "query": {
            "bool" : {
                "filter" : {
                    "term" : { "uid" : uid }
                }
            }
        },
       "sort": {
          "created": {
             "order": "desc"
          }
       }
    })

    messages = []
    previous = None
    for hit in res['hits']['hits'][::-1]:
        message = hit['_source']
        message['switch'] = previous != message['is_user']
        previous = message['is_user']
        response = message.get('response')
        elements = response.get('elements') if response else None
        if elements:
            message['elementWidth'] = len(elements)*215;
        message['json'] = json.dumps(message)
        messages.append(message)

    context = {'messages': messages}
    template = loader.get_template('golem/log_user.html')
    return HttpResponse(template.render(context,request))

def debug(request):
    FacebookInterface.accept_request({'entry':[{'messaging':[{'message': {'seq': 356950, 'mid': 'mid.$cAAPhQrFuNkFibcXMZ1cPICEB8YUn', 'text': 'hi'}, 'recipient': {'id': '1092102107505462'}, 'timestamp': 1595663674471, 'sender': {'id': '1046728978756975'}}]}]})

    return HttpResponse('done')