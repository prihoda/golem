import logging

interfaces = []


def register_chat_interface(interface):
    """
    Registers a chat interface.
    :param interface: Class of the interface to register.
                      See core.interfaces for reference.
    """
    interfaces.append(interface)


def get_interfaces():
    """
    :returns: List of all registered chat interface classes.
    """
    from core.interfaces.facebook import FacebookInterface
    from core.interfaces.telegram import TelegramInterface
    from core.interfaces.microsoft import MicrosoftInterface
    from core.interfaces.test import TestInterface
    return interfaces + [FacebookInterface, TelegramInterface, MicrosoftInterface, TestInterface]


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
        from core.interfaces.telegram import TelegramInterface
        TelegramInterface.init_webhooks()
    except Exception as e:
        logging.exception('Couldn\'t init webhooks')


def uid_to_interface_name(uid: str):
    prefix = str(uid).split('_')[0]

    for i in get_interfaces():
        if i.prefix == prefix:
            return i.name
    raise Exception('No interface for {}'.format(uid))
