
'''
This script will run all the individual scraping scripts for FencingTimeLive.

Poolsheet_FencingTimeLive_CSV_script.py 
Tableau_FencingTimeLive_CSV_script.py
Results_FencingTimeLive_CSV_script.py
'''

import argparse  # Import argparse for command-line arguments
import asyncio
import re
import csv
from dotenv import load_dotenv
from playwright.async_api import async_playwright

from Poolsheet_FencingTimeLive_CSV_script import run as run_poolsheet
from Tableau_FencingTimeLive_CSV_script import run as run_tableau
from Results_FencingTimeLive_CSV_script import run as run_results

def parseArguments():
    parser = argparse.ArgumentParser(description="Scrape fencing tournament data from Fencing Time Live.")
    parser.add_argument("url", help="The tournament URL from fencingtimelive.com")
    args = parser.parse_args()
    return args.url

async def main(tournament_url):
    await run_poolsheet(tournament_url)
    await run_tableau(tournament_url)
    await run_results(tournament_url)

if __name__ == "__main__":
    tournament_url = parseArguments()
    asyncio.run(main(tournament_url))