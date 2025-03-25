"""
This Script scrapes tableau results
1. Accepts a tournamen URL as a commans-line argument
2. Extracts the events IDs from the tournament page
3. Extrancts Tableau results for each event
4. scrapes the tableau results for each event
5. Saves the results to a CSV file

Author: Boris Bojanov
Date: 21 Mar 2025
"""
import asyncio
import csv
import re
import argparse
from playwright.async_api import async_playwright
from collections import defaultdict

BASE_URL = "https://www.fencingtimelive.com"

def sanitize_filename(name):
    """Sanitize the tournament name to create a valid filename."""
    return re.sub(r'[<>:"/\\|?*°¬†]', '', name).replace(' ', '_')

def convert_french_to_english(weapon):
    """Convert French weapon names to English."""
    translations = {"épée": "epee", "Épée": "Epee"}
    return translations.get(weapon, weapon)

# Function to check if a string is formatted like a score
def looks_like_score(text):
    return bool(re.search(r"\d+\s*-\s*\d+", text))

"""Fetch the tournament name from the tournament page."""
async def fetch_tournament_name(page, tournament_url):
    await page.goto(tournament_url)
    await page.wait_for_load_state("networkidle")
    try:
        tournament_name = await page.inner_text('[class="desktop tournName"]')
        return tournament_name.strip()
    except Exception as e:
        print(f"Error fetching tournament name: {e}")
        return "Unknown_Tournament"

"""Extract event links from the tournament schedule page."""
async def fetch_event_links(page):
    await page.wait_for_selector("tr")
    rows = await page.query_selector_all("tr")
    event_links = []
    for row in rows:
        if (row_class := await row.get_attribute("class")) == "clickable-row":
            if (path := await row.get_attribute("data-href")):
                event_links.append(path)
    return event_links

""" Extract the tableu page link from the navigation ba."""
async def fetch_tableau_link(page):
    await page.wait_for_selector("li")
    rows = await page.query_selector_all("li")
    for row in rows:
        if (row_class := await row.get_attribute("class")) == "nav-item":
            if (path := await row.get_attribute("data-href")):
                print(path)
                return path

"""Extract the tableu page link from the event page."""
async def fetch_tableau_results(page):
    links = await page.query_selector_all("a[href*='/tableaus/scores/']")
    if not links:
        print("No tableau links found on page.") # Debugging
    for link in links:
        if (path := await link.get_attribute("href")):
            return path
    return None

"""Extract tableau data from a tableau page."""
async def matrix_of_extracted_tableau_data(page, tableau_url, event_title):
    await page.goto(tableau_url)
    await page.wait_for_load_state("networkidle")
    # Wait for the dynamically inserted table to appear
    await page.wait_for_selector("#tableauPanel table.elimTableau")
    # Select all rows in the tableau div with tr tag
    table_rows = await page.query_selector_all("table.elimTableau tr")
    current_rounds = [] #list of round names in the tableau 
    matrix = [] 
    # Extract round labels from the header row
    header_cells = await table_rows[0].query_selector_all("th")
    for cell in header_cells:
        round_label = (await cell.inner_text()).strip()
        current_rounds.append(round_label)
    
    # Extract fencer data from all rows starting at index 2
    # cleans up the data and appends it to the matrix
    for row in table_rows[2:]:
        fencer_data = []
        # Select all cells in a tr tag with td tag
        cells = await row.query_selector_all("td") #[<JSHandle preview=JSHandle@<td class="tbb">…</td>>, <JSHandle preview=JSHandle@node>, <JSHandle preview=JSHandle@node>, <JSHandle preview=JSHandle@node>, <JSHandle preview=JSHandle@node>, <JSHandle preview=JSHandle@node>]
        # print('Cells in a row: ',cells) 
        for cell in cells:
            cell_class = await cell.get_attribute("class")  
            cell_text = (await cell.inner_text()).replace("\xa0"," ").replace("\n", " / ")
            # print('Text in a Cell: ', cell_text)
            fencer_data.append(cell_text)
        matrix.append(fencer_data)      
    return matrix

"""
1. Pair two fencers in the same column.
2. Scan the vertical range between their rows, in the column to the right, to find a cell with a valid score.
3. If none found, default to empty string.
"""
def extract_fencer_matches(matrix):
    matches = []
    matched_rows = set()

    num_rows = len(matrix)
    num_cols = len(matrix[0]) if matrix else 0

    for col in range(num_cols - 1):  # skip last column (no score in col+1)
        current_fencers = []

        for row in range(num_rows):
            name = matrix[row][col].strip()
            if name and row not in matched_rows:
                current_fencers.append((row, name))

                # When we have a pair of fencers:
                if len(current_fencers) == 2:
                    (row1, fencer1), (row2, fencer2) = current_fencers

                    # Mark as matched
                    matched_rows.add(row1)
                    matched_rows.add(row2)

                    # Search for score in column to the right (col+1)
                    score_col = col + 1
                    score = ""

                    # Scan between row1 and row2, inclusive
                    start, end = sorted([row1, row2])
                    for r in range(start, end + 1):
                        if r < num_rows and score_col < num_cols:
                            possible_score = matrix[r][score_col].strip()
                            if looks_like_score(possible_score):
                                score = possible_score
                                break

                    matches.append((fencer1, fencer2, score))
                    
                    current_fencers = []

    return matches

"""Saves matched fencer info to a CSV file."""
def save_bracket_to_csv(matches, filename):
    if not filename:
        filename="tableau_bracket.csv"
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Fencer A", "Fencer B", "Score and Referee"])

        for match in matches:
            writer.writerow([
                match[0],
                match[1],
                match[2]
            ])

    print(f"Bracket saved to {filename}")

async def main(tournament_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={'width': 3000, 'height': 1080} # Set very wide viewport to avoid having the tableau data cut off
        )
        page = await context.new_page()

        tournament_name = await fetch_tournament_name(page, tournament_url)
        tournament_name = sanitize_filename(tournament_name)
        
        await page.goto(tournament_url)
        event_links = await fetch_event_links(page)

        all_tableau_data = []
        all_tableau_matches = []

        for event_path in event_links:
            event_id = event_path.split("/")[-1]
            event_url = f"{BASE_URL}{event_path}"
            await page.goto(event_url)

            tableau_link = await fetch_tableau_results(page)
            if tableau_link:
                tableau_url = f"{BASE_URL}{tableau_link}"
                tableau_data = await matrix_of_extracted_tableau_data(page, tableau_url, event_id)
                grouped_matches = extract_fencer_matches(tableau_data)

                all_tableau_data.extend(tableau_data)
                all_tableau_matches.extend(grouped_matches)

        save_bracket_to_csv(all_tableau_matches, tournament_name + "_paired_matches.csv")
        await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape tableau results from Fencing Time Live.")
    parser.add_argument("tournament_url", help="The URL of the tournament event schedule page.")
    args = parser.parse_args()

    asyncio.run(main(args.tournament_url))
