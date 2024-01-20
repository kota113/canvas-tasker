import time
from datetime import datetime

import dataset
import requests
from icalendar import Calendar

import utils

db = dataset.connect("mysql://prod@100.65.209.33/prod", engine_kwargs={"pool_recycle": 3600})
users_table = db["users"]


def fetch_ical_data(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.text


def parse_ical(ical_string):
    cal = Calendar.from_ical(ical_string)
    events = []
    for component in cal.walk():
        if component.name == "VEVENT":
            summary = str(component.get('summary'))
            description = str(component.get('description'))
            dtstart = component.get('dtstart').dt

            # Format datetime objects for readability
            if isinstance(dtstart, datetime):
                dtstart = dtstart.strftime('%Y-%m-%d %H:%M:%S')
            else:
                dtstart = dtstart.strftime('%Y-%m-%d')

            events.append({'title': summary, 'desc': description, 'start_time': dtstart})

    return events


def add_events_to_tasks(access_token, events, task_list_id):
    for event in events:
        title = event['title']
        description = event['desc']
        start_time = event['start_time']

        # Add event to tasks
        url = f"https://www.googleapis.com/tasks/v1/lists/{task_list_id}/tasks"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        body = {
            "title": title,
            "notes": description,
            "due": start_time
        }
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()


def main():
    for user_row in users_table.find():
        user_id = user_row["user_id"]
        access_token = utils.validate_token(
            user_row["refresh_token"],
            user_row["access_token"],
            user_row["expiry"]
        )
        task_list_id = user_row["tasklist_id"]
        ical_url = user_row["ical_url"]
        data = fetch_ical_data(ical_url)
        events = parse_ical(data)
        add_events_to_tasks(access_token, events, task_list_id)
        print(f"Added {len(events)} events to {user_id}'s task list")


if __name__ == '__main__':
    while True:
        main()
        time.sleep(60)
