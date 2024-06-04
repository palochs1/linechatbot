import json
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from .models import User
from . import db
from .utils import add_event_to_google_calendar, delete_event_from_google_calendar, all_task_count, get_task_counts_from_db, task_count_success, format_room_flex, botnoipayload, get_task_counts
from .encryption import encrypt_data, decrypt_data
from cryptography.fernet import Fernet
import pandas as pd
import logging

bp = Blueprint('/api', __name__)

logging.basicConfig(level=logging.DEBUG)

@bp.route('/', methods=['POST'])
def create_task():
    try:
        task = request.args.get('task')
        date_str = request.args.get('date')
        time_str = request.args.get('time')
        status = request.args.get('status', 'notyet')
        data = request.data
        data2 = json.loads(data)
        
        if not task or not date_str or not time_str or not data:
            return jsonify({"msg": "ข้อมูลไม่ครบถ้วน"}), 400
        
        customer_id = data2['customer_id']

        logging.debug(f"Received task: {task}, date: {date_str}, time: {time_str}, customer_id: {customer_id}")

        date_obj = datetime.strptime(date_str, "%d/%m/%y").date()
        time_obj = datetime.strptime(time_str, "%H:%M").time()

        time_str = time_obj.strftime("%H:%M")

        key = Fernet.generate_key().decode()

        event_id = add_event_to_google_calendar(task, date_obj, time_obj)
        encrypted_event_id = encrypt_data(event_id, key)

        existing_task = User.query.filter_by(event_id=encrypted_event_id).all()
        for task in existing_task:
            decrypted_event_id = decrypt_data(task.event_id, task.key)
            if decrypted_event_id == event_id:
                return jsonify({"message": "ช่วงเวลานี้คุณมีงานอยู่แล้ว"}), 201

        user = User(task=task, date=date_obj, time=time_str, customer_id=customer_id, event_id=encrypted_event_id, status=status, key=key)
        db.session.add(user)
        db.session.commit()

        event_id = add_event_to_google_calendar(task, date_obj, time_obj)

        user.event_id = event_id
        db.session.commit()

        all_task_count(date_obj, status, customer_id)

        return jsonify({"message": "บันทึกตารางงานเรียบร้อย"}), 200 
    except ValueError as e:
        logging.error(f"รูปแบบวันที่หรือเวลาไม่ถูกต้อง: {e}")
        return jsonify({"msg": f"รูปแบบวันที่หรือเวลาไม่ถูกต้อง: {e}"}), 400
    except Exception as e:
        logging.error(f"เกิดข้อผิดพลาดในการบันทึกข้อมูล: {e}")
        db.session.rollback()
        return jsonify({"msg": f"เกิดข้อผิดพลาดในการบันทึกข้อมูล: {e}"}), 500


@bp.route('/show', methods=['GET'])
def get_all_tasks():
    customer_id = request.args.get('customer_id')
    period = request.args.get('period', 'daily')

    if not customer_id:
        return jsonify({'error': 'Customer ID not specified'}), 400

    tasks = User.query.all()

    today = datetime.today().date()

    if period == 'daily':
        start_date = today
        end_date = today
    elif period == 'weekly':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == 'monthly':
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(month=12, day=31)
        else:
            next_month_start = today.replace(month=today.month + 1, day=1)
            end_date = next_month_start - timedelta(days=1)
    else:
        return jsonify({'error': 'Invalid period specified'}), 400

    filtered_tasks = []
    for task in tasks:
        if start_date <= task.date <= end_date and task.status == 'notyet' and task.customer_id == customer_id:
            filtered_tasks.append(task)

    def generate():
        df = pd.DataFrame([{
            'task': task.task,
            'date': task.date,
            'time': task.time,
            'status': task.status
        } for task in filtered_tasks])

        df['date'] = pd.to_datetime(df['date'], format='%d/%m/%y').dt.date
        df['time'] = pd.to_datetime(df['time'], format='%H:%M').dt.time
        df_sorted = df.sort_values(by=['date', 'time'])

        for _, row in df_sorted.iterrows():
            yield {
                'task': row['task'],
                'date': row['date'].strftime("%d/%m/%Y"),
                'time': row['time'].strftime("%H:%M"),
                'status': row['status'],
            }

    flex_message = format_room_flex(generate())
    line_payload = botnoipayload(flex_message)

    return jsonify(line_payload)

