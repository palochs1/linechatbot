from flask import Blueprint, Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        from . import models
        db.create_all()  # Create tables in the database
        models.create_table()

    Migrate(app, db)

    from .api import bp as api_bp
    app.register_blueprint(api_bp)

    return app
