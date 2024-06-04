import os
import pickle
import logging
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow  
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from .encryption import encrypt_data
from cryptography.fernet import Fernet
import redis
import logging
from datetime import datetime, timedelta
from flask import Flask
from sqlalchemy import func
from app.models import User, db

app = Flask(__name__)

redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

def get_credentials():
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    creds = None

    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return creds

def add_event_to_google_calendar(task, date_obj, time_obj):
    try:
        creds = get_credentials()
        service = build('calendar', 'v3', credentials=creds)

        event_start = datetime.combine(date_obj, time_obj)
        event_end = event_start + timedelta(hours=1)

        event = {
            'summary': task,
            'start': {
                'dateTime': event_start.isoformat(),
                'timeZone': 'Asia/Bangkok',
            },
            'end': {
                'dateTime': event_end.isoformat(),
                'timeZone': 'Asia/Bangkok',
            },
        }

        created_event = service.events().insert(calendarId='primary', body=event).execute()
        logging.info(f'Event created: {created_event.get("htmlLink")}')

        return created_event.get('id')
    except Exception as e:
        logging.error(f"เกิดข้อผิดพลาดในการเพิ่มข้อมูลลงใน Google Calendar: {e}")
        raise

def delete_event_from_google_calendar(event_id):
    try:
        creds = get_credentials()
        service = build('calendar', 'v3', credentials=creds)

        service.events().delete(calendarId='primary', eventId=event_id).execute()
        logging.info(f'Event deleted: {event_id}')
    except Exception as e:
        logging.error(f"เกิดข้อผิดพลาดในการลบข้อมูลจาก Google Calendar: {e}")
        raise

def all_task_count(date, status, user_id):
    date_str = date.strftime("%d/%m/%Y")
    redis_key = f"task_count:{user_id}:{date_str}"
    redis_client.hincrby(redis_key, "total", 1)
    if status == "success":
        redis_client.hincrby(redis_key, "success", 1)
    counts = redis_client.hgetall(redis_key)
    logging.debug(f"all_task_count: {redis_key} - {counts}")

def task_count_success(date, status, user_id):
    date_str = date.strftime("%d/%m/%Y")
    redis_key = f"task_count:{user_id}:{date_str}"
    redis_client.hincrby(redis_key, "total", -1)
    if status == "success":
        redis_client.hincrby(redis_key, "success", -1)
    counts = redis_client.hgetall(redis_key)
    logging.debug(f"task_count_success: {redis_key} - {counts}")



def format_room_flex(data):
    bubble_list = []
    for item in data:
        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "ตารางงาน",
                        "weight": "bold",
                        "size": "xl"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "lg",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"งาน : {item['task']}",
                                "wrap": True,
                                "size": "sm"
                            },
                            {
                                "type": "text",
                                "text": f"ว/ด/ป : {item['date']}",
                                "wrap": True,
                                "size": "sm"
                            },
                            {
                                "type": "text",
                                "text": f"เวลา : {item['time']}",
                                "wrap": True,
                                "size": "sm"
                            },
                            {
                                "type": "text",
                                "text": f"สถานะ : {item['status']}",
                                "wrap": True,
                                "size": "sm"
                            }
                        ]
                    },
                ]
            }
        }
        bubble_list.append(bubble)
    carousel = {
        "type": "carousel",
        "contents": bubble_list
    }
    return carousel

def botnoipayload(flexdata):
    out = {
        "response_type": "object",
        "line_payload": [{
            "type": "flex",
            "altText": "Upcoming Events",
            "contents": flexdata
        }]
    }
    return out

def get_task_counts(date, user_id):
    date_str = date.strftime("%d/%m/%Y")
    redis_key = f"task_count:{user_id}:{date_str}"
    counts = redis_client.hgetall(redis_key)
    logging.debug(f"get_task_counts: {redis_key} - {counts}")
    return {
        'total': int(counts.get(b'total', 0)),
        'success': int(counts.get(b'success', 0))
    }

def get_task_counts_from_db(start_date, end_date, customer_id):

    user = User.query.filter_by(customer_id=customer_id).first()
    if not user:
      return {'error': 'Customer ID not found'}

    success_tasks = (
      User.query.filter(
        User.customer_id == customer_id,
        User.status == 'success',
        User.date >= start_date,
        User.date <= end_date
      ).count()
    )

    total_tasks = (
      User.query.filter(
        User.customer_id == customer_id,
        User.date >= start_date,
        User.date <= end_date
      ).count()
    )

    return {
      'success_tasks': success_tasks,
      'total_tasks': total_tasks
    }




    