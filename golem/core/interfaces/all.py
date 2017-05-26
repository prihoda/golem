def create_from_name(name):
    from golem.core.interfaces.facebook import FacebookInterface
    from golem.core.interfaces.telegram import TelegramInterface
    from golem.core.interfaces.test import TestInterface
    
    for interface in [FacebookInterface, TelegramInterface, TestInterface]:
        if interface.name == name:
            return interface