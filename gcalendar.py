import datetime
import pickle
import os.path
import google.auth
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# Define the scopes required for accessing the Calendar API
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Define the path to your client credentials JSON file
CLIENT_CREDENTIALS_FILE = '.google_calendar_credentials.json'


def authenticate_google_calendar():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def create_calendar_event(service, summary, start_time, end_time):
    event = {
        'summary': summary,
        'start': {
            'dateTime': start_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'timeZone': 'Your_Time_Zone',
        },
        'end': {
            'dateTime': end_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'timeZone': 'Your_Time_Zone',
        },
    }
    event = service.events().insert(calendarId='primary', body=event).execute()
    print('Event created: %s' % (event.get('htmlLink')))




if __name__ == "__main__":
    creds = authenticate_google_calendar()
    service = build('calendar', 'v3', credentials=creds)

    summary = 'Meeting with John'
    start_time = datetime.datetime(2023, 6, 15, 10, 0, 0)
    end_time = datetime.datetime(2023, 6, 15, 11, 0, 0)

    create_calendar_event(service, summary, start_time, end_time)

