from django.apps import AppConfig

from golem.core.interfaces import all


class WebGui(AppConfig):
    name = 'webgui'
    prefix = 'web'
    verbose_name = "Chatbot web GUI"

    def ready(self):
        from .interface import WebGuiInterface
        all.register_chat_interface(WebGuiInterface)
