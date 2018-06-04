from django.conf.urls import url, include

from golm_webgui import views as webgui_views
from django.contrib.auth import views as auth_views

urlpatterns = [
    url(r'^accounts/login/$', auth_views.login, name='login'),
    url(r'^$', webgui_views.webgui, name='golm_webgui'),
    url(r'^chat/', include('golm_webgui.urls')),
    url(r'^golm/', include('golm_admin.urls'))
]
