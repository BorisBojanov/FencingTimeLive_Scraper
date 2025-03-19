1. Clone the Repository (or Copy the Files)

If you haven’t already, copy these files to your Device:
	•	Dockerfile
	•	FencingTimeLive_CSV_script.py
	•	requirements.txt

2. Build the Docker image
In the folder with all three files: 
    docker build -t fencing_scraper .

This process may take a few minutes as it installs dependencies and Playwright browsers.

3. Run the FencingTimeLive_CSV_script

To scrape any tournament page, for the tournament results, use the following command:
docker run --rm fencing_scraper "<tournament_url>"

Example:
docker run --rm fencing_scraper "https://www.fencingtimelive.com/tournaments/eventSchedule/46C01711F6B24BD1A8C4A28C2F2C0CC4"

This will scrape the data and generate a CSV file named:
<Tournament_Name>_fencing_results.csv

4. Save CSV Output to Local Storage
docker run --rm -v $(pwd)/output:/app/output fencing_scraper "<tournament_url>"

The CSV file will be saved in the output/ folder inside your Device.



Automate the Scraper with cron
If you want to schedule the scraper to run automatically at 2 AM every day, add a cron job:
crontab -e

This will run the scraper daily and save the CSV file automatically.


Troubleshooting

Docker Build Fails
	•	Ensure requirements.txt does NOT include asyncio, re, or argparse.
	•	Make sure you have Docker installed and running.

Docker Run Error: No Such File or Directory
	•	Make sure the Dockerfile uses ENTRYPOINT instead of CMD.
	•	Rebuild the image and run it again:

docker build -t fencing_scraper .
docker run --rm fencing_scraper "<tournament_url>"

Project Structure
FencingTimeLiveProject/
│── Dockerfile  # Defines the Docker container environment
│── FencingTimeLive_CSV_script.py  # Python script for web scraping
│── requirements.txt  # Python dependencies
│── output/  # (Optional) Stores CSV results if using volume mounting