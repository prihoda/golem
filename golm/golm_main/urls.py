from django.conf import settings
from django.conf.urls import url, include

from core.nlp.gui.views import nlp_view
from . import views
from golm_webgui import views as webgui_views
from django.contrib.auth import views as auth_views

secret_url = settings.GOLEM_CONFIG.get('WEBHOOK_SECRET_URL')
urlpatterns = [
    url(r'^accounts/login/$', auth_views.login, name='login'),
    url(r'^golm/messenger/{}/?$'.format(secret_url),
        view=views.FacebookView.as_view(), name='messenger'),
    url(r'^golm/telegram/{}/?$'.format(secret_url),
        view=views.TelegramView.as_view(), name='telegram'),
    url(r'^golm/gactions/{}/?$'.format(secret_url),
        view=views.GActionsView.as_view(), name='gactions'),
    url(r'^golm/skype/{}/?$'.format(secret_url),
        view=views.SkypeView.as_view(), name='skype'),
    url(r'^golm/run_all_tests/?$', views.run_all_tests),
    url(r'^golm/run_test/(?P<name>[a-zA-Z0-9_\-]+)/?$', views.run_test),
    url(r'^golm/run_test_message/(?P<message>[a-zA-Z0-9 _\-]+)/?$', views.run_test_message),
    url(r'^golm/log/(?P<user_limit>[0-9]*)/?$', views.log),
    url(r'^golm/log_tests/?$', views.log_tests),
    url(r'^golm/test/?$', views.test),
    url(r'^golm/debug/?$', views.debug),
    url(r'^golm/test_record/?$', views.test_record),
    url(r'^golm/nlp/?$', nlp_view),
    url(r'^golm/users/?$', views.users_view),
    url(r'^golm/log_conversation/(?P<group_id>[a-zA-Z_0-9]*)/(?P<page>[0-9]*)/?$', views.log_conversation),
    url(r'^golm/?$', views.index),
    url(r'^dd/?$', webgui_views.webgui, name='golm_webgui'),
    url(r'^chat/', include('golm_webgui.urls'))

]
