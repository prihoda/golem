class MenuElement():
    def __init__(self, type, title, payload=None, url=None,
                 webview_height_ratio=None, messenger_extensions=None):
        self.type = type
        self.title = title
        self.payload = payload
        self.url = url
        self.buttons = []

    def __str__(self):
        text = 'element: ' + self.title
        return text

    def add_button(self, button):
        self.buttons.append(button)
        return button


class MessageElement:
    """
    Base class for message elements.
    """
    def to_message(self, fbid):
        return {"recipient": {"id": fbid}, "message": self.to_response()}

    def to_response(self):
        pass

    def get_response_for(self, platform='fb'):
        return str(self)  # TODO

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self)


class SenderActionMessage(MessageElement):
    def __init__(self, action):
        self.action = action

    def to_message(self, fbid):
        return {'sender_action': self.action, 'recipient': {"id": fbid}}


class TextMessage(MessageElement):
    """
    A plain text message. You can attach buttons or quick replies.
    """

    def __init__(self, text='', buttons=None, quick_replies=None):
        from .quick_reply import QuickReply
        self.text = text
        self.buttons = buttons if buttons else []
        self.quick_replies = [QuickReply(**reply) for reply in quick_replies or []]

    def to_response(self):
        if len(self.buttons):
            return {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "button",
                        "text": self.text,
                        "buttons": [button.to_response() for button in self.buttons]
                    }
                }
            }
        response = {'text': self.text}
        if self.quick_replies:
            response["quick_replies"] = [reply.to_response() for reply in self.quick_replies]
        return response

    def __str__(self):
        text = self.text
        for button in self.buttons:
            text += "\n " + str(button)
        for reply in self.quick_replies:
            text += "\n " + str(reply)
        return text

    def add_button(self, button):
        if self.quick_replies:
            raise ValueError('Cannot add quick_replies and buttons to the same message')
        self.buttons.append(button)
        return button

    def add_quick_reply(self, quick_reply):
        if self.buttons:
            raise ValueError('Cannot add quick_replies and buttons to the same message')
        self.quick_replies.append(quick_reply)
        return quick_reply

    def create_quick_reply(self, **kwargs):
        from .quick_reply import QuickReply
        quick_reply = QuickReply(**kwargs)
        return self.add_quick_reply(quick_reply)


class GenericTemplateMessage(MessageElement):
    """
    A horizontal list of GenericTemplateElement items.
    """

    def __init__(self, elements=None):
        self.elements = [GenericTemplateElement(**element) for element in elements or []]

    def to_response(self):
        return {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [element.to_response() for element in self.elements[:10]]
                }
            }
        }

    def __str__(self):
        text = 'generic template:'
        for element in self.elements:
            text += "\n " + str(element)
        return text

    def add_element(self, element):
        self.elements.append(element)
        return element

    def create_element(self, **kwargs):
        element = GenericTemplateElement(**kwargs)
        return self.add_element(element)


class AttachmentMessage(MessageElement):
    def __init__(self, attachment_type, url):
        self.attachment_type = attachment_type
        self.url = url

    def to_response(self):
        return {
            "attachment": {
                "type": self.attachment_type,
                "payload": {
                    "url": self.url
                }
            }
        }


# TODO stickers not yet supported by Messenger :(
# class StickerMessage(MessageElement):
#    def __init__(self, sticker_id):
#        self.sticker_id = sticker_id
#
#    def to_response(self):
#        return {
#            "sticker_id": self.sticker_id
#        }


class GenericTemplateElement(MessageElement):
    """
    A horizontal card view with title, subtitle, image and buttons.
    """

    def __init__(self, title, image_url=None, subtitle=None, item_url=None, buttons=None):
        self.title = title
        self.image_url = image_url
        self.subtitle = subtitle
        self.item_url = item_url
        self.buttons = buttons if buttons else []

    def to_response(self):
        response = {
            "title": self.title,
            "image_url": self.image_url,
            "subtitle": self.subtitle,
            "item_url": self.item_url
        }
        if self.buttons:
            response["buttons"] = [button.to_response() for button in self.buttons]
        return response

    def __str__(self):
        text = 'element: ' + self.title
        if self.subtitle:
            text += " (" + self.subtitle + ")"
        for button in self.buttons:
            text += "\n  " + str(button)
        return text

    def add_button(self, button):
        self.buttons.append(button)
        return button


def _get_payload_string(payload):
    text = ''
    for entity, values in payload.items():
        if isinstance(values, list):
            for value in values:
                text += '/{}/{}/ '.format(entity, value)
            break
        text += '/{}/{}/ '.format(entity, values)
    return text
