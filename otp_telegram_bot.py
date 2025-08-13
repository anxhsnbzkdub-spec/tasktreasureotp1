#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OTP Telegram Bot
Monitors website for incoming OTP messages and forwards them to Telegram channel
"""

import asyncio
import logging
import time
import re
import os
import platform
from datetime import datetime
from typing import Set, Dict, Any
import json

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import telegram
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('otp_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OTPTelegramBot:
    def __init__(self):
        # Telegram configuration
        self.bot_token = "8354306480:AAFPh2CTRZpjOdntLM8zqdM5kNkE6fthqPw"
        self.channel_id = "-1002724043027"
        
        # Website configuration
        self.login_url = "http://94.23.120.156/ints/login"
        self.sms_url = "http://94.23.120.156/ints/client/SMSCDRStats"
        self.username = "Roni_dada"
        self.password = "Roni_dada"
        
        # Bot state
        self.sent_messages: Set[str] = set()
        self.session = requests.Session()
        self.driver = None
        self.bot = telegram.Bot(token=self.bot_token)
        
        # No fixed interval - continuous check and refresh cycle
        
    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--single-process")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--ignore-ssl-errors")
        chrome_options.add_argument("--ignore-certificate-errors-spki-list")
        chrome_options.add_argument("--ignore-certificate-errors-invalid-ca")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        # Set Chrome binary path if available
        chrome_binary_paths = [
            '/usr/bin/chromium-browser',      # Render Aptfile install
            '/usr/bin/chromium',              # Alternative Chromium path
            '/usr/bin/google-chrome',         # Google Chrome
            '/usr/bin/google-chrome-stable',  # Google Chrome stable
            '/app/.apt/usr/bin/google-chrome', # Heroku buildpack
            '/app/.apt/usr/bin/chromium-browser', # Heroku Chromium
            os.environ.get('GOOGLE_CHROME_BIN', ''),
            os.environ.get('CHROME_BIN', ''),
        ]
        
        # Debug: Check which Chrome binaries exist
        logger.info("Checking for Chrome binaries...")
        for chrome_path in chrome_binary_paths:
            if chrome_path:
                exists = os.path.exists(chrome_path)
                logger.info(f"Chrome binary {chrome_path}: {'EXISTS' if exists else 'NOT FOUND'}")
                if exists:
                    chrome_options.binary_location = chrome_path
                    logger.info(f"Using Chrome binary at: {chrome_path}")
                    break
        
        # If no binary found, try to detect system Chrome
        if not hasattr(chrome_options, 'binary_location') or not chrome_options.binary_location:
            logger.warning("No Chrome binary found in standard locations, trying system detection...")
            try:
                import subprocess
                # Try to find chromium via which command
                result = subprocess.run(['which', 'chromium-browser'], capture_output=True, text=True)
                if result.returncode == 0:
                    chromium_path = result.stdout.strip()
                    logger.info(f"Found chromium via 'which': {chromium_path}")
                    chrome_options.binary_location = chromium_path
                else:
                    result = subprocess.run(['which', 'chromium'], capture_output=True, text=True)
                    if result.returncode == 0:
                        chromium_path = result.stdout.strip()
                        logger.info(f"Found chromium via 'which': {chromium_path}")
                        chrome_options.binary_location = chromium_path
            except Exception as e:
                logger.warning(f"System Chrome detection failed: {e}")
        
        try:
            # Check for various ChromeDriver locations
            chromedriver_paths = [
                '/usr/bin/chromedriver',              # Aptfile install (Render)
                '/usr/bin/chromium-chromedriver',     # Chromium driver
                '/usr/local/bin/chromedriver',        # Docker
                '/app/.chromedriver/bin/chromedriver', # Heroku/Render buildpack
                os.environ.get('CHROMEDRIVER_PATH', ''), # Environment variable
            ]
            
            # Debug: Check which ChromeDriver binaries exist
            logger.info("Checking for ChromeDriver binaries...")
            for chromedriver_path in chromedriver_paths:
                if chromedriver_path:
                    exists = os.path.exists(chromedriver_path)
                    logger.info(f"ChromeDriver {chromedriver_path}: {'EXISTS' if exists else 'NOT FOUND'}")
                    if exists:
                        logger.info(f"Using chromedriver at: {chromedriver_path}")
                        service = Service(chromedriver_path)
                        self.driver = webdriver.Chrome(service=service, options=chrome_options)
                        return self.driver
            
            # Check for local Windows chromedriver.exe
            if os.path.exists('./chromedriver.exe') and platform.system() == 'Windows':
                logger.info("Using local Windows chromedriver")
                service = Service('./chromedriver.exe')
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                return self.driver
        except Exception as e:
            logger.warning(f"Specific chromedriver failed: {e}")
        
        try:
            # Try ChromeDriverManager as fallback
            logger.info("Trying ChromeDriverManager...")
            from webdriver_manager.chrome import ChromeDriverManager
            
            # Force ChromeDriverManager to use specific Chrome version if we have binary location
            if hasattr(chrome_options, 'binary_location') and chrome_options.binary_location:
                logger.info(f"Setting Chrome binary for WebDriverManager: {chrome_options.binary_location}")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("ChromeDriverManager setup successful")
        except Exception as e:
            logger.warning(f"ChromeDriverManager failed: {e}")
            logger.info("Trying system Chrome without explicit driver path...")
            try:
                # Fallback to system Chrome - let Chrome find its own driver
                self.driver = webdriver.Chrome(options=chrome_options)
                logger.info("System Chrome setup successful")
            except Exception as e2:
                logger.error(f"System Chrome failed: {e2}")
                logger.error(f"Chrome binary location: {getattr(chrome_options, 'binary_location', 'Not set')}")
                
                # Final fallback - try to use chromium directly
                try:
                    logger.info("Final fallback: trying chromium-browser directly...")
                    chrome_options.binary_location = '/usr/bin/chromium-browser'
                    self.driver = webdriver.Chrome(options=chrome_options)
                    logger.info("Chromium fallback successful")
                except Exception as e3:
                    logger.error(f"All Chrome setup methods failed: {e3}")
                    raise Exception(f"Could not setup Chrome driver: {e3}")
        
        return self.driver
    
    def solve_captcha(self, captcha_text: str) -> int:
        """Solve simple math captcha"""
        try:
            # Extract numbers and operator from captcha text
            # Expected format: "What is X + Y = ?"
            match = re.search(r'(\d+)\s*\+\s*(\d+)', captcha_text)
            if match:
                num1, num2 = map(int, match.groups())
                result = num1 + num2
                logger.info(f"Solved captcha: {num1} + {num2} = {result}")
                return result
            
            # Try other operators if needed
            match = re.search(r'(\d+)\s*-\s*(\d+)', captcha_text)
            if match:
                num1, num2 = map(int, match.groups())
                result = num1 - num2
                logger.info(f"Solved captcha: {num1} - {num2} = {result}")
                return result
                
            match = re.search(r'(\d+)\s*\*\s*(\d+)', captcha_text)
            if match:
                num1, num2 = map(int, match.groups())
                result = num1 * num2
                logger.info(f"Solved captcha: {num1} * {num2} = {result}")
                return result
                
        except Exception as e:
            logger.error(f"Error solving captcha: {e}")
        
        return 0
    
    def login_to_website(self) -> bool:
        """Login to the website with captcha solving"""
        try:
            logger.info("Starting login process...")
            self.driver.get(self.login_url)
            
            # Wait longer for SSL warning page to load
            time.sleep(5)
            
            # Handle SSL certificate warning if present
            try:
                # Look for "Advanced" button or "Proceed to site" option
                advanced_button = None
                proceed_link = None
                
                try:
                    advanced_button = self.driver.find_element(By.ID, "details-button")
                except:
                    try:
                        advanced_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Advanced')]")
                    except:
                        pass
                
                if advanced_button:
                    logger.info("Found SSL warning, clicking Advanced...")
                    advanced_button.click()
                    time.sleep(2)
                    
                    try:
                        proceed_link = self.driver.find_element(By.ID, "proceed-link")
                    except:
                        try:
                            proceed_link = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Proceed') or contains(text(), 'unsafe')]")
                        except:
                            pass
                    
                    if proceed_link:
                        logger.info("Clicking proceed to unsafe site...")
                        proceed_link.click()
                        time.sleep(3)
                        
            except Exception as ssl_error:
                logger.warning(f"SSL handling failed: {ssl_error}")
            
            # Wait for actual login page to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Get page source for debugging
            page_source = self.driver.page_source
            logger.info(f"Page title: {self.driver.title}")
            logger.info(f"Current URL: {self.driver.current_url}")
            
            # Find username field with multiple strategies
            username_field = None
            username_selectors = [
                (By.NAME, "username"),
                (By.ID, "username"),
                (By.XPATH, "//input[@type='text']"),
                (By.XPATH, "//input[contains(@name, 'user')]"),
                (By.CSS_SELECTOR, "input[name='username']"),
            ]
            
            for selector_type, selector_value in username_selectors:
                try:
                    username_field = self.driver.find_element(selector_type, selector_value)
                    logger.info(f"Found username field using {selector_type}: {selector_value}")
                    break
                except:
                    continue
            
            if not username_field:
                logger.error("Could not find username field with any selector")
                logger.info(f"Page source excerpt: {page_source[:500]}")
                return False
            

                
            username_field.clear()
            username_field.send_keys(self.username)
            logger.info("Username entered successfully")
            
            # Find password field with multiple strategies
            password_field = None
            password_selectors = [
                (By.NAME, "password"),
                (By.ID, "password"),
                (By.XPATH, "//input[@type='password']"),
                (By.XPATH, "//input[contains(@name, 'pass')]"),
                (By.CSS_SELECTOR, "input[name='password']"),
            ]
            
            for selector_type, selector_value in password_selectors:
                try:
                    password_field = self.driver.find_element(selector_type, selector_value)
                    logger.info(f"Found password field using {selector_type}: {selector_value}")
                    break
                except:
                    continue
                    
            if not password_field:
                logger.error("Could not find password field with any selector")
                return False
                
            password_field.clear()
            password_field.send_keys(self.password)
            logger.info("Password entered successfully")
            
            # Get captcha text and solve it (improved method)
            captcha_solved = False
            try:
                # Get the full page text to find captcha
                page_text = self.driver.find_element(By.TAG_NAME, "body").text
                logger.info(f"Page text excerpt: {page_text[:200]}")
                
                # Look for captcha pattern in page text
                import re
                captcha_match = re.search(r'What is (\d+) \+ (\d+) = \?', page_text)
                if captcha_match:
                    num1, num2 = map(int, captcha_match.groups())
                    captcha_answer = num1 + num2
                    logger.info(f"Found captcha: {num1} + {num2} = {captcha_answer}")
                    
                    # Find captcha input field with multiple strategies
                    captcha_field = None
                    captcha_selectors = [
                        (By.NAME, "capt"),
                        (By.ID, "capt"),
                        (By.XPATH, "//input[@type='number']"),
                        (By.XPATH, "//input[contains(@name, 'capt')]"),
                        (By.CSS_SELECTOR, "input[name='capt']"),
                    ]
                    
                    for selector_type, selector_value in captcha_selectors:
                        try:
                            captcha_field = self.driver.find_element(selector_type, selector_value)
                            logger.info(f"Found captcha field using {selector_type}: {selector_value}")
                            break
                        except:
                            continue
                    
                    if captcha_field:
                        captcha_field.clear()
                        captcha_field.send_keys(str(captcha_answer))
                        captcha_solved = True
                        logger.info(f"Captcha solved and entered: {captcha_answer}")
                    else:
                        logger.warning("Could not find captcha field with any selector")
                else:
                    logger.warning("Could not find captcha pattern in page text")
                    
            except Exception as e:
                logger.warning(f"Captcha handling failed: {e}")
            
            # Submit form with multiple strategies
            submit_clicked = False
            submit_selectors = [
                (By.TAG_NAME, "button"),
                (By.XPATH, "//input[@type='submit']"),
                (By.XPATH, "//button[@type='submit']"),
                (By.XPATH, "//input[contains(@value, 'Login')]"),
                (By.XPATH, "//button[contains(text(), 'Login')]"),
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.CSS_SELECTOR, "input[type='submit']"),
            ]
            
            for selector_type, selector_value in submit_selectors:
                try:
                    submit_button = self.driver.find_element(selector_type, selector_value)
                    submit_button.click()
                    logger.info(f"Clicked submit button using {selector_type}: {selector_value}")
                    submit_clicked = True
                    break
                except:
                    continue
            
            if not submit_clicked:
                logger.error("Could not find or click submit button with any selector")
                return False
            
            # Wait for redirect or check if login was successful
            time.sleep(5)
            
            current_url = self.driver.current_url
            logger.info(f"After login URL: {current_url}")
            
            # Check for successful login (confirmed pattern from interactive test)
            if "client" in current_url.lower() and "login" not in current_url.lower():
                logger.info("Login successful!")
                return True
            else:
                logger.error(f"Login failed - unexpected URL: {current_url}")
                return False
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    def get_country_info(self, phone_number: str) -> Dict[str, str]:
        """Get country information based on phone number"""
        country_codes = {
            # North America
            '1': {'name': 'USA/Canada', 'flag': '🇺🇸'},
            '52': {'name': 'Mexico', 'flag': '🇲🇽'},
            
            # Europe
            '44': {'name': 'UK', 'flag': '🇬🇧'},
            '33': {'name': 'France', 'flag': '🇫🇷'},
            '49': {'name': 'Germany', 'flag': '🇩🇪'},
            '39': {'name': 'Italy', 'flag': '🇮🇹'},
            '34': {'name': 'Spain', 'flag': '🇪🇸'},
            '31': {'name': 'Netherlands', 'flag': '🇳🇱'},
            '32': {'name': 'Belgium', 'flag': '🇧🇪'},
            '41': {'name': 'Switzerland', 'flag': '🇨🇭'},
            '43': {'name': 'Austria', 'flag': '🇦🇹'},
            '45': {'name': 'Denmark', 'flag': '🇩🇰'},
            '46': {'name': 'Sweden', 'flag': '🇸🇪'},
            '47': {'name': 'Norway', 'flag': '🇳🇴'},
            '48': {'name': 'Poland', 'flag': '🇵🇱'},
            '351': {'name': 'Portugal', 'flag': '🇵🇹'},
            '30': {'name': 'Greece', 'flag': '🇬🇷'},
            '7': {'name': 'Russia', 'flag': '🇷🇺'},
            '380': {'name': 'Ukraine', 'flag': '🇺🇦'},
            '36': {'name': 'Hungary', 'flag': '🇭🇺'},
            '420': {'name': 'Czech Republic', 'flag': '🇨🇿'},
            '421': {'name': 'Slovakia', 'flag': '🇸🇰'},
            '386': {'name': 'Slovenia', 'flag': '🇸🇮'},
            '385': {'name': 'Croatia', 'flag': '🇭🇷'},
            '381': {'name': 'Serbia', 'flag': '🇷🇸'},
            '382': {'name': 'Montenegro', 'flag': '🇲🇪'},
            '387': {'name': 'Bosnia', 'flag': '🇧🇦'},
            '389': {'name': 'Macedonia', 'flag': '🇲🇰'},
            '355': {'name': 'Albania', 'flag': '🇦🇱'},
            '40': {'name': 'Romania', 'flag': '🇷🇴'},
            '359': {'name': 'Bulgaria', 'flag': '🇧🇬'},
            '358': {'name': 'Finland', 'flag': '🇫🇮'},
            '372': {'name': 'Estonia', 'flag': '🇪🇪'},
            '371': {'name': 'Latvia', 'flag': '🇱🇻'},
            '370': {'name': 'Lithuania', 'flag': '🇱🇹'},
            '353': {'name': 'Ireland', 'flag': '🇮🇪'},
            '354': {'name': 'Iceland', 'flag': '🇮🇸'},
            '298': {'name': 'Faroe Islands', 'flag': '🇫🇴'},
            '90': {'name': 'Turkey', 'flag': '🇹🇷'},
            
            # Asia
            '86': {'name': 'China', 'flag': '🇨🇳'},
            '91': {'name': 'India', 'flag': '🇮🇳'},
            '81': {'name': 'Japan', 'flag': '🇯🇵'},
            '82': {'name': 'South Korea', 'flag': '🇰🇷'},
            '65': {'name': 'Singapore', 'flag': '🇸🇬'},
            '60': {'name': 'Malaysia', 'flag': '🇲🇾'},
            '66': {'name': 'Thailand', 'flag': '🇹🇭'},
            '84': {'name': 'Vietnam', 'flag': '🇻🇳'},
            '62': {'name': 'Indonesia', 'flag': '🇮🇩'},
            '63': {'name': 'Philippines', 'flag': '🇵🇭'},
            '880': {'name': 'Bangladesh', 'flag': '🇧🇩'},
            '92': {'name': 'Pakistan', 'flag': '🇵🇰'},
            '94': {'name': 'Sri Lanka', 'flag': '🇱🇰'},
            '95': {'name': 'Myanmar', 'flag': '🇲🇲'},
            '855': {'name': 'Cambodia', 'flag': '🇰🇭'},
            '856': {'name': 'Laos', 'flag': '🇱🇦'},
            '673': {'name': 'Brunei', 'flag': '🇧🇳'},
            '976': {'name': 'Mongolia', 'flag': '🇲🇳'},
            '852': {'name': 'Hong Kong', 'flag': '🇭🇰'},
            '853': {'name': 'Macau', 'flag': '🇲🇴'},
            '886': {'name': 'Taiwan', 'flag': '🇹🇼'},
            '850': {'name': 'North Korea', 'flag': '🇰🇵'},
            '977': {'name': 'Nepal', 'flag': '🇳🇵'},
            '975': {'name': 'Bhutan', 'flag': '🇧🇹'},
            '960': {'name': 'Maldives', 'flag': '🇲🇻'},
            '98': {'name': 'Iran', 'flag': '🇮🇷'},
            '93': {'name': 'Afghanistan', 'flag': '🇦🇫'},
            '992': {'name': 'Tajikistan', 'flag': '🇹🇯'},
            '993': {'name': 'Turkmenistan', 'flag': '🇹🇲'},
            '998': {'name': 'Uzbekistan', 'flag': '🇺🇿'},
            '996': {'name': 'Kyrgyzstan', 'flag': '🇰🇬'},
            '7': {'name': 'Kazakhstan', 'flag': '🇰🇿'},
            
            # Middle East
            '971': {'name': 'UAE', 'flag': '🇦🇪'},
            '966': {'name': 'Saudi Arabia', 'flag': '🇸🇦'},
            '974': {'name': 'Qatar', 'flag': '🇶🇦'},
            '973': {'name': 'Bahrain', 'flag': '🇧🇭'},
            '968': {'name': 'Oman', 'flag': '🇴🇲'},
            '965': {'name': 'Kuwait', 'flag': '🇰🇼'},
            '972': {'name': 'Israel', 'flag': '🇮🇱'},
            '970': {'name': 'Palestine', 'flag': '🇵🇸'},
            '962': {'name': 'Jordan', 'flag': '🇯🇴'},
            '961': {'name': 'Lebanon', 'flag': '🇱🇧'},
            '963': {'name': 'Syria', 'flag': '🇸🇾'},
            '964': {'name': 'Iraq', 'flag': '🇮🇶'},
            '967': {'name': 'Yemen', 'flag': '🇾🇪'},
            
            # Africa
            '20': {'name': 'Egypt', 'flag': '🇪🇬'},
            '27': {'name': 'South Africa', 'flag': '🇿🇦'},
            '212': {'name': 'Morocco', 'flag': '🇲🇦'},
            '213': {'name': 'Algeria', 'flag': '🇩🇿'},
            '216': {'name': 'Tunisia', 'flag': '🇹🇳'},
            '218': {'name': 'Libya', 'flag': '🇱🇾'},
            '220': {'name': 'Gambia', 'flag': '🇬🇲'},
            '221': {'name': 'Senegal', 'flag': '🇸🇳'},
            '222': {'name': 'Mauritania', 'flag': '🇲🇷'},
            '223': {'name': 'Mali', 'flag': '🇲🇱'},
            '224': {'name': 'Guinea', 'flag': '🇬🇳'},
            '225': {'name': 'Ivory Coast', 'flag': '🇨🇮'},
            '226': {'name': 'Burkina Faso', 'flag': '🇧🇫'},
            '227': {'name': 'Niger', 'flag': '🇳🇪'},
            '228': {'name': 'Togo', 'flag': '🇹🇬'},
            '229': {'name': 'Benin', 'flag': '🇧🇯'},
            '230': {'name': 'Mauritius', 'flag': '🇲🇺'},
            '231': {'name': 'Liberia', 'flag': '🇱🇷'},
            '232': {'name': 'Sierra Leone', 'flag': '🇸🇱'},
            '233': {'name': 'Ghana', 'flag': '🇬🇭'},
            '234': {'name': 'Nigeria', 'flag': '🇳🇬'},
            '235': {'name': 'Chad', 'flag': '🇹🇩'},
            '236': {'name': 'Central African Republic', 'flag': '🇨🇫'},
            '237': {'name': 'Cameroon', 'flag': '🇨🇲'},
            '238': {'name': 'Cape Verde', 'flag': '🇨🇻'},
            '239': {'name': 'Sao Tome', 'flag': '🇸🇹'},
            '240': {'name': 'Equatorial Guinea', 'flag': '🇬🇶'},
            '241': {'name': 'Gabon', 'flag': '🇬🇦'},
            '242': {'name': 'Congo', 'flag': '🇨🇬'},
            '243': {'name': 'DR Congo', 'flag': '🇨🇩'},
            '244': {'name': 'Angola', 'flag': '🇦🇴'},
            '245': {'name': 'Guinea-Bissau', 'flag': '🇬🇼'},
            '246': {'name': 'Diego Garcia', 'flag': '🇮🇴'},
            '248': {'name': 'Seychelles', 'flag': '🇸🇨'},
            '249': {'name': 'Sudan', 'flag': '🇸🇩'},
            '250': {'name': 'Rwanda', 'flag': '🇷🇼'},
            '251': {'name': 'Ethiopia', 'flag': '🇪🇹'},
            '252': {'name': 'Somalia', 'flag': '🇸🇴'},
            '253': {'name': 'Djibouti', 'flag': '🇩🇯'},
            '254': {'name': 'Kenya', 'flag': '🇰🇪'},
            '255': {'name': 'Tanzania', 'flag': '🇹🇿'},
            '256': {'name': 'Uganda', 'flag': '🇺🇬'},
            '257': {'name': 'Burundi', 'flag': '🇧🇮'},
            '258': {'name': 'Mozambique', 'flag': '🇲🇿'},
            '260': {'name': 'Zambia', 'flag': '🇿🇲'},
            '261': {'name': 'Madagascar', 'flag': '🇲🇬'},
            '262': {'name': 'Reunion', 'flag': '🇷🇪'},
            '263': {'name': 'Zimbabwe', 'flag': '🇿🇼'},
            '264': {'name': 'Namibia', 'flag': '🇳🇦'},
            '265': {'name': 'Malawi', 'flag': '🇲🇼'},
            '266': {'name': 'Lesotho', 'flag': '🇱🇸'},
            '267': {'name': 'Botswana', 'flag': '🇧🇼'},
            '268': {'name': 'Swaziland', 'flag': '🇸🇿'},
            '269': {'name': 'Comoros', 'flag': '🇰🇲'},
            
            # South America
            '55': {'name': 'Brazil', 'flag': '🇧🇷'},
            '54': {'name': 'Argentina', 'flag': '🇦🇷'},
            '56': {'name': 'Chile', 'flag': '🇨🇱'},
            '57': {'name': 'Colombia', 'flag': '🇨🇴'},
            '58': {'name': 'Venezuela', 'flag': '🇻🇪'},
            '51': {'name': 'Peru', 'flag': '🇵🇪'},
            '593': {'name': 'Ecuador', 'flag': '🇪🇨'},
            '591': {'name': 'Bolivia', 'flag': '🇧🇴'},
            '595': {'name': 'Paraguay', 'flag': '🇵🇾'},
            '598': {'name': 'Uruguay', 'flag': '🇺🇾'},
            '597': {'name': 'Suriname', 'flag': '🇸🇷'},
            '594': {'name': 'French Guiana', 'flag': '🇬🇫'},
            '592': {'name': 'Guyana', 'flag': '🇬🇾'},
            
            # Oceania
            '61': {'name': 'Australia', 'flag': '🇦🇺'},
            '64': {'name': 'New Zealand', 'flag': '🇳🇿'},
            '679': {'name': 'Fiji', 'flag': '🇫🇯'},
            '685': {'name': 'Samoa', 'flag': '🇼🇸'},
            '686': {'name': 'Kiribati', 'flag': '🇰🇮'},
            '687': {'name': 'New Caledonia', 'flag': '🇳🇨'},
            '688': {'name': 'Tuvalu', 'flag': '🇹🇻'},
            '689': {'name': 'French Polynesia', 'flag': '🇵🇫'},
            '690': {'name': 'Tokelau', 'flag': '🇹🇰'},
            '691': {'name': 'Micronesia', 'flag': '🇫🇲'},
            '692': {'name': 'Marshall Islands', 'flag': '🇲🇭'},
            '508': {'name': 'St Pierre', 'flag': '🇵🇲'},
            
            # Caribbean
            '590': {'name': 'Guadeloupe', 'flag': '🇬🇵'},
            '596': {'name': 'Martinique', 'flag': '🇲🇶'},
            '599': {'name': 'Netherlands Antilles', 'flag': '🇨🇼'},
            '1242': {'name': 'Bahamas', 'flag': '🇧🇸'},
            '1246': {'name': 'Barbados', 'flag': '🇧🇧'},
            '1264': {'name': 'Anguilla', 'flag': '🇦🇮'},
            '1268': {'name': 'Antigua', 'flag': '🇦🇬'},
            '1284': {'name': 'British Virgin Islands', 'flag': '🇻🇬'},
            '1345': {'name': 'Cayman Islands', 'flag': '🇰🇾'},
            '1441': {'name': 'Bermuda', 'flag': '🇧🇲'},
            '1473': {'name': 'Grenada', 'flag': '🇬🇩'},
            '1649': {'name': 'Turks and Caicos', 'flag': '🇹🇨'},
            '1664': {'name': 'Montserrat', 'flag': '🇲🇸'},
            '1721': {'name': 'Sint Maarten', 'flag': '🇸🇽'},
            '1758': {'name': 'St Lucia', 'flag': '🇱🇨'},
            '1767': {'name': 'Dominica', 'flag': '🇩🇲'},
            '1784': {'name': 'St Vincent', 'flag': '🇻🇨'},
            '1787': {'name': 'Puerto Rico', 'flag': '🇵🇷'},
            '1809': {'name': 'Dominican Republic', 'flag': '🇩🇴'},
            '1829': {'name': 'Dominican Republic', 'flag': '🇩🇴'},
            '1849': {'name': 'Dominican Republic', 'flag': '🇩🇴'},
            '1868': {'name': 'Trinidad and Tobago', 'flag': '🇹🇹'},
            '1869': {'name': 'St Kitts and Nevis', 'flag': '🇰🇳'},
            '1876': {'name': 'Jamaica', 'flag': '🇯🇲'},
            '53': {'name': 'Cuba', 'flag': '🇨🇺'},
            '509': {'name': 'Haiti', 'flag': '🇭🇹'},
        }
        
        # Clean the phone number
        cleaned_number = re.sub(r'[^\d]', '', phone_number)
        
        # Try to match country codes (longest first)
        for code in sorted(country_codes.keys(), key=len, reverse=True):
            if cleaned_number.startswith(code):
                return country_codes[code]
        
        # Default fallback
        return {'name': 'Unknown', 'flag': '🌍'}

    def extract_sms_data(self, row_data: list) -> Dict[str, Any]:
        """Extract SMS data from table row"""
        try:
            # Default structure
            sms_data = {
                'time': 'Unknown',
                'number': 'Unknown', 
                'country': 'Unknown',
                'country_flag': '🌍',
                'service': 'Unknown',
                'otp_code': 'Unknown',
                'message': 'No message'
            }
            
            # Extract from row data based on ACTUAL column mapping:
            # Column 0: Date (Time)
            # Column 1: Range (skip this)
            # Column 2: Number 
            # Column 3: CLI (Service)
            # Column 4: SMS (Message)
            if len(row_data) >= 5:
                # Map data from table columns according to actual headers
                sms_data['time'] = row_data[0].strip() if row_data[0] else 'Unknown'     # Date
                sms_data['number'] = row_data[2].strip() if row_data[2] else 'Unknown'   # Number (Column 2)
                sms_data['service'] = row_data[3].strip() if row_data[3] else 'Unknown'  # CLI (Column 3)
                sms_data['message'] = row_data[4].strip() if row_data[4] else 'No message' # SMS (Column 4)
                
                # Get country info from phone number
                if sms_data['number'] != 'Unknown':
                    country_info = self.get_country_info(sms_data['number'])
                    sms_data['country'] = country_info['name']
                    sms_data['country_flag'] = country_info['flag']
                
                # Extract OTP code from message (improved patterns for various formats)
                otp_patterns = [
                    r'code[:\s]*(\d{2,3}[-\s]\d{2,3})',          # 123-456 or 123 456
                    r'otp[:\s]*(\d{2,3}[-\s]\d{2,3})',           # OTP: 123-456
                    r'verification[:\s]*(\d{2,3}[-\s]\d{2,3})',  # verification: 123-456
                    r'code[:\s]*(\d{3,8})',                      # code: 123456
                    r'otp[:\s]*(\d{3,8})',                       # otp: 123456
                    r'verification[:\s]*(\d{3,8})',              # verification: 123456
                    r'(\d{2,3}[-\s]\d{2,3})',                    # any 123-456 pattern
                    r'\b(\d{4,8})\b'                             # any 4-8 digit number
                ]
                
                for pattern in otp_patterns:
                    match = re.search(pattern, sms_data['message'], re.IGNORECASE)
                    if match:
                        sms_data['otp_code'] = match.group(1)
                        break
            
            return sms_data
            
        except Exception as e:
            logger.error(f"Error extracting SMS data: {e}")
            return None
    
    def escape_markdown_v2(self, text: str) -> str:
        """Escape special characters for MarkdownV2"""
        # Characters that need escaping in MarkdownV2
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    def format_message(self, sms_data: Dict[str, Any]) -> str:
        """Format SMS message according to specified template with clickable OTP"""
        try:
            country_name = sms_data.get('country', 'Unknown')
            country_flag = sms_data.get('country_flag', '🌍')
            service = sms_data.get('service', 'Unknown')
            otp_code = sms_data.get('otp_code', 'Unknown')
            
            # Escape special characters for Telegram
            safe_time = self.escape_markdown_v2(sms_data.get('time', 'Unknown'))
            safe_number = self.escape_markdown_v2(sms_data.get('number', 'Unknown'))
            safe_country = self.escape_markdown_v2(country_name)
            safe_service = self.escape_markdown_v2(service)
            safe_message = sms_data.get('message', 'No message')  # Keep raw for code block
            
            # Make OTP clickable for easy copying (proper format for Telegram)
            clickable_otp = f"`{otp_code}`" if otp_code != 'Unknown' else 'Unknown'
            
            # Format message with proper markdown for Telegram
            message = f"""🔔{safe_country} {country_flag} {safe_service} Otp Code Received Successfully\\.

