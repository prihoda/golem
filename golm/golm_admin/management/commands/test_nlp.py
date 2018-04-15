from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Tests the NLP on a sentence'

    # def add_arguments(self, parser):
    #     parser.add_argument('text', nargs=1, type=str)

    def handle(self, *args, **options):
        from core.nlp import classify
        classify.test_all()
