"""
This script scrapes fencing tournament data from the Fencing Time Live website.
It extracts the tournament name, event details, and fencer results.
The data is saved to a CSV file with the tournament name in the filename.
"""


#Import Dependencies
import argparse  # Import argparse for command-line arguments
import asyncio
import re
import csv
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Load environment variables
load_dotenv()

# Constants
BASE_URL = "https://www.fencingtimelive.com"
F = {"C": 10, "J": 20, "S": 30, "O": 30, "V": 20}

"""Clean the tournament name to create a valid filename

Arguments:
name -- Tournament name string

Return: filename string
"""
def sanitize_filename(name):
    """Clean the tournament name to create a valid filename."""
    return re.sub(r'[<>:"/\\|?*°]', '', name).replace(' ', '_')

"""Helper Convert French to English
Arguments:
weapon -- Weapon name in French or English
Returns:
str() -- Weapon name in English
"""
def convertFrenchToEnglish(weapon):
    if weapon == "épée":
        return "epee"
    elif weapon == "Épée":
        return "Epee"
    else:
        return weapon

""" Fetch tournament page
# 	1.	Launch a browser.
#	2.	Navigate to the tournament page provided my command-line argument.
#	3.	Extract the tournament name.

Arguments:
page -- Playwright page object
tournament_url -- URL of the tournament page

Returns:
Tournament name as a string
"""
async def fetch_tournament_info(page, tournament_url):
    """Fetches the tournament name from a given URL."""
    await page.goto(tournament_url)
    await page.wait_for_load_state("networkidle")

    try:
        tournament_name = await page.inner_text('[class="desktop tournName"]')
        return tournament_name.strip()
    except Exception as e:
        print(f"Error fetching tournament name: {e}")
        return "Unknown_Tournament"

""" Extract Event Links
Finds all tr elements.
Extracts data-href attributes.
"""
async def fetch_event_links(page):
    rows = await page.query_selector_all("tr")
    paths = []

    for row in rows:
        row_type = await row.get_attribute("class")
        if row_type == "clickable-row":
            path = await row.get_attribute("data-href") 
            #data-href="/events/view/B842E0E22FA947FEA4EF37DF113A2FB6"
            #path = "/events/view/B842E0E22FA947FEA4EF37DF113A2FB6"
            if path:
                paths.append(path)

    return paths

"""	Process each event
Extracts event title and time.
Fetches fencer results.

Arguments:
page -- Playwright page object
path -- Event path to navigate to
tournament_name -- Name of the tournament

Returns:
List of fencer data dictionaries
"""
async def process_event(page, path, tournament_name):
    """Scrapes data for a single event."""
    await page.goto(BASE_URL + path)
    await page.wait_for_load_state("networkidle")

    title = (await page.inner_text('[class="desktop eventName"]')).strip()
    time = (await page.inner_text('[class="desktop eventTime"]')).strip()

    title_parts = title.split()
    if len(title_parts) == 3:
        title_parts[1] = title_parts[1].split("'")[0]
    elif len(title_parts) == 2:
        title_parts.append(title_parts[1].split("'")[0])
        title_parts[1] = title_parts[0]


        
    
    event_data = {
        "tournament": tournament_name,
        "level": title_parts[0],
        "sex": title_parts[1],
        "weapon": "title_parts",
        "full_text": convertFrenchToEnglish(title_parts[-1]),
        "time": time,
        "event_url": BASE_URL + path
    }

    fencers = await fetch_fencer_results(page)
    for fencer in fencers:
        fencer.update(event_data)  # Merge event details into each fencer record

    return fencers

"""Fetch and store fencer results

Arguments:
page -- Playwright page object
Returns:
List of fencer data dictionaries
"""
async def fetch_fencer_results(page):
    fencers = []
    rows = await page.query_selector_all('table[id="resultList"] > tbody > tr')

    for row in rows:
        data = await row.query_selector_all("td")
        place = str(await data[0].inner_text())
        fencer = await data[1].inner_text()
        club = await data[2].inner_text()
        region = await data[3].inner_text()

        fencers.append({"place": place, "fencer": fencer, "club": club, "region": region})

    return fencers

"""
Writes the scraped data to a dynamically named CSV file.

Arguments:
data -- List of fencer data dictionaries
tournament_name -- Name of the tournament

Returns:
None - writes to CSV file
"""
def save_to_csv(data, tournament_name):
    if not data:
        print("No data to save.")
        return

    filename = f"{sanitize_filename(tournament_name)}_fencing_results.csv"
    headers = data[0].keys()  # Extract column names from the first dictionary

    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)

    print(f"Data successfully saved to {filename}")

def parseArguments():
    parser = argparse.ArgumentParser(description="Scrape fencing tournament data from Fencing Time Live.")
    parser.add_argument("url", help="The tournament URL from fencingtimelive.com")
    args = parser.parse_args()
    return args.url

async def run(tournament_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        tournament_name = await fetch_tournament_info(page, tournament_url)
        event_links = await fetch_event_links(page)
        all_fencers = []

        for path in event_links:
            fencer_data = await process_event(page, path, tournament_name)
            all_fencers.extend(fencer_data)  # Collect data for all events

        await browser.close()

    save_to_csv(all_fencers, tournament_name)  # Pass tournament name to save_to_csv

"""Main function to scrape data and save it to a CSV file."""
async def main(tournament_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        tournament_name = await fetch_tournament_info(page, tournament_url)
        event_links = await fetch_event_links(page)
        all_fencers = []

        for path in event_links:
            fencer_data = await process_event(page, path, tournament_name)
            all_fencers.extend(fencer_data)  # Collect data for all events

        await browser.close()

    save_to_csv(all_fencers, tournament_name)  # Pass tournament name to save_to_csv

if __name__ == "__main__":
    tournament_url = parseArguments()
    asyncio.run(main(tournament_url))
