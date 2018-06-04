from django.apps import AppConfig

from core.interfaces import all


class WebGui(AppConfig):
    name = 'golm_webgui'
    prefix = 'web'
    verbose_name = "Chatbot web GUI"

    def ready(self):
        from .interface import WebGuiInterface
        all.register_chat_interface(WebGuiInterface)
