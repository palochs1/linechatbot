from app import create_app
from app.conjob import schedule_notifications
import threading
import logging
import pika
import json
from datetime import datetime
from app.models import User
from app.conjob import send_message

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = create_app()

def run_scheduler():
    logging.debug("Starting scheduler")
    try:
        schedule_notifications()
    except Exception as e:
        logging.error(f"Scheduler error: {e}")

def callback(ch, method, properties, body):
    logging.debug("Received message")
    task = json.loads(body)
    with app.app_context():
        try:
            customer_id = (task['customer_id'])
            message = f"คุณมีงาน '{task['task']}' ที่จะต้องทำเวลา {task['time']}"
            send_message(customer_id, message)
            logging.info(f"Message sent to {customer_id}")
        except Exception as e:
            logging.error(f"Error processing task {task['task_id']}: {e}")
    
    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_worker():
    logging.debug("Starting RabbitMQ worker")
    try:
        logging.debug("Connecting to RabbitMQ")
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue='task_queue', durable=True)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='task_queue', on_message_callback=callback)

        logging.info(' [*] Waiting for messages. To exit press CTRL+C')
        channel.start_consuming()
    except Exception as e:
        logging.error(f"Failed to connect to RabbitMQ: {e}")

if __name__ == "__main__":
    # Start the scheduler in a separate daemon thread
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()

    # Start the worker in a separate thread
    worker_thread = threading.Thread(target=start_worker)
    worker_thread.daemon = True
    worker_thread.start()

    # Run the Flask app
    try:
        app.run(debug=True, host='0.0.0.0')
    except Exception as e:
        logging.error(f"Flask app error: {e}")
