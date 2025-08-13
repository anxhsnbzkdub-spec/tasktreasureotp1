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
import hashlib
from datetime import datetime
from typing import Set, Dict, Any
import json

import requests
from playwright.async_api import async_playwright
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
        # Website credentials and URLs
        self.username = "Roni_dada"
        self.password = "Roni_dada"
        self.login_url = "http://94.23.120.156/ints/login"
        self.sms_url = "http://94.23.120.156/ints/client/SMSCDRStats"
        
        # Telegram Bot credentials
        self.bot_token = "8354306480:AAFPh2CTRZpjOdntLM8zqdM5kNkE6fthqPw"
        self.channel_id = "-1002724043027"
        
        # Initialize Telegram bot
        self.bot = telegram.Bot(token=self.bot_token)
        
        # Store sent message hashes to prevent duplicates
        self.sent_messages: Set[str] = set()
        
        # Playwright browser and page
        self.playwright = None
        self.browser = None
        self.page = None
        
    async def ensure_browsers_installed(self):
        """Ensure Playwright browsers are installed"""
        try:
            logger.info("Checking if Playwright browsers are installed...")
            
            # Try to start playwright and check if chromium is available
            test_playwright = await async_playwright().start()
            
            try:
                # Try to launch chromium to check if it's installed
                test_browser = await test_playwright.chromium.launch(headless=True)
                await test_browser.close()
                logger.info("Playwright browsers are already installed")
                return True
            except Exception as browser_error:
                logger.warning(f"Browser not available: {browser_error}")
                
                # Install browsers
                logger.info("Installing Playwright browsers...")
                import subprocess
                import sys
                
                result = subprocess.run([
                    sys.executable, "-m", "playwright", "install", "chromium"
                ], capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    logger.info("Playwright chromium installed successfully")
                    return True
                else:
                    logger.error(f"Failed to install browsers: {result.stderr}")
                    return False
            finally:
                await test_playwright.stop()
                    
        except Exception as e:
            logger.error(f"Error ensuring browsers installed: {e}")
            return False
    
    async def setup_browser(self):
        """Setup Playwright browser with appropriate options"""
        logger.info("Setting up Playwright browser...")
        
        # Ensure browsers are installed first
        if not await self.ensure_browsers_installed():
            logger.error("Failed to ensure browsers are installed")
            return False
        
        self.playwright = await async_playwright().start()
        
        # Launch browser with options
        try:
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--allow-running-insecure-content',
                    '--ignore-certificate-errors',
                    '--ignore-ssl-errors',
                    '--ignore-certificate-errors-spki-list',
                    '--ignore-certificate-errors-invalid-ca',
                    '--disable-setuid-sandbox',
                ]
            )
        except Exception as launch_error:
            logger.error(f"Failed to launch browser: {launch_error}")
            logger.info("Trying to install browsers again...")
            
            # Last resort: try to install browsers again
            import subprocess
            import sys
            
            result = subprocess.run([
                sys.executable, "-m", "playwright", "install", "chromium"
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info("Browsers reinstalled, trying launch again...")
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-web-security',
                        '--allow-running-insecure-content',
                        '--ignore-certificate-errors',
                        '--ignore-ssl-errors',
                        '--ignore-certificate-errors-spki-list',
                        '--ignore-certificate-errors-invalid-ca',
                        '--disable-setuid-sandbox',
                    ]
                )
            else:
                logger.error("Failed to reinstall browsers")
                return False
        
        # Create new page with user agent
        self.page = await self.browser.new_page(
            user_agent='Mozilla/5.0 (Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        
        logger.info("Playwright browser setup successful")
        return True
    
    async def solve_captcha(self, page_content: str) -> int:
        """Solve simple math captcha"""
        try:
            # Look for captcha pattern in page content
            captcha_match = re.search(r'What is (\d+) \+ (\d+) = \?', page_content)
            if captcha_match:
                num1, num2 = map(int, captcha_match.groups())
                result = num1 + num2
                logger.info(f"Solved captcha: {num1} + {num2} = {result}")
                return result
        except Exception as e:
            logger.error(f"Error solving captcha: {e}")
        
        return 0
    
    async def login_to_website(self) -> bool:
        """Login to the website with captcha solving"""
        try:
            logger.info("Starting login process...")
            
            # Navigate to login page
            await self.page.goto(self.login_url, wait_until='load', timeout=30000)
            
            # Wait for page to load
            await asyncio.sleep(3)
            
            # Get page content for debugging
            page_content = await self.page.content()
            page_title = await self.page.title()
            current_url = self.page.url
            
            logger.info(f"Page title: {page_title}")
            logger.info(f"Current URL: {current_url}")
            
            # Handle SSL warning if present
            if "not secure" in page_title.lower() or "privacy error" in page_content.lower():
                logger.info("Detected SSL warning page, attempting to bypass...")
                
                # Try to click Advanced button
                try:
                    advanced_button = await self.page.query_selector('#details-button')
                    if advanced_button:
                        await advanced_button.click()
                        await asyncio.sleep(2)
                        
                        # Try to click proceed link
                        proceed_link = await self.page.query_selector('#proceed-link')
                        if proceed_link:
                            await proceed_link.click()
                            await asyncio.sleep(3)
                            logger.info("SSL warning bypassed successfully")
                        
                except Exception as ssl_error:
                    logger.warning(f"SSL bypass failed: {ssl_error}")
                    # Try direct navigation
                    await self.page.goto(self.login_url, wait_until='load', timeout=30000)
                    await asyncio.sleep(3)
            
            # Wait for login form elements
            await self.page.wait_for_load_state('networkidle', timeout=15000)
            
            # Get updated page content
            page_content = await self.page.content()
            page_title = await self.page.title()
            current_url = self.page.url
            
            logger.info(f"After SSL handling - Title: {page_title}")
            logger.info(f"After SSL handling - URL: {current_url}")
            
            # Find and fill username field
            username_field = None
            username_selectors = [
                'input[name="username"]',
                'input[id="username"]', 
                'input[type="text"]',
                'input[name*="user"]'
            ]
            
            for selector in username_selectors:
                try:
                    username_field = await self.page.query_selector(selector)
                    if username_field:
                        logger.info(f"Found username field using selector: {selector}")
                        break
                except:
                    continue
            
            if not username_field:
                logger.error("Could not find username field")
                logger.info(f"Page content excerpt: {page_content[:500]}")
                return False
            
            # Clear and fill username
            await username_field.clear()
            await username_field.fill(self.username)
            logger.info("Username entered successfully")
            
            # Find and fill password field
            password_field = None
            password_selectors = [
                'input[name="password"]',
                'input[id="password"]',
                'input[type="password"]',
                'input[name*="pass"]'
            ]
            
            for selector in password_selectors:
                try:
                    password_field = await self.page.query_selector(selector)
                    if password_field:
                        logger.info(f"Found password field using selector: {selector}")
                        break
                except:
                    continue
            
            if not password_field:
                logger.error("Could not find password field")
                return False
            
            # Clear and fill password
            await password_field.clear()
            await password_field.fill(self.password)
            logger.info("Password entered successfully")
            
            # Solve captcha
            captcha_answer = await self.solve_captcha(page_content)
            if captcha_answer > 0:
                captcha_field = None
                captcha_selectors = [
                    'input[name="capt"]',
                    'input[id="capt"]',
                    'input[type="number"]',
                    'input[name*="capt"]'
                ]
                
                for selector in captcha_selectors:
                    try:
                        captcha_field = await self.page.query_selector(selector)
                        if captcha_field:
                            logger.info(f"Found captcha field using selector: {selector}")
                            break
                    except:
                        continue
                
                if captcha_field:
                    await captcha_field.clear()
                    await captcha_field.fill(str(captcha_answer))
                    logger.info(f"Captcha solved and entered: {captcha_answer}")
                else:
                    logger.warning("Could not find captcha field")
            
            # Submit form
            submit_button = None
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button',
                'input[value*="Login"]',
                'button:has-text("Login")'
            ]
            
            for selector in submit_selectors:
                try:
                    submit_button = await self.page.query_selector(selector)
                    if submit_button:
                        logger.info(f"Found submit button using selector: {selector}")
                        break
                except:
                    continue
            
            if not submit_button:
                logger.error("Could not find submit button")
                return False
            
            # Click submit
            await submit_button.click()
            logger.info("Clicked submit button")
            
            # Wait for navigation
            await self.page.wait_for_load_state('networkidle', timeout=10000)
            await asyncio.sleep(3)
            
            # Check if login was successful
            current_url = self.page.url
            logger.info(f"After login URL: {current_url}")
            
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
        """Get country name and flag based on phone number"""
        country_codes = {
            # Major countries
            '1': {'name': 'USA/Canada', 'flag': '🇺🇸'},
            '7': {'name': 'Russia', 'flag': '🇷🇺'},
            '20': {'name': 'Egypt', 'flag': '🇪🇬'},
            '27': {'name': 'South Africa', 'flag': '🇿🇦'},
            '30': {'name': 'Greece', 'flag': '🇬🇷'},
            '31': {'name': 'Netherlands', 'flag': '🇳🇱'},
            '32': {'name': 'Belgium', 'flag': '🇧🇪'},
            '33': {'name': 'France', 'flag': '🇫🇷'},
            '34': {'name': 'Spain', 'flag': '🇪🇸'},
            '36': {'name': 'Hungary', 'flag': '🇭🇺'},
            '39': {'name': 'Italy', 'flag': '🇮🇹'},
            '40': {'name': 'Romania', 'flag': '🇷🇴'},
            '41': {'name': 'Switzerland', 'flag': '🇨🇭'},
            '43': {'name': 'Austria', 'flag': '🇦🇹'},
            '44': {'name': 'United Kingdom', 'flag': '🇬🇧'},
            '45': {'name': 'Denmark', 'flag': '🇩🇰'},
            '46': {'name': 'Sweden', 'flag': '🇸🇪'},
            '47': {'name': 'Norway', 'flag': '🇳🇴'},
            '48': {'name': 'Poland', 'flag': '🇵🇱'},
            '49': {'name': 'Germany', 'flag': '🇩🇪'},
            '51': {'name': 'Peru', 'flag': '🇵🇪'},
            '52': {'name': 'Mexico', 'flag': '🇲🇽'},
            '53': {'name': 'Cuba', 'flag': '🇨🇺'},
            '54': {'name': 'Argentina', 'flag': '🇦🇷'},
            '55': {'name': 'Brazil', 'flag': '🇧🇷'},
            '56': {'name': 'Chile', 'flag': '🇨🇱'},
            '57': {'name': 'Colombia', 'flag': '🇨🇴'},
            '58': {'name': 'Venezuela', 'flag': '🇻🇪'},
            '60': {'name': 'Malaysia', 'flag': '🇲🇾'},
            '61': {'name': 'Australia', 'flag': '🇦🇺'},
            '62': {'name': 'Indonesia', 'flag': '🇮🇩'},
            '63': {'name': 'Philippines', 'flag': '🇵🇭'},
            '64': {'name': 'New Zealand', 'flag': '🇳🇿'},
            '65': {'name': 'Singapore', 'flag': '🇸🇬'},
            '66': {'name': 'Thailand', 'flag': '🇹🇭'},
            '81': {'name': 'Japan', 'flag': '🇯🇵'},
            '82': {'name': 'South Korea', 'flag': '🇰🇷'},
            '84': {'name': 'Vietnam', 'flag': '🇻🇳'},
            '86': {'name': 'China', 'flag': '🇨🇳'},
            '90': {'name': 'Turkey', 'flag': '🇹🇷'},
            '91': {'name': 'India', 'flag': '🇮🇳'},
            '92': {'name': 'Pakistan', 'flag': '🇵🇰'},
            '93': {'name': 'Afghanistan', 'flag': '🇦🇫'},
            '94': {'name': 'Sri Lanka', 'flag': '🇱🇰'},
            '95': {'name': 'Myanmar', 'flag': '🇲🇲'},
            '98': {'name': 'Iran', 'flag': '🇮🇷'},
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
            '239': {'name': 'Sao Tome and Principe', 'flag': '🇸🇹'},
            '240': {'name': 'Equatorial Guinea', 'flag': '🇬🇶'},
            '241': {'name': 'Gabon', 'flag': '🇬🇦'},
            '242': {'name': 'Republic of Congo', 'flag': '🇨🇬'},
            '243': {'name': 'Democratic Republic of Congo', 'flag': '🇨🇩'},
            '244': {'name': 'Angola', 'flag': '🇦🇴'},
            '245': {'name': 'Guinea-Bissau', 'flag': '🇬🇼'},
            '246': {'name': 'British Indian Ocean Territory', 'flag': '🇮🇴'},
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
            '290': {'name': 'Saint Helena', 'flag': '🇸🇭'},
            '291': {'name': 'Eritrea', 'flag': '🇪🇷'},
            '297': {'name': 'Aruba', 'flag': '🇦🇼'},
            '298': {'name': 'Faroe Islands', 'flag': '🇫🇴'},
            '299': {'name': 'Greenland', 'flag': '🇬🇱'},
            '350': {'name': 'Gibraltar', 'flag': '🇬🇮'},
            '351': {'name': 'Portugal', 'flag': '🇵🇹'},
            '352': {'name': 'Luxembourg', 'flag': '🇱🇺'},
            '353': {'name': 'Ireland', 'flag': '🇮🇪'},
            '354': {'name': 'Iceland', 'flag': '🇮🇸'},
            '355': {'name': 'Albania', 'flag': '🇦🇱'},
            '356': {'name': 'Malta', 'flag': '🇲🇹'},
            '357': {'name': 'Cyprus', 'flag': '🇨🇾'},
            '358': {'name': 'Finland', 'flag': '🇫🇮'},
            '359': {'name': 'Bulgaria', 'flag': '🇧🇬'},
            '370': {'name': 'Lithuania', 'flag': '🇱🇹'},
            '371': {'name': 'Latvia', 'flag': '🇱🇻'},
            '372': {'name': 'Estonia', 'flag': '🇪🇪'},
            '373': {'name': 'Moldova', 'flag': '🇲🇩'},
            '374': {'name': 'Armenia', 'flag': '🇦🇲'},
            '375': {'name': 'Belarus', 'flag': '🇧🇾'},
            '376': {'name': 'Andorra', 'flag': '🇦🇩'},
            '377': {'name': 'Monaco', 'flag': '🇲🇨'},
            '378': {'name': 'San Marino', 'flag': '🇸🇲'},
            '380': {'name': 'Ukraine', 'flag': '🇺🇦'},
            '381': {'name': 'Serbia', 'flag': '🇷🇸'},
            '382': {'name': 'Montenegro', 'flag': '🇲🇪'},
            '383': {'name': 'Kosovo', 'flag': '🇽🇰'},
            '385': {'name': 'Croatia', 'flag': '🇭🇷'},
            '386': {'name': 'Slovenia', 'flag': '🇸🇮'},
            '387': {'name': 'Bosnia and Herzegovina', 'flag': '🇧🇦'},
            '389': {'name': 'North Macedonia', 'flag': '🇲🇰'},
            '420': {'name': 'Czech Republic', 'flag': '🇨🇿'},
            '421': {'name': 'Slovakia', 'flag': '🇸🇰'},
            '423': {'name': 'Liechtenstein', 'flag': '🇱🇮'},
            '500': {'name': 'Falkland Islands', 'flag': '🇫🇰'},
            '501': {'name': 'Belize', 'flag': '🇧🇿'},
            '502': {'name': 'Guatemala', 'flag': '🇬🇹'},
            '503': {'name': 'El Salvador', 'flag': '🇸🇻'},
            '504': {'name': 'Honduras', 'flag': '🇭🇳'},
            '505': {'name': 'Nicaragua', 'flag': '🇳🇮'},
            '506': {'name': 'Costa Rica', 'flag': '🇨🇷'},
            '507': {'name': 'Panama', 'flag': '🇵🇦'},
            '508': {'name': 'Saint Pierre and Miquelon', 'flag': '🇵🇲'},
            '509': {'name': 'Haiti', 'flag': '🇭🇹'},
        }
        
        # Clean phone number
        cleaned_number = re.sub(r'[^\d]', '', phone_number)
        
        # Find matching country code (longest match first)
        for code in sorted(country_codes.keys(), key=len, reverse=True):
            if cleaned_number.startswith(code):
                return country_codes[code]
        
        return {'name': 'Unknown', 'flag': '🌍'}
    
    def extract_sms_data(self, row_data: list) -> Dict[str, Any]:
        """Extract and format SMS data from table row"""
        try:
            sms_data = {
                'time': 'Unknown',
                'number': 'Unknown', 
                'country': 'Unknown',
                'country_flag': '🌍',
                'service': 'Unknown',
                'otp_code': 'Unknown',
                'message': 'No message'
            }
            
            # Column mapping: Date, Range, Number, CLI, SMS
            if len(row_data) >= 5:
                sms_data['time'] = row_data[0].strip() if row_data[0] else 'Unknown'
                sms_data['number'] = row_data[2].strip() if row_data[2] else 'Unknown'
                sms_data['service'] = row_data[3].strip() if row_data[3] else 'Unknown'
                sms_data['message'] = row_data[4].strip() if row_data[4] else 'No message'
                
                # Get country info from phone number
                if sms_data['number'] != 'Unknown':
                    country_info = self.get_country_info(sms_data['number'])
                    sms_data['country'] = country_info['name']
                    sms_data['country_flag'] = country_info['flag']
                
                # Extract OTP code from message
                otp_patterns = [
                    r'code[:\s]*(\d{2,3}[-\s]\d{2,3})',
                    r'otp[:\s]*(\d{2,3}[-\s]\d{2,3})',
                    r'verification[:\s]*(\d{2,3}[-\s]\d{2,3})',
                    r'code[:\s]*(\d{3,8})',
                    r'otp[:\s]*(\d{3,8})',
                    r'verification[:\s]*(\d{3,8})',
                    r'(\d{2,3}[-\s]\d{2,3})',
                    r'\b(\d{4,8})\b'
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
        """Escape special characters for Telegram MarkdownV2"""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    def format_message(self, sms_data: Dict[str, Any]) -> str:
        """Format SMS data into Telegram message"""
        try:
            country_name = sms_data.get('country', 'Unknown')
            country_flag = sms_data.get('country_flag', '🌍')
            service = sms_data.get('service', 'Unknown')
            otp_code = sms_data.get('otp_code', 'Unknown')
            
            # Escape special characters for MarkdownV2
            safe_time = self.escape_markdown_v2(sms_data.get('time', 'Unknown'))
            safe_number = self.escape_markdown_v2(sms_data.get('number', 'Unknown'))
            safe_country = self.escape_markdown_v2(country_name)
            safe_service = self.escape_markdown_v2(service)
            safe_message = sms_data.get('message', 'No message')
            
            # Make OTP clickable
            clickable_otp = f"`{otp_code}`" if otp_code != 'Unknown' else 'Unknown'
            
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
        """Generate hash for message to prevent duplicates"""
        return hashlib.md5(message.encode()).hexdigest()
    
    async def test_telegram_connection(self):
        """Test Telegram bot connection"""
        try:
            bot_info = await self.bot.get_me()
            logger.info(f"Bot info: {bot_info.first_name} (@{bot_info.username})")
            
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
    
    async def send_to_telegram(self, message: str) -> bool:
        """Send message to Telegram channel"""
        try:
            message_hash = self.get_message_hash(message)
            if message_hash in self.sent_messages:
                logger.info("Message already sent, skipping duplicate")
                return False
            
            # Try MarkdownV2 first, then fallback
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
                    logger.warning(f"All markdown parsing failed, sending as plain text: {markdown_error}")
                    await self.bot.send_message(
                        chat_id=self.channel_id,
                        text=message,
                        connect_timeout=30,
                        read_timeout=30,
                        write_timeout=30
                    )
            
            self.sent_messages.add(message_hash)
            logger.info("Message sent to Telegram successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error sending to Telegram: {e}")
            return False
    
    async def check_for_new_messages(self) -> list:
        """Check for new SMS messages on the website"""
        try:
            # Navigate to SMS page (this acts as refresh)
            await self.page.goto(self.sms_url, wait_until='networkidle', timeout=30000)
            
            # Wait for table to load
            await asyncio.sleep(3)
            
            # Look for table with headers
            table = await self.page.query_selector('table')
            if not table:
                logger.warning("No table found on SMS page")
                return []
            
            # Get all table rows
            rows = await table.query_selector_all('tbody tr')
            if not rows:
                logger.warning("No table rows found")
                return []
            
            messages = []
            for row in rows:
                try:
                    # Get all cells in the row
                    cells = await row.query_selector_all('td')
                    if len(cells) >= 5:
                        row_data = []
                        for cell in cells:
                            cell_text = await cell.inner_text()
                            row_data.append(cell_text.strip())
                        
                        # Check if row contains SMS-related keywords
                        row_text = ' '.join(row_data).lower()
                        if any(keyword in row_text for keyword in ['whatsapp', 'code', 'verification', 'sms', 'otp']) and len(row_data[0]) > 0:
                            messages.append(row_data)
                            logger.info(f"Found SMS row: {row_data[:5]}...")
                            
                except Exception as row_error:
                    logger.warning(f"Error processing table row: {row_error}")
                    continue
            
            logger.info(f"Found {len(messages)} SMS messages from table")
            return messages
            
        except Exception as e:
            logger.error(f"Error checking for messages: {e}")
            return []
    
    async def run_monitoring_loop(self):
        """Main monitoring loop"""
        try:
            logger.info("Starting OTP monitoring bot...")
            
            # Setup browser
            if not await self.setup_browser():
                logger.error("Failed to setup browser")
                return
            
            # Test Telegram connection
            if not await self.test_telegram_connection():
                logger.error("Failed to connect to Telegram")
                return
            
            # Login to website
            if not await self.login_to_website():
                logger.error("Failed to login to website")
                return
            
            logger.info("Starting continuous monitoring loop (check → refresh → repeat)...")
            
            while True:
                try:
                    logger.info("📋 Checking for new SMS messages...")
                    
                    # Check for new messages
                    messages = await self.check_for_new_messages()
                    
                    # Process each message
                    for row_data in messages:
                        sms_data = self.extract_sms_data(row_data)
                        if sms_data:
                            formatted_message = self.format_message(sms_data)
                            sent = await self.send_to_telegram(formatted_message)
                            if sent:
                                logger.info(f"✅ New OTP sent: {sms_data.get('country', 'Unknown')} - {sms_data.get('otp_code', 'Unknown')}")
                    
                    logger.info("🔄 Refreshing page for next check...")
                    
                except Exception as e:
                    logger.error(f"❌ Error in monitoring loop: {e}")
                    await asyncio.sleep(2)  # Brief pause on error
                    
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            # Cleanup
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()

async def main():
    bot = OTPTelegramBot()
    await bot.run_monitoring_loop()

if __name__ == "__main__":
    asyncio.run(main())