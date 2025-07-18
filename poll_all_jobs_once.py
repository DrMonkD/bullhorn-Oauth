from poll_to_sheets import connect_to_sheet, get_bullhorn_session
import requests
import json

def poll_all_jobs():
    session = get_bullhorn_session()
    bhrest_token = session["BhRestToken"]
    rest_url = session["restUrl"]

    url = f"{rest_url}search/JobOrder?BhRestToken={bhrest_token}&fields=id,title,dateAdded,isOpen,employmentType,clientCorporation(name)&sort=dateAdded&count=500"
    response = requests.get(url)
    jobs = response.json().get("data", [])

    if not jobs:
        print("No jobs found.")
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

    print(f"✅ Imported {len(jobs)} existing jobs.")

if __name__ == "__main__":
    poll_all_jobs()
