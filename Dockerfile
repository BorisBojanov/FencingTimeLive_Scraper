# Use official Python image
FROM python:3.10-bullseye

# Set the working directory
WORKDIR /app

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright dependencies
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxkbcommon-x11-0 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libgtk-3-0 \
    libgbm1 \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Copy the script
COPY FencingTimeLive_CSV_script.py .

# Define the command to run the script
ENTRYPOINT ["python", "FencingTimeLive_CSV_script.py"]