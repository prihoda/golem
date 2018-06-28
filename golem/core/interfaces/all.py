import logging

def get_interfaces():
    """
    :returns: List of all registered chat interface classes.
    """
    from golem.webgui.interface import WebGuiInterface
    from golem.core.interfaces.facebook import FacebookInterface
    from golem.core.interfaces.telegram import TelegramInterface
    from golem.core.interfaces.microsoft import MicrosoftInterface
    from golem.core.interfaces.google import GoogleActionsInterface
    from golem.core.interfaces.test import TestInterface
    return [WebGuiInterface, FacebookInterface, TelegramInterface, MicrosoftInterface, GoogleActionsInterface,
                         TestInterface]


def create_from_name(name):
    ifs = get_interfaces()
    for interface in ifs:
        if interface.name == name:
            return interface


def create_from_prefix(prefix):
    ifs = get_interfaces()
    for interface in ifs:
        if interface.prefix == prefix:
            return interface


def create_from_chat_id(chat_id):
    prefix = chat_id.split("_", maxsplit=1)[0]
    return create_from_prefix(prefix)


def init_webhooks():
    """
    Registers webhooks for telegram messages.
    """
    logging.debug('Trying to register telegram webhook')
    try:
        from golem.core.interfaces.telegram import TelegramInterface
        TelegramInterface.init_webhooks()
    except Exception as e:
        logging.exception('Couldn\'t init webhooks')


def uid_to_interface_name(uid: str):
    prefix = str(uid).split('_')[0]

    for i in get_interfaces():
        if i.prefix == prefix:
            return i.name
    raise Exception('No interface for {}'.format(uid))
