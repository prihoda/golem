from django.conf.urls import url
from . import views
from django.conf import settings  

urlpatterns = [
    url(r'^messenger/{}/?$'.format(settings.GOLEM_CONFIG.get('WEBHOOK_SECRET_URL')), views.FacebookView.as_view()),
    url(r'^telegram/{}/?$'.format(settings.GOLEM_CONFIG.get('WEBHOOK_SECRET_URL')), views.TelegramView.as_view()),
    url(r'^run_test/(?P<name>[a-zA-Z0-9_\-]+)/?$', views.run_test),
    url(r'^run_test_message/(?P<message>[a-zA-Z0-9 _\-]+)/?$', views.run_test_message),
    url(r'^log/(?P<user_limit>[0-9]*)/?$', views.log),
    url(r'^test/?$', views.test),
    url(r'^debug/?$', views.debug),
    url(r'^test_record/?$', views.test_record),
    url(r'^log_user/(?P<uid>[a-zA-Z_0-9]*)/(?P<page>[0-9]*)/?$', views.log_user),
]

