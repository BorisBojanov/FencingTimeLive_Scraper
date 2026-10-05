'''
This script will run all the individual scraping scripts for FencingTimeLive.

Poolsheet_FencingTimeLive_CSV_script.py 
Tableau_FencingTimeLive_CSV_script.py
Results_FencingTimeLive_CSV_script.py

By default it runs on every URL in tournament_urls.txt (or --file PATH).
Use --url to run on just one tournament URL from fencingtimelive.com.
Usage:
    python3.13 runAllTheFencingTimeScripts.py [--url <tournament_url>] [--file <path>]

Example:
    python3.13 runAllTheFencingTimeScripts.py --url "https://www.fencingtimelive.com/tournaments/eventSchedule/139B9901A42841D0A83B3B451DD2E78C#today"

Author: Boris Bojanov
Date: Dec 5, 2025
'''

import argparse  # Import argparse for command-line arguments
import asyncio
import re
import csv
from dotenv import load_dotenv
from playwright.async_api import async_playwright

from Poolsheet_FencingTimeLive_CSV_script import main as run_poolsheet
from Tableau_FencingTimeLive_CSV_script import main as run_tableau
from Results_FencingTimeLive_CSV_script import main as run_results

def parseArguments():
    parser = argparse.ArgumentParser(description="Scrape fencing tournament data from Fencing Time Live.")
    parser.add_argument("--url", help="Run on this single tournament URL instead of the URLs in the file")
    parser.add_argument("--file", default="tournament_urls.txt", help="File containing tournament URLs, one per line (default: tournament_urls.txt)")
    return parser.parse_args()

async def main(tournament_url):
    await run_poolsheet(tournament_url)
    await run_tableau(tournament_url)
    await run_results(tournament_url)

async def textInput():
    args = parseArguments()

    if args.url:
        urls = [args.url]
    else:
        with open(args.file, 'r') as file:
            urls = [line.strip() for line in file.readlines() if line.strip()]

    for tournament_url in urls:
        print(f"Running scripts for tournament URL: {tournament_url}")
        await main(tournament_url)

if __name__ == "__main__":
    asyncio.run(textInput())
