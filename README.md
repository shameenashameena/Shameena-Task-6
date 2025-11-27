# Scheduled Cleanup Job (Azure SQL → Blob Storage)

This project implements a Timer-triggered Azure Function that runs nightly to archive old `Orders` records from Azure SQL into Blob Storage as NDJSON files and deletes the archived rows.

## Features

- Timer-triggered function runs daily at **02:00 UTC**.  
- Queries the `Orders` table in Azure SQL for rows older than 30 days.  
- Writes archive files to Blob Storage: `archive/orders/YYYY/MM/DD/orders-<timestamp>.ndjson`.  
- Deletes successfully archived rows from SQL (transactional, batched).  
- Logs operation details including number of rows archived and blob URL.

# Open project in VS Code
Install Python and Azure Functions extensions if not already installed.
Set up a Python virtual environment

python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
pip install -r requirements.txt
Configure local settings (local.settings.json)

# Run the function locally

func start
# Verify
Check local logs for the number of rows processed.
Confirm NDJSON files are created in your Blob Storage emulator or configured storage account.
