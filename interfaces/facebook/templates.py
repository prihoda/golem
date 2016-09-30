from .responses import *

class FacebookTemplates:
    @staticmethod
    def fb_message(text, quick_replies=[], buttons=[], next=None):
        if not isinstance(text, list):
            text = [text]
        def action(state):
            messages = [TextMessage(text) for t in text]
            if messages:
                last = message[-1]
                for button in buttons:
                    if isinstance(button, Button):
                        last.create_button(**button)
                    else:
                        last.add_button(button)
                for quick_reply in quick_replies:
                    if isinstance(quick_reply, QuickReply):
                        last.create_quick_reply(**quick_reply)
                    else:
                        last.add_quick_reply(quick_reply)
            return messages, next
        return action
    
        