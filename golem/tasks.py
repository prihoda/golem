from celery import shared_task
from celery.utils.log import get_task_logger
import traceback
from golem.core.interfaces.all import create_from_name
from golem.core.persistence import get_redis
from celery.task.schedules import crontab
from django.conf import settings
import time

logger = get_task_logger(__name__)

@shared_task
def accept_user_message(interface_name, uid, raw_message):
    from golem.core.dialog_manager import DialogManager
    print("Accepting message from {}: {}".format(uid, raw_message))
    interface = create_from_name(interface_name)
    dialog = DialogManager(uid=uid, interface=interface)
    parsed = interface.parse_message(raw_message)
    _process_message(dialog, parsed)

def setup_schedule_callbacks(sender, callback):
    callbacks = settings.GOLEM_CONFIG.get('SCHEDULE_CALLBACKS')
    if not callbacks:
        return

    for name in callbacks:
        params = callbacks[name]
        print('Scheduling task {}: {}'.format(name, params))
        if isinstance(params, dict):
            cron = crontab(**params)
        elif isinstance(params, int):
            cron = params
        else:
            raise Exception('Specify either number of seconds or dict of celery crontab params (hour, minute): {}'.format(params))
        sender.add_periodic_task(   
            cron,
            callback.s(name),
        )
        print(' Scheduled for {}'.format(cron))

def accept_schedule_all_users(callback_name):
    print('Accepting scheduled callback {}'.format(callback_name))
    db = get_redis()
    interface_names = db.hgetall('session_interface')
    for uid in interface_names:
        interface_name = interface_names[uid].decode('utf-8')
        accept_schedule_callback(interface_name, uid.decode('utf-8'), callback_name)

@shared_task
def accept_schedule_callback(interface_name, uid, callback_name):
    from golem.core.dialog_manager import DialogManager
    db = get_redis()
    active_time = float(db.hget('session_active', uid).decode('utf-8'))
    inactive_seconds = time.time() - active_time
    interface = create_from_name(interface_name)
    print('{} from {} was active {}'.format(uid, interface, active_time))
    parsed = {
        'type' : 'schedule',
        'entities' : {
            'intent' : '_schedule',
            '_inactive_seconds' : inactive_seconds,
            '_callback_name' : callback_name
        }
    }
    dialog = DialogManager(uid=uid, interface=interface)
    _process_message(dialog, parsed)

@shared_task
def accept_inactivity_callback(interface_name, uid, context_counter, callback_name, inactive_seconds):
    from golem.core.dialog_manager import DialogManager
    interface = create_from_name(interface_name)
    dialog = DialogManager(uid=uid, interface=interface)

    # User has sent a message, cancel inactivity callback
    if dialog.context.counter != context_counter:
        return

    parsed = {
        'type' : 'schedule',
        'entities' : {
            'intent' : '_inactive',
            '_inactive_seconds' : inactive_seconds,
            '_callback_name' : callback_name
        }
    }

    _process_message(dialog, parsed)

def _process_message(dialog, parsed):
    try:
        dialog.process(parsed['type'], parsed['entities'])
    except Exception as e:
        print("!!!!!!!!!!!!!!!! EXCEPTION AT MESSAGE QUEUE !!!!!!!!!!!!!!!", e)
        traceback.print_exc()
        dialog.logger.log_error(exception=e, state=dialog.current_state_name)