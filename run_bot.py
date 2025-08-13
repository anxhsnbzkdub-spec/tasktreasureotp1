#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple runner script for the OTP Telegram Bot
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from otp_telegram_bot import OTPTelegramBot

async def main():
    bot = OTPTelegramBot()
    await bot.run_monitoring_loop()

if __name__ == "__main__":
    print("🤖 Starting OTP Telegram Bot...")
    print("Press Ctrl+C to stop the bot")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error running bot: {e}")
