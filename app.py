import os
from flask import Flask,request,jsonify
from flask_cors import CORS, cross_origin

# from flask_migrate import Migrate
# from flask_sqlalchemy import SQLAlchemy
from dbpg import DATABASE_URL,db  # Import SQLAlchemy Base and engine from dbpg.py
#from models import *

app = Flask(__name__)
CORS(app)


# Configure your app settings (e.g., database URI)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True, 
    "pool_size": 10, 
    "max_overflow": 5,
    "pool_timeout": 30  # Time to wait before raising timeout
}

db.init_app(app)

from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("SELECT 1"))  # Wrap SQL query with `text()`
        print("Database connection successful!")
    except Exception as e:
        print(f"Database connection failed: {e}")


@app.route("/api/health", methods=["GET"])
def health_check():
    try:
        db.session.execute(text("SELECT 1"))
        return {"status": "ok"}, 200
    except Exception:
        return {"status": "db_error"}, 500



@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()


#enable timezone before commit
#TIMEZONE = os.environ.get('TIMEZONE', 'America/New_York')
# Set the desired time zone
#os.environ['TZ'] = TIMEZONE
# Now, datetime.now() should return the time in the New York time zone
#from time import tzset
#tzset()  # Apply the environment time zone change

# Setup Flask-Migrate
#migrate = Migrate(app, db)
#from models import *
'''
cors = CORS(app, resource={
    r"/*":{
        "origins":"*"
    }
})
'''


#if __name__ == '__main__':
#   app.run(debug = True)
