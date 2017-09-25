from django.apps import AppConfig


class GolemConfig(AppConfig):
    name = 'golem'

    def ready(self):
        print('Init webhooks @ GolemConfig')
        from golem.core.interfaces.all import init_webhooks
        init_webhooks()
