import logging

interfaces = []


def add_interface(interface):
    """
    You can add your own chat interface for a chat platform here.
    :param interface: See telegram.py for an example.
    """
    interfaces.append(interface)


def get_interfaces():
    from golem.core.interfaces.facebook import FacebookInterface
    from golem.core.interfaces.telegram import TelegramInterface
    from golem.core.interfaces.test import TestInterface
    return interfaces + [FacebookInterface, TelegramInterface, TestInterface]


def create_from_name(name):
    from golem.core.interfaces.facebook import FacebookInterface
    from golem.core.interfaces.telegram import TelegramInterface
    from golem.core.interfaces.test import TestInterface
    ifs = interfaces + [FacebookInterface, TelegramInterface, TestInterface]
    for interface in ifs:
        if interface.name == name:
            return interface


def init_webhooks():
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
