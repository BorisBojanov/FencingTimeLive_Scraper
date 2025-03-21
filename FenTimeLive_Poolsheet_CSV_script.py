"""
This script scrapes pool results from Fencing Time Live and saves them to a CSV file.
1.	Accepts a tournament URL as a command-line argument.
2.	Extracts event IDs from the tournament page.
3.	Extracts pool results page (rid) from the event.
4.	Extracts pool IDs from JavaScript (var ids).
5.	Scrapes each pool’s results and saves them to a CSV file.

Author: Boris Bojanov
Date: 19 Mar 2025
"""
import asyncio
import csv
import re
import argparse
from playwright.async_api import async_playwright

BASE_URL = "https://www.fencingtimelive.com"

def sanitize_filename(name):
    """Sanitize the tournament name to create a valid filename."""
    return re.sub(r'[<>:"/\\|?*°]', '', name).replace(' ', '_')

def convert_french_to_english(weapon):
    """Convert French weapon names to English."""
    translations = {"épée": "epee", "Épée": "Epee"}
    return translations.get(weapon, weapon)

async def fetch_tournament_name(page, tournament_url):
    """Fetch the tournament name from the tournament page."""
    await page.goto(tournament_url)
    await page.wait_for_load_state("networkidle")
    try:
        tournament_name = await page.inner_text('[class="desktop tournName"]')
        return tournament_name.strip()
    except Exception as e:
        print(f"Error fetching tournament name: {e}")
        return "Unknown_Tournament"

async def fetch_event_links(page):
    """Extract event links from the tournament schedule page."""
    await page.wait_for_selector("tr")
    rows = await page.query_selector_all("tr")
    event_links = []
    for row in rows:
        if (row_class := await row.get_attribute("class")) == "clickable-row":
            if (path := await row.get_attribute("data-href")):
                event_links.append(path)
    return event_links

async def fetch_pools_page_link(page):
    """Extract the pools page link from the event's navigation bar."""
    links = await page.query_selector_all("a[href*='/pools/scores/']")
    for link in links:
        if (href := await link.get_attribute("href")):
            return href
    return None

async def fetch_pool_ids(page):
    """Extract pool IDs from the pools page."""
    try:
        for _ in range(20):
            pool_ids = await page.evaluate("window.ids || []")
            if pool_ids:
                return pool_ids
            await asyncio.sleep(0.5)
        print("Warning: Pool IDs not found after multiple retries.")
        return []
    except Exception as e:
        print(f"Error extracting pool IDs: {e}")
        return []

async def scrape_pool_results(page, event_id, rid, pool_id, tournament_name):
    """Scrape results for a specific pool."""
    pool_url = f"{BASE_URL}/pools/details/{event_id}/{rid}/{pool_id}"
    await page.goto(pool_url)
    await page.wait_for_load_state("networkidle")

    title = (await page.inner_text('[class="desktop eventName"]')).strip()
    title_parts = title.split()
    if len(title_parts) == 3:
        title_parts[1] = title_parts[1].split("'")[0]
    title_parts[2] = convert_french_to_english(title_parts[2])
    results = []
    try:
        rows = await page.query_selector_all("table tbody tr")
        for row in rows:
            columns = await row.query_selector_all("td")
            # print('raw columns: ', await row.inner_text()) # Debuggingg
            # print('columns lenth: ', len(columns)) # Debugging

            try:
                if len(columns) < 4:
                    # print("Skipping row with unexpected number of columns")
                    continue
                elif len(columns) == 6:
                    # Bout Order will always be 6 columns wide
                    # fencer_right_pool_position , fencer_right, fencer_right_touches_scored, fencer_left_touches_scored, fencer_left, fencer_left_pool_position
                    fencer_right_pool_position   = (await columns[0].inner_text()).strip()
                    fencer_right                 = (await columns[1].inner_text()).strip()
                    fencer_right_touches_scored  = (await columns[2].inner_text()).strip()
                    fencer_left_touches_scored   = (await columns[3].inner_text()).strip()
                    fencer_left                  = (await columns[4].inner_text()).strip()
                    fencer_left_pool_position    = (await columns[5].inner_text()).strip()

                    results.append({
                        "Fencer Right Pool Position": fencer_right_pool_position,
                        "Fencer Right": fencer_right,
                        "Fencer Right Touches Scored": fencer_right_touches_scored,
                        "Fencer Left Touches Scored": fencer_left_touches_scored,
                        "Fencer Left": fencer_left,
                        "Fencer Left Pool Position": fencer_left_pool_position
                    })
                elif len(columns) > 6:
                    # Pool Sheet
                    # fencer, pool_position, bouts, number_of_bounts, number_of_victories, victories_per_match, touches_scored, touches_received, indicators
                    fencer = (await columns[0].inner_text()).strip()
                    pool_position = (await columns[1].inner_text()).strip()

                    bouts = []
                    for i in range(2, -6, 1):
                        bouts.append((await columns[i].inner_text()).strip())
                    num_columns = len(columns)
                    pool_size = num_columns - 8
                    raw_bouts = [(await columns[i].inner_text()).strip() for i in range(2, 2 + pool_size)]
                    position_index = int(pool_position) - 1
                    bouts = ["" if i == position_index else raw_bouts[i] for i in range(pool_size)]
                    
                    number_of_bounts = len(bouts)
                    number_of_victories = (await columns[-5].inner_text()).strip()
                    victories_per_match = (await columns[-4].inner_text()).strip()
                    touches_scored = (await columns[-3].inner_text()).strip()
                    touches_received = (await columns[-2].inner_text()).strip()
                    indicators = (await columns[-1].inner_text()).strip()

                    results.append({
                        "Tournament": tournament_name,
                        "Level": title_parts[0],
                        "Sex": title_parts[1],
                        "Weapon": title_parts[2],
                        "Pool ID": pool_id,
                        "Fencer": fencer,
                        "Bouts list": bouts,
                        "Number of Bouts": number_of_bounts,
                        "Pool Position": pool_position,
                        "Victories": number_of_victories,
                        "Victories / Matches": victories_per_match,
                        "Touches Scored": touches_scored,
                        "Touches Received": touches_received, 
                        "Indicators": indicators
                    })

                else:
                    print("Skipping row with unexpected number of columns")
                    continue
            except Exception as e:
                print(f"Error parsing row: {e}")
    except Exception as e:
        print(f"Error scraping pool {pool_id}: {e}")
    return results

