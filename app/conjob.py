from datetime import datetime, timedelta
import requests
import schedule
import time as t
from app import db, create_app
from app.models import User
from app.encryption import decrypt_data
import pika
import json

app = create_app()

LINE_ACCESS_TOKEN = "YMiJ43NIxV+aauc8TpYPGMcQsX07v5+oP8MWwTcJW9NQMGVT8RdrX5zLoMv58PF+zPTaToZZQrH3mCOCEe9UPBf75Womddh64LmOaLDJfh6Yo3HNmkk/IESDUqN9IqdJkJ8zUbYOumbOgSiGykEx6wdB04t89/1O/w1cDnyilFU="
LINE_API_URL = "https://api.line.me/v2/bot/message/push"

headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + LINE_ACCESS_TOKEN,
}

def send_message(to, message):
    payload = {
        "to": to,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }
    response = requests.post(LINE_API_URL, headers=headers, json=payload)
    print("Message sent. Response Status Code:", response.status_code)

def publish_task(task):
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='task_queue', durable=True)
    
    message = {
        'customer_id': task.customer_id,
        'time': task.time,
        'task': task.task,
        'key': task.key,
    }
    
    channel.basic_publish(
        exchange='',
        routing_key='task_queue',
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
        ))
    connection.close()

def check_and_send_notifications():
    current_time = datetime.now().time()
    current_date = datetime.now().date()
    with app.app_context():
        tasks = User.query.filter_by(date=current_date).all()
        for task in tasks:
            task_time = datetime.strptime(task.time, "%H:%M").time()
            notification_time = (datetime.combine(datetime.today(), task_time) - timedelta(minutes=15)).time()
            if notification_time <= current_time < task_time:
                try:
                    publish_task(task)
                    if task.key_send == "SEND_MESSAGE_KEY":  
                        send_message(task.customer_id, task.task)
                        task.key_send = "MESSAGE_SENT"
                        db.session.commit()
                except Exception as e:
                    print(f"Error publishing task {task.id}: {e}")

def schedule_notifications():
    schedule.every().minute.do(check_and_send_notifications)

    while True:
        schedule.run_pending()
        t.sleep(1)