⏰Time: {safe_time}
📱Number: {safe_number}
🌍Country: {safe_country} {country_flag}
💬Service: {safe_service}
🔐Otp Code: {clickable_otp}
📝Message:
```
{safe_message}
```

Powered by @tasktreasur\\_support"""
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting message: {e}")
            return "Error formatting message"
    
    def get_message_hash(self, message: str) -> str:
        """Create a hash for message to prevent duplicates"""
        import hashlib
        return hashlib.md5(message.encode('utf-8')).hexdigest()
    
    async def send_to_telegram(self, message: str) -> bool:
        """Send message to Telegram channel"""
        try:
            message_hash = self.get_message_hash(message)
            
            # Check if message was already sent
            if message_hash in self.sent_messages:
                logger.info("Message already sent, skipping duplicate")
                return False
            
            # Send message with proper markdown parsing
            try:
                await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    connect_timeout=30,
                    read_timeout=30,
                    write_timeout=30
                )
            except Exception as parse_error:
                logger.warning(f"MarkdownV2 failed, trying Markdown: {parse_error}")
                try:
                    await self.bot.send_message(
                        chat_id=self.channel_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN,
                        connect_timeout=30,
                        read_timeout=30,
                        write_timeout=30
                    )
                except Exception as markdown_error:
                    # If all parsing fails, send as plain text
                    logger.warning(f"All markdown parsing failed, sending as plain text: {markdown_error}")
                    await self.bot.send_message(
                        chat_id=self.channel_id,
                        text=message,
                        connect_timeout=30,
                        read_timeout=30,
                        write_timeout=30
                    )
            
            # Mark message as sent
            self.sent_messages.add(message_hash)
            logger.info("Message sent to Telegram successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error sending to Telegram: {e}")
            return False
    
    def check_for_new_messages(self) -> list:
        """Check website for new SMS messages using proper table structure"""
        try:
            self.driver.get(self.sms_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Find table headers first to understand structure
            # Expected order: Date, Number, CLI, SMS
            try:
                # Look for headers by text content in the correct order
                date_header = self.driver.find_element(By.XPATH, "//th[contains(text(), 'Date')]")
                number_header = self.driver.find_element(By.XPATH, "//th[contains(text(), 'Number')]") 
                cli_header = self.driver.find_element(By.XPATH, "//th[contains(text(), 'CLI')]")
                sms_header = self.driver.find_element(By.XPATH, "//th[contains(text(), 'SMS')]")
                
                logger.info("Found table headers - parsing table structure")
                
                # Get the table containing these headers
                table = date_header.find_element(By.XPATH, "./ancestor::table")
                
                # Get all rows from the table body
                rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
                
                messages = []
                for row in rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 3:  # Make sure we have enough columns
                            row_data = []
                            for cell in cells:
                                cell_text = cell.text.strip()
                                row_data.append(cell_text)
                            
                            # Check if this row contains SMS data
                            row_text = ' '.join(row_data).lower()
                            if any(keyword in row_text for keyword in ['whatsapp', 'code', 'verification', 'sms', 'otp']) and len(row_data[0]) > 0:
                                messages.append(row_data)
                                logger.info(f"Found SMS row: {row_data[:3]}...")  # Log first 3 columns
                    
                    except Exception as row_error:
                        logger.warning(f"Error processing table row: {row_error}")
                        continue
                
                logger.info(f"Found {len(messages)} SMS messages from table")
                return messages
                
            except Exception as table_error:
                logger.warning(f"Could not find table structure: {table_error}")
                
                # Fallback to original method
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                
                messages = []
                rows = soup.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) > 2:
                        row_data = [cell.get_text(strip=True) for cell in cells]
                        row_text = ' '.join(row_data).lower()
                        if any(keyword in row_text for keyword in ['whatsapp', 'code', 'verification']):
                            messages.append(row_data)
                
                logger.info(f"Found {len(messages)} messages using fallback method")
                return messages
            
        except Exception as e:
            logger.error(f"Error checking for messages: {e}")
            return []
    
    async def run_monitoring_loop(self):
        """Main monitoring loop"""
        logger.info("Starting OTP monitoring bot...")
        
        try:
            # Setup driver
            self.setup_driver()
            
            # Login to website
            if not self.login_to_website():
                logger.error("Failed to login to website")
                return
            
            logger.info("Starting continuous monitoring loop (check → refresh → repeat)...")
            
            while True:
                try:
                    # Step 1: Check for new messages
                    logger.info("📋 Checking for new SMS messages...")
                    messages = self.check_for_new_messages()
                    
                    # Step 2: Process any found messages
                    for row_data in messages:
                        # Extract SMS data from table row
                        sms_data = self.extract_sms_data(row_data)
                        
                        if sms_data:
                            # Format message
                            formatted_message = self.format_message(sms_data)
                            
                            # Send to Telegram
                            sent = await self.send_to_telegram(formatted_message)
                            if sent:
                                logger.info(f"✅ New OTP sent: {sms_data.get('country', 'Unknown')} - {sms_data.get('otp_code', 'Unknown')}")
                    
                    # Step 3: Refresh page for next check (no waiting)
                    logger.info("🔄 Refreshing page for next check...")
                    # The page refresh happens in check_for_new_messages() when it loads the URL
                    
                except Exception as e:
                    logger.error(f"❌ Error in monitoring loop: {e}")
                    # Brief pause on error to prevent rapid cycling
                    await asyncio.sleep(2)
                    
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            if self.driver:
                self.driver.quit()
    
    async def test_telegram_connection(self):
        """Test Telegram bot connection"""
        try:
            # First try to get bot info
            bot_info = await self.bot.get_me()
            logger.info(f"Bot info: {bot_info.first_name} (@{bot_info.username})")
            
            # Then try to send a test message
            await self.bot.send_message(
                chat_id=self.channel_id,
                text="🤖 OTP Bot started successfully!",
                connect_timeout=30,
                read_timeout=30,
                write_timeout=30
            )
            logger.info("Telegram connection test successful")
            return True
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False

def main():
    """Main function to run the bot"""
    bot = OTPTelegramBot()
    
    async def run_bot():
        # Test Telegram connection first
        if not await bot.test_telegram_connection():
            logger.error("Failed to connect to Telegram. Please check bot token and channel ID.")
            return
        
        # Start monitoring
        await bot.run_monitoring_loop()
    
    # Run the bot
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()
