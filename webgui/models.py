import datetime

from django.db import models


class Message(models.Model):
    text = models.CharField(max_length=256)
    uid = models.CharField(max_length=256)
    timestamp = models.BigIntegerField()
    is_response = models.BooleanField(default=False)  # true <=> sent by chatbot

    def get_time(self) -> str:
        return datetime.datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M')

    def get_buttons(self) -> list:
        return list(Button.objects.all().filter(message_id__exact=self.id))

    def get_elements(self) -> list:
        return list(Element.objects.all().filter(message_id__exact=self.id))


class Button(models.Model):
    message = models.ForeignKey(Message)
    text = models.CharField(max_length=256)
    action = models.CharField(max_length=256, null=True, blank=True)  # json
    url = models.CharField(max_length=1024, null=True, blank=True)


class Element(models.Model):
    message = models.ForeignKey(Message)
    title = models.CharField(max_length=256)
    subtitle = models.CharField(max_length=256, null=True, blank=True)
    image_url = models.CharField(max_length=256, null=True, blank=True)
