# app/models.py
from sqlalchemy import Column, Integer, String, Date
from app import db


class User(db.Model):
    id = Column(Integer, primary_key=True)
    task = Column(String(128), nullable=False)
    date = Column(Date, nullable=False)
    time = Column(String(8), nullable=False)
    customer_id = Column(String(256), nullable=False)
    status = Column(String(10), nullable=True)
    event_id = Column(String(120))
    key = Column(String(256), nullable=False)
    key_send = Column(String(50), nullable=False, default="SEND_MESSAGE_KEY")


    def __repr__(self):
        return f"<User {self.id}>"
  

def create_table():
    db.create_all()