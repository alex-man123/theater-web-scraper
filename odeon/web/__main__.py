import os

from odeon.web import create_app

if __name__ == "__main__":
    create_app().run(host=os.getenv("WEB_HOST", "127.0.0.1"), port=int(os.getenv("WEB_PORT", "5000")),
                     debug=os.getenv("FLASK_DEBUG") == "1")
