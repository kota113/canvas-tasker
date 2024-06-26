import datetime
import time

import dataset
import requests
from icalendar import Calendar

import sentry_sdk
import utils

db = dataset.connect("mysql://prod@100.65.209.33/prod", engine_kwargs={"pool_recycle": 3600})
users_table = db["users"]

sentry_sdk.init(
    dsn="https://ea04c692eefc0400d68fd41adf0b7779@o476618.ingest.sentry.io/4506608188325888",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,
)


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

            events.append({'title': summary, 'desc': description, 'start_time': dtstart})

    return events


def add_events_to_tasks(access_token, events, tasklist_id):
    existing_tasks = retrieve_existing_tasks(access_token, tasklist_id)
    existing_tasks_titles = [task["title"] for task in existing_tasks]
    for event in events:
        title = event['title']
        if title in existing_tasks_titles:
            # todo: update task instead of skipping
            continue
        description = event['desc']
        start_time = event['start_time']
        # ignore already ended events
        if isinstance(start_time, datetime.datetime):
            # set tzinfo to UTC
            start_time = start_time.replace(tzinfo=datetime.timezone.utc)
            if start_time < datetime.datetime.now(datetime.timezone.utc):
                continue

        elif isinstance(start_time, datetime.date) and start_time < datetime.datetime.today().date():
            continue

        # Add event to tasks
        url = f"https://www.googleapis.com/tasks/v1/lists/{tasklist_id}/tasks"
        # add time if it's date
        if isinstance(start_time, datetime.date):
            start_time = datetime.datetime.combine(start_time, datetime.datetime.min.time())
        headers = {
            "Content-Type": "application/json"
        }
        params = {
            "access_token": access_token
        }

        body = {
            "title": title,
            "notes": description,
            "due": start_time.isoformat() + "Z"
        }
        response = requests.post(url, headers=headers, json=body, params=params)
        response.raise_for_status()


def retrieve_existing_tasks(access_token, tasklist_id):
    url = f"https://www.googleapis.com/tasks/v1/lists/{tasklist_id}/tasks"
    headers = {
        "Content-Type": "application/json",
    }
    params = {
        "access_token": {access_token},
        "showCompleted": "true",
        "showHidden": "true",
        "dueMin": datetime.datetime.now().isoformat() + "Z",
        "maxResults": 100
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()["items"]


def main():
    for user_row in users_table.find():
        try:
            user_id = user_row["user_id"]
            access_token, expiry = utils.validate_token(
                user_row["refresh_token"],
                user_row["access_token"]
            )
            tasklist_id = user_row["tasklist_id"]
            ical_url = user_row["ical_url"]
            data = fetch_ical_data(ical_url)
            events = parse_ical(data)
            add_events_to_tasks(access_token, events, tasklist_id)
            print(f"Added {len(events)} events to {user_id}'s task list")
        except Exception as e:
            print(e)


if __name__ == '__main__':
    main()
