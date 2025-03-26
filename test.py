import asyncio
import csv
import re
import argparse
from playwright.async_api import async_playwright
from collections import defaultdict

'''
TODO: add a round header cell that shows which round the match took place in.
TODO: add a winner header cell that shows which of the who fencers won the match.
'''
base_url = "https://www.fencingtimelive.com"
tableau_scores_url = f"{base_url}/tableaus/scores"

async def fetch_table_html_directly(eid, rid):

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()

        # Step 1: Get tree metadata
        trees_url = f"{base_url}/tableaus/scores/{eid}/{rid}/trees"
        response = await page.request.get(trees_url)
        trees = await response.json()

        if not trees:
            print("No trees found.")
            return None

        tree = trees[0]
        tree_guid = tree["guid"]
        count = tree["numTables"]

        # Step 2: Fetch full tableau HTML directly
        table_url = f"{base_url}/tableaus/scores/{eid}/{rid}/trees/{tree_guid}/tables/0/{count}?refs=0"
        table_response = await page.request.get(table_url)
        html_content = await table_response.text()

        await browser.close()
        return html_content

# Function to check if a string is formatted like a score
def looks_like_score(text):
    return bool(re.search(r"\d+\s*-\s*\d+", text))

async def matrix_of_extracted_tableau_data(page, tableau_url, event_title):
    """Extract tableau data from a tableau page."""
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
    filename="tableau_bracket.csv"
    headers = ["Fencer A", "Fencer B", "Score and Referee"]
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

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        #Solution 1. Open a new browser context so that tableu data is not cut off
        context = await browser.new_context(
            viewport={'width': 3000, 'height': 1080} # Set very wide viewport to avoid having the tableau data cut off
        )
        #option 2. Override $("#tableauPanel").width() via JavaScript injection
        page = await context.new_page()
        
        matrix = await matrix_of_extracted_tableau_data(page, "https://www.fencingtimelive.com/tableaus/scores/B842E0E22FA947FEA4EF37DF113A2FB6/DACE41133DA9407EAD625A2000AAAD0B", "test")
        tableau_matches = extract_fencer_matches(matrix)


        # Debugging output
        print("\nMatrix of extracted tableau data:")
        for row in matrix:
            print(row)

        save_bracket_to_csv(tableau_matches, "tableau_bracket.csv")

        # print("\nExtracted fencer matches:")
        # for index in tableau_matches:
        #     print(index)
        

        await browser.close()

if __name__ == "__main__":
    eid = "B842E0E22FA947FEA4EF37DF113A2FB6"
    rid = "DACE41133DA9407EAD625A2000AAAD0B"
    # html = asyncio.run(fetch_table_html_directly(eid, rid))
    # print(html[:1000])  # print part of the HTML to verify

    asyncio.run(main())