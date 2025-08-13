#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple runner script for the OTP Telegram Bot
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from otp_telegram_bot import main

if __name__ == "__main__":
    print("🤖 Starting OTP Telegram Bot...")
    print("Press Ctrl+C to stop the bot")
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error running bot: {e}")
