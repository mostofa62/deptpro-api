import os
from flask import Flask,request,jsonify
from flask_cors import CORS, cross_origin

#from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from dbpg import DATABASE_URL,db  # Import SQLAlchemy Base and engine from dbpg.py
from models import *

app = Flask(__name__)
CORS(app)


# Configure your app settings (e.g., database URI)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

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
