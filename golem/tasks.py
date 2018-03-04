import logging
import time
import traceback

from celery import shared_task
from celery.task.schedules import crontab
from celery.utils.log import get_task_logger
from django.conf import settings

from golem.core import message_logger  # this should register the celery log task
from golem.core.interfaces.all import create_from_name, uid_to_interface_name
from golem.core.persistence import get_redis

logger = get_task_logger(__name__)


@shared_task
def accept_user_message(interface_name, uid, raw_message, chat_id=None):
    from golem.core.dialog_manager import DialogManager
    print("Accepting message, uid {}, chat_id {}, message: {}".format(uid, chat_id, raw_message))
    interface = create_from_name(interface_name)
    prefixed_uid = interface.prefix + '_' + uid
    if chat_id:
        prefixed_chat_id = interface.prefix + '_' + chat_id
    else:
        prefixed_chat_id = None

    dialog = DialogManager(uid=prefixed_uid, chat_id=prefixed_chat_id, interface=interface)
    parsed = interface.parse_message(raw_message)
    _process_message(dialog, parsed)

    should_log_messages = settings.GOLEM_CONFIG.get('should_log_messages', False)

    if should_log_messages and 'text' in raw_message:
        text = raw_message['text']
        message_logger.on_message.delay(prefixed_uid, prefixed_chat_id, text, dialog, from_user=True)


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
            raise Exception(
                'Specify either number of seconds or dict of celery crontab params (hour, minute): {}'.format(params))
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
def accept_schedule_callback(interface_name, uid, callback_name, chat_id=None):
    from golem.core.dialog_manager import DialogManager
    db = get_redis()
    active_time = float(db.hget('session_active', uid).decode('utf-8'))
    inactive_seconds = time.time() - active_time
    interface = create_from_name(interface_name)
    print('{} from {} was active {}'.format(uid, interface, active_time))
    parsed = {
        'type': 'schedule',
        'entities': {
            'intent': '_schedule',
            '_inactive_seconds': inactive_seconds,
            '_callback_name': callback_name
        }
    }
    dialog = DialogManager(uid=uid, interface=interface, chat_id=chat_id)
    _process_message(dialog, parsed)


@shared_task
def accept_inactivity_callback(interface_name, uid, chat_id, context_counter, callback_name, inactive_seconds):
    from golem.core.dialog_manager import DialogManager
    interface = create_from_name(interface_name)
    dialog = DialogManager(uid=uid, chat_id=chat_id, interface=interface)

    # User has sent a message, cancel inactivity callback
    if dialog.context.counter != context_counter:
        return

    parsed = {
        'type': 'schedule',
        'entities': {
            'intent': '_inactive',
            '_inactive_seconds': inactive_seconds,
            '_callback_name': callback_name
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


@shared_task
def fake_move_to_state(uid: str, chat_id: str, state: str, entities=()):
    if not chat_id:
        # find last chat for the uid and move its state
        redis = get_redis()
        bytes = redis.get('last_chat_id_{}'.format(str(uid)))
        chat_id = bytes.decode()
    if not (chat_id and state):
        logging.warning('Cannot move to state {} for chat {}'.format(state, chat_id))
        return

    uid, chat_id, state = str(uid), str(chat_id), str(state)
    from golem.core.dialog_manager import DialogManager
    logging.debug("Moving chat id {} to state {}".format(chat_id, state))
    interface = create_from_name(uid_to_interface_name(chat_id))
    dialog = DialogManager(uid=uid, interface=interface, chat_id=chat_id)
    msg_data = {'_state': state}
    for k, v in entities:
        msg_data[k] = [{"value": v}]
    dialog.process('postback', msg_data)