@bp.route('/delete', methods=['POST'])
def delete_task():
    try:
        task = request.args.get('task')
        customer_id = request.args.get('customer_id')

        if not task or not customer_id:
            return jsonify({"msg": "ข้อมูลไม่ครบถ้วน"}), 400

        user_tasks = User.query.filter_by(task=task).all()
        user_task = None
        for task in user_tasks:
            if task.customer_id == customer_id:
                user_task = task
                break

        if not user_task:
            return jsonify({"msg": "ไม่พบตารางงานที่ระบุ"}), 404

        event_id = user_task.event_id

        db.session.delete(user_task)
        db.session.commit()

        delete_event_from_google_calendar(event_id)
        task_count_success(user_task.date, user_task.status, user_task.customer_id)

        return jsonify({"msg": "ลบตารางงานเรียบร้อย"}), 200
    except Exception as e:
        logging.error(f"เกิดข้อผิดพลาดในการลบข้อมูล: {e}")
        db.session.rollback()
        return jsonify({"msg": f"เกิดข้อผิดพลาดในการลบข้อมูล: {e}"}), 500

@bp.route('/update_status', methods=['POST'])
def update_status():
    try:
        task_name = request.args.get('task')
        new_status = request.args.get('status' , 'success')
        customer_id = request.args.get('customer_id')
        
        if not task_name or not new_status or not customer_id:
            return jsonify({"msg": "ข้อมูลไม่ครบถ้วน"}), 400

        logging.debug(f"Updating status for task: {task_name}")

        user_tasks = User.query.filter_by(task=task_name, status='notyet').all()
        task_to_update = None
        for task in user_tasks:
            if customer_id == customer_id:
                task_to_update = task
                break

        if not task_to_update:
            return jsonify({"msg": "ไม่พบงานที่ต้องการอัปเดตหรือสถานะไม่ใช่ notyet"}), 404

        old_status = task_to_update.status
        task_to_update.status = 'success'
        db.session.commit()

        task_count_success(task_to_update.date, old_status, customer_id)
        all_task_count(task_to_update.date, new_status, customer_id)

        return jsonify({"message": "อัปเดตสถานะเป็น success เรียบร้อย"}), 200
    except Exception as e:
        logging.error(f"เกิดข้อผิดพลาดในการอัปเดตสถานะงาน: {e}")
        db.session.rollback()
        return jsonify({"msg": f"เกิดข้อผิดพลาดในการอัปเดตสถานะ: {e}"}), 500

@bp.route('/task_counts', methods=['GET'])
def task_counts():
    period = request.args.get('period', 'daily')
    customer_id = request.args.get('customer_id')
    
    if not customer_id:
        return jsonify({'error': 'Customer ID not specified'}), 400

    today = datetime.today().date()

    if period == 'daily':
        date = today
    else:
        return jsonify({'error': 'Invalid period specified'}), 400

    try:
        counts = get_task_counts(date, customer_id)
        return jsonify(counts), 200
    except ValueError as e:
        logging.error(f"Invalid date format: {e}")
        return jsonify({'error': 'Invalid date format'}), 400
    
@bp.route('/task_counts_db', methods=['GET'])
def task_counts_db():
    period = request.args.get('period', 'weekly')
    customer_id = request.args.get('customer_id')
    
    if not customer_id:
        return jsonify({'error': 'Customer ID not specified'}), 400

    today = datetime.today().date()

    if period == 'weekly':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == 'monthly':
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(month=12, day=31)
        else:
            next_month_start = today.replace(month=today.month + 1, day=1)
            end_date = next_month_start - timedelta(days=1)
    else:
        return jsonify({'error': 'Invalid period specified'}), 400

    try:
        counts = get_task_counts_from_db(start_date, end_date, customer_id)  
        return jsonify(counts), 200
    except Exception as e:
        logging.error(f"Error getting task counts: {e}")
        return jsonify({'error': 'Error getting task counts'}), 500

