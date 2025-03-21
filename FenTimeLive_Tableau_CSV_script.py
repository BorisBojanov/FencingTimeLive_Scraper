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

BASE_URL = "https://www.fencingtimelive.com"

def sanitize_filename(name):
    """Sanitize the tournament name to create a valid filename."""
    return re.sub(r'[<>:"/\\|?*°¬†]', '', name).replace(' ', '_')

"""
This is a tree structure, each match has:
	•	A parent (the next round in the bracket)
	•	Two children (the fencers competing)
	•	A match ID to keep track of each round
    •	Seed, fencer name, club, region, country, score, and referee data
"""
class MatchNode:
    def __init__(self, seed, fencer_name, club, region, country, score=None, referee=None):
        self.seed = seed
        self.fencer_name = fencer_name
        self.club = club
        self.region = region
        self.country = country
        self.score = score
        self.referee = referee
        self.parent = None  # Next round in the tree
        self.left_child = None  # Previous match (left fencer)
        self.right_child = None  # Previous match (right fencer)

    def set_children(self, left, right):
        self.left_child = left
        self.right_child = right
        left.parent = self
        right.parent = self


"""
Parse the tableau data in bottom-up order:
	1.	Start with the initial matches (first round of 64 or 32).
	2.	Link winners to the next round.
	3.	Continue until the final match.
"""
"""
[{'Event': 'B842E0E22FA947FEA4EF37DF113A2FB6', 'Round': 'Table of 64', 'Seed': '1', 'Last Name': 'BUDOVSKYI', 'First Name': 'Borys', 'Club': 'DYN', 'Region': 'British Columbia', 'Country': 'CAN', 'Score': '', 'Referee': ''},
 {'Event': 'B842E0E22FA947FEA4EF37DF113A2FB6', 'Round': 'Table of 32', 'Seed': '1', 'Last Name': 'BUDOVSKYI', 'First Name': 'Borys', 'Club': '', 'Region': '', 'Country': '', 'Score': '', 'Referee': ''},
 {'Event': 'B842E0E22FA947FEA4EF37DF113A2FB6', 'Round': 'Table of 64', 'Seed': '64', 'Last Name': '- BYE -', 'First Name': '', 'Club': '', 'Region': '', 'Country': '', 'Score': '', 'Referee': ''},
 {'Event': 'B842E0E22FA947FEA4EF37DF113A2FB6', 'Round': 'Table of 16', 'Seed': '1', 'Last Name': 'BUDOVSKYI', 'First Name': 'Borys', 'Club': '', 'Region': '', 'Country': '', 'Score': '', 'Referee': ''},
 {'Event': 'B842E0E22FA947FEA4EF37DF113A2FB6', 'Round': 'Table of 64', 'Seed': '33', 'Last Name': 'HU', 'First Name': 'Ben', 'Club': 'CFA', 'Region': 'Ontario', 'Country': 'CAN', 'Score': '15 - 5', 'Referee': 'ROSS Michael'},
 {'Event': 'B842E0E22FA947FEA4EF37DF113A2FB6', 'Round': 'Table of 32', 'Seed': '32', 'Last Name': 'HERNANDEZ BERRON', 'First Name': 'Salvador', 'Club': '', 'Region': '', 'Country': '', 'Score': '', 'Referee': ''},
 {'Event': 'B842E0E22FA947FEA4EF37DF113A2FB6', 'Round': 'Table of 64', 'Seed': '32', 'Last Name': 'HERNANDEZ BERRON', 'First Name': 'Salvador', 'Club': 'EPIC', 'Region': 'Alberta', 'Country': 'CAN', 'Score': '15 - 10', 'Referee': 'Ref MANYOKI Daniel WAT / Ontario /  CAN'}
"""
def build_bracket(matches_data):
    """Builds a bracket tree from a list of match data."""
    match_nodes = {}  # Store MatchNode objects by match ID

    for match in matches_data:
        match_id = match["match_id"]
        seed = match["Seed"]
        fencer_name = match["Last Name"] + " " + match["First Name"]
        club = match["Club"]
        region = match["Region"]
        country = match["Country"]
        score = match["Score"]
        referee = match["Referee"]

        match_nodes[match_id] = MatchNode(seed, fencer_name, club, region, country, score, referee)

    # Link winners to the next round (parent nodes)
    for match in matches_data:
        match_id = match["match_id"]
        next_match_id = match.get("next_match_id")  # The match this feeds into
        if next_match_id and next_match_id in match_nodes:
            parent_match = match_nodes[next_match_id]
            if not parent_match.left_child:
                parent_match.set_children(match_nodes[match_id], parent_match.right_child)
            else:
                parent_match.set_children(parent_match.left_child, match_nodes[match_id])

    return match_nodes

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

async def fetch_tableau_link(page):
    """ Extract the tableu page link from the navigation ba."""
    await page.wait_for_selector("li")
    rows = await page.query_selector_all("li")
    for row in rows:
        if (row_class := await row.get_attribute("class")) == "nav-item":
            if (path := await row.get_attribute("data-href")):
                print(path)
                return path
            
async def fetch_tableau_results(page):
    """Extract the tableu page link from the event page."""
    links = await page.query_selector_all("a[href*='/tableaus/scores/']")
    if not links:
        print("No tableau links found on page.") # Debugging
    for link in links:
        if (path := await link.get_attribute("href")):
            return path
    return None

