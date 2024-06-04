import os
import redis

r = redis.Redis(host='localhost', port=6379, db=0)
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'mysecret')
    SQLALCHEMY_DATABASE_URI = "sqlite:///demo.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwtsecret')
    SESSION_TYPE = 'redis'  # ตั้งค่า SESSION_TYPE เป็น 'redis'
    SESSION_REDIS = os.getenv('REDIS_URL', 'redis://localhost:6379/0')