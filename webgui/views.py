import time

from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render

from .forms import MessageForm
from .interface import WebGuiInterface
from .models import Message


def webgui(request):
    if 'uid' in request.session:
        uid = request.session['uid']
        if request.method == 'POST':
            # message received via webgui
            msg = Message()
            msg.uid = uid
            msg.text = request.POST.get('message')
            msg.timestamp = time.time()
            if msg.text is not None and len(msg.text) > 0:
                # process message if text != null
                msg.save()
                WebGuiInterface.accept_request(msg)
            return HttpResponse()

        messages = Message.objects.filter(uid=uid).order_by('timestamp')
        context = {'uid': uid, 'messages': messages, 'form': MessageForm}
        return render(request, 'index.html', context)
    else:
        return render(request, 'welcome.html')


def do_login(request):
    if request.method == 'POST' and 'username' in request.POST:
        username = request.POST.get('username')
        uid = WebGuiInterface.make_uid(username)
        request.session['uid'] = uid
        request.session['username'] = username
        return HttpResponse()
    else:
        return HttpResponseBadRequest()


def do_logout(request):
    if 'uid' in request.session:
        WebGuiInterface.destroy_uid(request.session['uid'])
        del request.session['uid']
        del request.session['username']
    return HttpResponse()
