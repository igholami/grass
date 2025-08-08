from django.core.management import BaseCommand

from auto_grader.telegram import run_bot


class Command(BaseCommand):
    help = 'Run the bot'

    def handle(self, *args, **options):
        run_bot()