def save_to_two_csvs(bout_orders, pool_sheets, tournament_name):
    """Save bout orders and pool sheets into separate CSV files."""
    if bout_orders:
        bout_filename = f"{sanitize_filename(tournament_name)}_bout_orders.csv"
        bout_headers = set()
        for row in bout_orders:
            bout_headers.update(row.keys())
        with open(bout_filename, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(bout_headers))
            writer.writeheader()
            writer.writerows(bout_orders)
        print(f"Bout orders saved to {bout_filename}")

    if pool_sheets:
        sheet_filename = f"{sanitize_filename(tournament_name)}_pool_sheets.csv"
        sheet_headers = set()
        for row in pool_sheets:
            sheet_headers.update(row.keys())
        with open(sheet_filename, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(sheet_headers))
            writer.writeheader()
            writer.writerows(pool_sheets)
        print(f"Pool sheets saved to {sheet_filename}")

async def main(tournament_url):
    """Main function to orchestrate the scraping process."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Fetch the tournament name
        tournament_name = await fetch_tournament_name(page, tournament_url)

        # Navigate to the tournament page
        await page.goto(tournament_url)
        await page.wait_for_load_state("networkidle")

        # Extract event links
        event_links = await fetch_event_links(page)

        all_pool_results = []

        # Iterate through each event
        for event_path in event_links:
            event_id = event_path.split("/")[-1]
            event_url = f"{BASE_URL}{event_path}"

            await page.goto(event_url)
            await page.wait_for_load_state("networkidle")

            # Extract pools page link
            pools_page_link = await fetch_pools_page_link(page)
            if not pools_page_link:
                print(f"Skipping event {event_id} due to missing pools page.")
                continue

            rid = pools_page_link.split("/")[-1]
            pools_page_url = f"{BASE_URL}{pools_page_link}"

            await page.goto(pools_page_url)
            await page.wait_for_load_state("networkidle")

            # Extract pool IDs
            pool_ids = await fetch_pool_ids(page)
            if not pool_ids:
                print(f"No pools found for event {event_id}")
                continue

            # Scrape results for each pool
            for pool_id in pool_ids:
                pool_results = await scrape_pool_results(page, event_id, rid, pool_id, tournament_name)
                all_pool_results.extend(pool_results)

        # Separate data into pool sheets and bout orders
        pool_sheets = [row for row in all_pool_results if "Bouts list" in row]
        bout_orders = [row for row in all_pool_results if "Fencer Right" in row and "Fencer Left" in row]

        # Save to two separate CSV files
        save_to_two_csvs(bout_orders, pool_sheets, tournament_name)

        await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape pool results from Fencing Time Live.")
    parser.add_argument("tournament_url", help="The URL of the tournament's event schedule")
    args = parser.parse_args()

    asyncio.run(main(args.tournament_url))
