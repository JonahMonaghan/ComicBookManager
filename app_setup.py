from flask import Flask
from flask_session import Session
from app.comic_manager import ComicBookManagerApp 
from app.auth_manager import AuthManager
import app_config

def create_app():
    app = Flask(__name__)
    app.config.from_object(app_config)
    Session(app)
    manager = ComicBookManagerApp(app)
    auth_manager = AuthManager(app)

    auth_manager.register_auth_routes()
    manager.register_routes()

    return app