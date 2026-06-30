# Setup

1. **Clone the Repository (or Copy the Files)**

   If you haven’t already, copy these files to your device:
   - `Dockerfile`
   - `FencingTimeLive_CSV_script.py`
   - `requirements.txt`

2. **Build the Docker Image**

   In the folder with all three files, run:

   ```bash
   docker build -t fencing_scraper .
   ```

   This process may take a few minutes as it installs dependencies and Playwright browsers.

## Usage

3.**Run the FencingTimeLive_CSV_script**
   To scrape any tournament page for the tournament results, use the following command:

   ```bash
   docker run --rm fencing_scraper "<tournament_url>"
   ```

   **Example:**

   ```bash
   docker run --rm fencing_scraper "https://www.fencingtimelive.com/tournaments/eventSchedule/46C01711F6B24BD1A8C4A28C2F2C0CC4"
   ```

   This will scrape the data and generate a CSV file named:
   `<Tournament_Name>_fencing_results.csv`

4.**Save CSV Output to Local Storage**

   Ensure the `output/` folder exists or create it if it doesn't. To mount the output folder and persist the CSV, run:

   ```bash
   docker run --rm -v $(pwd)/output:/app/output fencing_scraper "<tournament_url>"
   ```

   The CSV file will be saved in the `output/` folder inside your device.

## Local (Python) Setup & Usage

If you prefer to run the scrapers directly with Python instead of Docker, use `runAllTheFencingTimeScripts.py`, which runs the pool sheet, tableau, and results scrapers in one go.

1. **Install dependencies**

   Use the same Python interpreter you plan to run the scripts with (e.g. `python3`):

   ```bash
   pip3 install -r requirements.txt
   ```

2. **Install the Playwright browser**

   The `playwright` package also needs its Chromium browser binary:

   ```bash
   python3 -m playwright install chromium
   ```

3. **Log in to Fencing Time Live (required)**

   Fencing Time Live requires you to be logged in to view tournament data. Run the login helper once to save your session:

   ```bash
   python3 login.py
   ```

   A browser window opens — sign in (Google or email/password), then return to the terminal and press **Enter**. Your session is saved to `auth_state.json` and reused automatically by the scrapers. Re-run this whenever the session expires.

4. **Run all scrapers**

   ```bash
   python3 runAllTheFencingTimeScripts.py "<tournament_url>"
   ```

   **Example:**

   ```bash
   python3 runAllTheFencingTimeScripts.py "https://www.fencingtimelive.com/tournaments/eventSchedule/4F5E7D615E7740DC945894E7CB58EC24#today"
   ```

   This generates CSV files in the current folder for pool sheets, bout orders, paired matches, and results.

## Automation

5.**Automate the Scraper with cron**

If you want to schedule the scraper to run automatically at 2 AM every day, add a cron job:

```bash
crontab -e
```

This will run the scraper daily and save the CSV file automatically. Ensure that Docker has the necessary permissions to run the cron job.

## Troubleshooting

### Docker

If the **Docker Build Fails**.

- Ensure `requirements.txt` does NOT include `asyncio` or `re`.
- Make sure you have Docker installed and running.

If **Docker Run Error: No Such File or Directory**

- Make sure the Dockerfile uses `ENTRYPOINT` instead of `CMD`.
- Rebuild the image and run it again:

   ```bash
   docker build -t fencing_scraper .
   docker run --rm fencing_scraper "<tournament_url>"
   ```

### Local (Python)

**`ModuleNotFoundError: No module named 'dotenv'`**

Dependencies aren't installed for the interpreter you're using. Install them with the *same* Python you run the script with (for example, if you run `python3.14 ...`, install with `pip3.14 install ...`):

```bash
pip3 install -r requirements.txt
```

**`BrowserType.launch: Executable doesn't exist ...` (Playwright)**

The Chromium browser binary hasn't been downloaded yet. Run:

```bash
python3 -m playwright install chromium
```

**Scraper hangs then fails with `Timeout 30000ms exceeded` (waiting for `tr` or `tournName`), or the page redirects to `/account/login`**

Your saved login session is missing or expired — Fencing Time Live requires you to be logged in. Re-create the session with `login.py`, then re-run the scraper:

```bash
python3 login.py
```

## Project Structure

```text
FencingTimeLiveProject/
│── Dockerfile  # Defines the Docker container environment
│── runAllTheFencingTimeScripts.py  # Runs all scrapers for a tournament URL
│── Poolsheet_FencingTimeLive_CSV_script.py  # Scrapes pool sheets / bout orders
│── Tableau_FencingTimeLive_CSV_script.py  # Scrapes the elimination tableau
│── Results_FencingTimeLive_CSV_script.py  # Scrapes final results
│── login.py  # One-time login helper; saves auth_state.json
│── auth.py  # Loads the saved login session for the scrapers
│── auth_state.json  # Saved login session (created by login.py)
│── Readme.md
│── requirements.txt  # Python dependencies
```
