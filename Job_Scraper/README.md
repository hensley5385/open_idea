# Job Scraper

A robust, asynchronous job scraper designed to competitively search for full-stack developer opportunities across multiple platforms while avoiding bot detection.

## Targeted Markets
- **X (Twitter)**
- **Reddit**
- **WeWorkRemotely**
- **SimplyHired**
- **Hacker News**
- **RemoteOK**

## Features
- **Asynchronous & Concurrent**: Scrapes all sources simultaneously for maximum speed.
- **Anti-Bot Stealth**: Uses Playwright with rotated user-agents and natural delays to bypass security checks.
- **Detailed Results**: Extracts full job descriptions and metadata.

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Install Playwright browsers: `playwright install chromium`
3. Run the scraper: `python scraper.py`
