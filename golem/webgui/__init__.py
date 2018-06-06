# default_app_config = 'webgui.app.WebGui'

from golem.core.interfaces import all
from .interface import WebGuiInterface

all.register_chat_interface(WebGuiInterface)