async def extract_tableau_data(page, tableau_url, event_title):
    """Extract tableau data from a tableau page."""
    await page.goto(tableau_url)
    await page.wait_for_selector("table.elimTableau")

    # Select all rows in the tableau div with tr tag
    rows = await page.query_selector_all("table.elimTableau tr")

    results = []
    current_rounds = []

    # Extract round labels from the header row
    header_cells = await rows[0].query_selector_all("th")
    for cell in header_cells:
        round_label = await cell.inner_text()
        current_rounds.append(round_label.strip())

    # Iterate through the tableau div rows tr elements
    for row in rows[1:]:

        # Select all cells in a tr element with td tag
        cells = await row.query_selector_all("td")

        # Extract data from each cell, use the column index to find the corresponding round
        for col_index, cell in enumerate(cells):

            #get the class attribute of the cell
            cell_class = await cell.get_attribute("class") or ""

            # Extract data from the cell based on the class attribute
            if "tbb" in cell_class or "tbbr" in cell_class:
                seed_element = await cell.query_selector(".tseed")
                lastname_element = await cell.query_selector(".tcln")
                firstname_element = await cell.query_selector(".tcfn")

                club_elements = await cell.query_selector(".tcaff") #format <span class="tcaff"><br>EPIC / Alberta / <span class="flag flagCAN"></span>CAN</span>
                club_info = await club_elements.inner_text() if club_elements else "" #format: \nEPIC / Alberta / CAN
                club_info = club_info.split("/") if club_info else [] #format: ['\nEPIC ', ' Alberta ', ' CAN']
                club_info = [info.strip("\n") for info in club_info]    #format: ['EPIC', 'Alberta', 'CAN']
                
                seed = await seed_element.inner_text() if seed_element else "" #format: (62)\xa0
                seed = seed.replace("\xa0", "").strip("()") # format: 62

                last_name = await lastname_element.inner_text() if lastname_element else ""
                first_name = await firstname_element.inner_text() if firstname_element else ""

                club_name = club_info[0].strip() if club_info else ""
                club_region = club_info[1].strip() if club_info else ""
                club_country = club_info[2].strip() if club_info else ""

                # Append the extracted data to the results list.
                # added placeholder for the score and referee
                results.append({
                        "Event": event_title,
                        "Round": current_rounds[col_index] if col_index < len(current_rounds) else "",
                        "Seed": seed,
                        "Last Name": last_name,
                        "First Name": first_name,
                        "Club": club_name,
                        "Region": club_region,
                        "Country": club_country,
                        "Score": "", # placeholder
                        "Referee": "" # placeholder 
                    })
            elif "tscoref" in cell_class:

                score_element = await cell.query_selector(".tsco") #<td class="tscoref"><span class="tsco">15 - 10<br><span class="tref">Ref MANYOKI Daniel WAT / Ontario / <span class="flag flagCAN"></span> CAN</span>&nbsp;</span></td>
                score_data = (await score_element.inner_text()).split("\n") if score_element else "" #15 - 5\nRef ROSS Michael \xa0
                # print(score_data)

                if len(score_data) > 1:
                    score = score_data[0] if score_data else "" #15 - 5
                    raw_referee = score_data[1] if score_data else "" #Ref ROSS Michael \xa0
                    raw_referee = raw_referee.replace("\xa0", "").strip() if raw_referee else "" #Ref ROSS Michael
                    raw_referee = raw_referee.split("Ref")[0:] if raw_referee else "" #['', ' MANYOKI Daniel WAT / Ontario /  CAN']
                    referee_info = raw_referee[1].split("/") if raw_referee else "" # [MANYOKI Daniel WAT , Ontario ,  CAN]
                    referee = [info.strip() for info in referee_info] if referee_info else "" # ['MANYOKI Daniel WAT', 'Ontario', 'CAN']
                    # print(score, referee)

                    if results:
                        results[-1]["Score"] = score #15 - 5
                        results[-1]["Referee"] = referee #['MANYOKI Daniel WAT', 'Ontario', 'CAN']
                    
                # print("Results: ",results,'\n')
    # print("Results: ",results,'\n')
    return results

def save_bracket_to_csv(matches, filename="tableau_bracket.csv"):
    """Saves bracket tree structure to a CSV file."""
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Match ID", "Seed", "Fencer", "Club", "Score", "Referee", "Next Match ID"])

        for match_id, match in matches.items():
            writer.writerow([
                match_id,
                match.seed,
                match.fencer_name,
                match.club,
                match.score or "",
                match.referee or "",
                match.parent.match_id if match.parent else ""
            ])

    print(f"Bracket saved to {filename}")

def save_to_csv(data, tournament_name):
    """Save the tableau data to a CSV file."""
    if not data:
        print("No data to save.")
        return

    filename = f"{sanitize_filename(tournament_name)}_tableau_results.csv"
    headers = sorted(set().union(*(row.keys() for row in data)))

    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)

    print(f"Tableau data saved to {filename}")

async def main(tournament_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        tournament_name = await fetch_tournament_name(page, tournament_url)
        await page.goto(tournament_url)
        event_links = await fetch_event_links(page)

        all_tableau_data = []

        for event_path in event_links:
            event_id = event_path.split("/")[-1]
            event_url = f"{BASE_URL}{event_path}"
            await page.goto(event_url)

            tableau_link = await fetch_tableau_results(page)
            if tableau_link:
                tableau_url = f"{BASE_URL}{tableau_link}"
                tableau_data = await extract_tableau_data(page, tableau_url, event_id)
                all_tableau_data.extend(tableau_data)

        save_to_csv(all_tableau_data, tournament_name)
        await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape tableau results from Fencing Time Live.")
    parser.add_argument("tournament_url", help="The URL of the tournament event schedule page.")
    args = parser.parse_args()

    asyncio.run(main(args.tournament_url))
