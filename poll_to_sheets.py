import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from auth_utils import get_bullhorn_session

def save_last_timestamp(ts):
    with open("last_checked.txt", "w") as f:
        f.write(str(ts))

def load_last_timestamp():
    try:
        with open("last_checked.txt", "r") as f:
            return int(f.read())
    except:
        return 0

def connect_to_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("gcreds.json", scope)
    client = gspread.authorize(creds)
    return client.open("Job Board").sheet1

def poll_and_write():
    session = get_bullhorn_session()
    bhrest_token = session["BhRestToken"]
    rest_url = session["restUrl"]
    last_checked = load_last_timestamp()

    url = f"{rest_url}search/JobOrder?BhRestToken={bhrest_token}&fields=id,title,dateAdded,isOpen,employmentType,clientCorporation(name)&where=dateAdded>{last_checked}&sort=dateAdded&count=50"
    response = requests.get(url)
    jobs = response.json().get("data", [])

    if not jobs:
        print("No new jobs.")
        return

    sheet = connect_to_sheet()

    for job in jobs:
        sheet.append_row([
            job.get("id"),
            job.get("title"),
            job.get("dateAdded"),
            job.get("employmentType", ""),
            job.get("clientCorporation", {}).get("name", "")
        ])

    latest_timestamp = max(job["dateAdded"] for job in jobs)
    save_last_timestamp(latest_timestamp)
    print(f"✅ Added {len(jobs)} new jobs to the sheet.")

if __name__ == "__main__":
    poll_and_write()
