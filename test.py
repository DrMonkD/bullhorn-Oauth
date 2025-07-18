import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Define Google API scope
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Load credentials and authorize client
creds = ServiceAccountCredentials.from_json_keyfile_name("gcreds.json", scope)
client = gspread.authorize(creds)

# Open the sheet (use title from your actual sheet)
sheet = client.open("Bullhorn Job Feed").sheet1

# Append a test row
sheet.append_row(["123456", "Sample Job", "2025-07-18", "TestCorp"])

print("✅ Test row added to Google Sheet.")
