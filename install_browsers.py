#!/usr/bin/env python3
"""
Install Playwright browsers for deployment
"""

import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def install_browsers():
    """Install Playwright browsers"""
    try:
        logger.info("Installing Playwright browsers...")
        
        # Install chromium browser
        result = subprocess.run([
            sys.executable, "-m", "playwright", "install", "chromium"
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.info("Playwright chromium browser installed successfully")
            logger.info(result.stdout)
        else:
            logger.error(f"Failed to install Playwright browsers: {result.stderr}")
            return False
            
        # Install system dependencies
        result = subprocess.run([
            sys.executable, "-m", "playwright", "install-deps", "chromium"
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.info("Playwright system dependencies installed successfully")
            logger.info(result.stdout)
        else:
            logger.warning(f"System dependencies installation had issues: {result.stderr}")
            # Continue anyway as this might work
            
        return True
        
    except Exception as e:
        logger.error(f"Error installing Playwright browsers: {e}")
        return False

if __name__ == "__main__":
    success = install_browsers()
    if success:
        logger.info("✅ Playwright setup completed successfully")
    else:
        logger.error("❌ Playwright setup failed")
        sys.exit(1)
