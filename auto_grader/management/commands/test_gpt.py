from django.conf import settings
from django.core.management import BaseCommand

from auto_grader.gpt import ChatGPTAutomation


class Command(BaseCommand):
    help = 'Simple GPT test command'

    def handle(self, *args, **options):
        print("Initializing GPT...")
        gpt = ChatGPTAutomation(settings.CHROME_PATH, settings.CHROME_DRIVER_PATH)
        
        print("Opening ChatGPT...")
        gpt.open_chatgpt()
        
        print("Sending test prompt...")
        test_prompt = """Hello, this is a test message with multiple lines.
        
Line 2: Testing line breaks
Line 3: Testing formatting
Line 4: Testing special characters: !@#$%
Line 5: Please respond with 'Test successful' if you can read all 5 lines."""
        
        gpt.send_prompt_to_chatgpt(test_prompt)
        
        print("Getting response...")
        response = gpt.return_last_response()
        
        print("Response:", response)

        gpt.quit()
        print("Done!")