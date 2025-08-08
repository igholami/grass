import os
import socket
import threading
import time

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


class ChatGPTAutomation:

    def __init__(self, chrome_path, chrome_driver_path, cookie=None):
        """
        This constructor automates the following steps:
        1. Open a Chrome browser with remote debugging enabled.
        2. Navigate to ChatGPT.
        3. Prompt the user to complete the log-in/registration/human verification, if required.

        :param chrome_path: file path to chrome browser
        :param chrome_driver_path: file path to chromedriver executable
        :param cookie: optional session cookie for authentication
        """

        self.cookie = cookie
        self.chrome_path = chrome_path
        self.chrome_driver_path = chrome_driver_path
        self.chrome_process = None

        url = r"https://chatgpt.com"
        self.free_port = self.find_available_port()

        self.launch_chrome_with_remote_debugging(self.free_port, url)
        if cookie is None:
            self.wait_for_human_verification()
        self.driver = self.setup_webdriver(self.free_port)
        if cookie:
            self.driver.add_cookie({
                'name': '__Secure-next-auth.session-token',
                'value': cookie,
                'domain': 'chatgpt.com',
                'path': '/',
                'httpOnly': True,
                'secure': True
            })
            self.driver.refresh()


    @staticmethod
    def find_available_port():
        """ This function finds and returns an available port number on the local machine by creating a temporary
            socket, binding it to an ephemeral port, and then closing the socket. """

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return s.getsockname()[1]

    def launch_chrome_with_remote_debugging(self, port, url):
        """ Launches a new Chrome instance with remote debugging enabled on the specified port and navigates to the
            provided url """
        import subprocess
        
        chrome_cmd = [
            self.chrome_path,
            f'--remote-debugging-port={port}',
            '--user-data-dir=remote-profile',
            url
        ]
        
        self.chrome_process = subprocess.Popen(chrome_cmd)
        time.sleep(3)  # Give Chrome time to start

    def open_chatgpt(self):
        """ Opens the chatgpt website in the browser """
        self.driver.get("https://chatgpt.com")
        time.sleep(5)
        
        # Wait for page to fully load
        max_attempts = 60  # 60 seconds max
        attempts = 0
        
        while attempts < max_attempts:
            print(f"Waiting for ChatGPT to load... (attempt {attempts + 1})")
            
            # Check if document is ready
            if self.driver.execute_script("return document.readyState") != "complete":
                time.sleep(1)
                attempts += 1
                continue
            
            # Look for the main chat input area with multiple possible selectors
            input_selectors = [
                '//textarea[@placeholder]',  # Main textarea
                '//div[@contenteditable="true"]',  # Content editable div
                '//textarea[contains(@id, "prompt")]',  # Prompt textarea
                '//div[contains(@data-testid, "composer-text-input")]',  # New UI
                '//*[@role="textbox"]'  # Any textbox
            ]
            
            found_input = False
            for selector in input_selectors:
                elements = self.driver.find_elements(By.XPATH, selector)
                if len(elements) > 0:
                    print(f"Found input element with selector: {selector}")
                    found_input = True
                    break
            
            if found_input:
                print("ChatGPT page loaded successfully!")
                break
                
            time.sleep(1)
            attempts += 1
        
        if attempts >= max_attempts:
            print("Warning: ChatGPT page may not have loaded completely")
        
        time.sleep(2)  # Extra wait for any final loading

    def setup_webdriver(self, port):
        """Initializes a Selenium WebDriver instance connected to remote debugging"""

        chrome_options = webdriver.ChromeOptions()
        chrome_options.binary_location = self.chrome_path
        chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
        
        service = Service(self.chrome_driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver

    def get_cookie(self):
        """
        Get chat.openai.com cookie from the running chrome instance.
        """
        cookies = self.driver.get_cookies()
        cookie = [elem for elem in cookies if elem["name"] == '__Secure-next-auth.session-token'][0]['value']
        return cookie

    def send_prompt_to_chatgpt(self, prompt):
        """ Sends a message to ChatGPT and waits for the response """
        
        # Wait for ChatGPT to be fully ready
        max_attempts = 30
        input_box = None
        
        for attempt in range(max_attempts):
            print(f"Looking for input element (attempt {attempt + 1}/{max_attempts})")
            
            # Try multiple selectors to find the input element
            input_selectors = [
                '//textarea[@placeholder and not(@disabled)]',  # Active textarea
                '//div[@contenteditable="true" and not(@aria-disabled="true")]',  # Active contenteditable
                '//textarea[contains(@id, "prompt") and not(@disabled)]',
                '//div[contains(@data-testid, "composer-text-input")]',
                '//*[@role="textbox" and not(@disabled) and not(@aria-disabled="true")]',
            ]
            
            for selector in input_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        # Check if element is actually interactable
                        if element.is_displayed() and element.is_enabled():
                            # Try to click and interact with it
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                            time.sleep(0.5)
                            element.click()
                            time.sleep(0.5)
                            
                            # Test if we can type in it
                            element.send_keys("test")
                            time.sleep(0.2)
                            element.clear()
                            
                            input_box = element
                            print(f"Found interactive input element with selector: {selector}")
                            break
                except Exception as e:
                    print(f"Element not interactable with selector {selector}: {e}")
                    continue
                    
                if input_box:
                    break
            
            if input_box:
                break
                
            time.sleep(2)
        
        if input_box is None:
            raise Exception("Could not find interactable ChatGPT input element after multiple attempts")
        
        # Send the prompt
        try:
            print("Sending prompt to ChatGPT...")
            
            # Ensure element is focused
            input_box.click()
            time.sleep(0.5)
            
            # Clear any existing content thoroughly
            input_box.send_keys(Keys.CONTROL + "a")  # Select all
            time.sleep(0.2)
            input_box.send_keys(Keys.DELETE)  # Delete selected content
            time.sleep(0.5)
            
            # Send the prompt
            for line in prompt.splitlines():
                input_box.send_keys(line)
                input_box.send_keys(Keys.SHIFT + Keys.ENTER)
                time.sleep(0.01)
            time.sleep(1)
            
            # Look for and click the send button instead of using keyboard shortcuts
            send_button = None
            send_selectors = [
                '//button[contains(@data-testid, "send-button")]',
                '//button[contains(@aria-label, "Send")]',
                '//button[contains(@title, "Send")]',
                '//button[contains(text(), "Send")]',
                '//button[@type="submit"]',
                '//button[.//*[name()="svg"]]'  # Button with SVG icon (common for send buttons)
            ]
            
            for selector in send_selectors:
                try:
                    buttons = self.driver.find_elements(By.XPATH, selector)
                    for button in buttons:
                        if button.is_displayed() and button.is_enabled():
                            send_button = button
                            break
                    if send_button:
                        break
                except Exception:
                    continue
            
            if send_button:
                print("Found send button, clicking...")
                send_button.click()
            else:
                print("No send button found, trying Enter key...")
                input_box.send_keys(Keys.RETURN)
            
        except Exception as e:
            print(f"Direct input failed, trying JavaScript method: {e}")
            try:
                # Clear and set content using JavaScript
                self.driver.execute_script("""
                    arguments[0].focus();
                    arguments[0].value = '';
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('input', {bubbles: true}));
                    arguments[0].dispatchEvent(new Event('change', {bubbles: true}));
                """, input_box, prompt)
                time.sleep(1)
                
                # Try to find and click send button
                send_button_js = self.driver.execute_script("""
                    // Look for send button using various selectors
                    const selectors = [
                        'button[data-testid*="send"]',
                        'button[aria-label*="Send"]',
                        'button[title*="Send"]',
                        'button[type="submit"]',
                        'button:has(svg)'
                    ];
                    
                    for (let selector of selectors) {
                        const btn = document.querySelector(selector);
                        if (btn && btn.offsetParent !== null) {
                            return btn;
                        }
                    }
                    return null;
                """)
                
                if send_button_js:
                    print("Clicking send button via JavaScript...")
                    self.driver.execute_script("arguments[0].click();", send_button_js)
                else:
                    print("Fallback: Using Enter key...")
                    input_box.send_keys(Keys.RETURN)
                    
            except Exception as e2:
                raise Exception(f"All input methods failed: {e2}")
        
        print("Done sending the prompt to ChatGPT.")
        self.check_response_ended()

    def check_response_ended(self):
        """ Checks if ChatGPT response ended """
        start_time = time.time()
        time.sleep(10)  # wait for the response to start
        found = 0
        while found != 3:
            print("Waiting for the response to end...")
            time.sleep(0.5)
            found = 0
            if len(self.driver.find_elements(by=By.XPATH, value='//button[contains(@data-testid, "stop-button")]')) == 0:
                found += 1
            upper = self.driver.find_elements(by=By.CSS_SELECTOR, value='div.text-message')
            if len(upper) > 0:
                found += 1
                inner = upper[-1].find_elements(by=By.TAG_NAME, value='p')
                if len(inner) > 0:
                    found += 1
        print("Response ended.")
        time.sleep(10)  # the length should be =4, so it's better to wait a moment to be sure it's really finished

    def return_chatgpt_conversation(self):
        """
        :return: returns a list of items, even items are the submitted questions (prompts) and odd items are chatgpt response
        """

        return self.driver.find_elements(by=By.CSS_SELECTOR, value='div.text-message')

    def save_conversation(self, file_name):
        """
        It saves the full chatgpt conversation of the tab open in chrome into a text file, with the following format:
            prompt: ...
            response: ...
            delimiter
            prompt: ...
            response: ...

        :param file_name: name of the file where you want to save
        """

        directory_name = "conversations"
        if not os.path.exists(directory_name):
            os.makedirs(directory_name)

        delimiter = "|^_^|"
        chatgpt_conversation = self.return_chatgpt_conversation()
        with open(os.path.join(directory_name, file_name), "a") as file:
            for i in range(0, len(chatgpt_conversation), 2):
                file.write(
                    f"prompt: {chatgpt_conversation[i].text}\nresponse: {chatgpt_conversation[i + 1].text}\n\n{delimiter}\n\n")

    def return_last_response(self):
        """ :return: the text of the last chatgpt response """
        time.sleep(0.5)
        response_elements = self.driver.find_elements(by=By.CSS_SELECTOR, value='div.text-message')
        return response_elements[-1].find_element(by=By.TAG_NAME, value='p').text

    @staticmethod
    def wait_for_human_verification():
        print("You need to manually complete the log-in or the human verification if required.")

        while True:
            user_input = input(
                "Enter 'y' if you have completed the log-in or the human verification, or 'n' to check again: ").lower().strip()

            if user_input == 'y':
                print("Continuing with the automation process...")
                break
            elif user_input == 'n':
                print("Waiting for you to complete the human verification...")
                time.sleep(5)  # You can adjust the waiting time as needed
            else:
                print("Invalid input. Please enter 'y' or 'n'.")

    def quit(self):
        """ Closes the browser and terminates the WebDriver session."""
        print("Closing the browser...")
        try:
            self.driver.close()
            self.driver.quit()
        except Exception as e:
            print(f"Error closing driver: {e}")
        
        # Terminate the Chrome process
        if self.chrome_process:
            try:
                print("Terminating Chrome process...")
                self.chrome_process.terminate()
                self.chrome_process.wait(timeout=5)  # Wait up to 5 seconds for graceful shutdown
                print("Chrome process terminated successfully.")
            except Exception as e:
                print(f"Error terminating Chrome process: {e}")
                try:
                    # Force kill if terminate doesn't work
                    self.chrome_process.kill()
                    print("Chrome process force killed.")
                except Exception as e2:
                    print(f"Error force killing Chrome process: {e2}")
