import os
from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'visitor.settings')

app = Celery('golem')

app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

@app.on_after_configure.connect
def setup_schedule_callbacks_wrapper(sender, **kwargs):
    from core.tasks import setup_schedule_callbacks
    setup_schedule_callbacks(sender, accept_schedule_all_users_wrapper)

@app.task
def accept_schedule_all_users_wrapper(callback_name):
    from core.tasks import accept_schedule_all_users
    accept_schedule_all_users(callback_name)
