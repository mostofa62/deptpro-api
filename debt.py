import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from app import app
from db import my_col
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta

collection = my_col('debts')


@app.route("/api/save-debts", methods=['POST'])
def member_registration():
    if request.method == 'POST':
        data = json.loads(request.data)
        debt_id = None
        message = ''
        error = 0
        try:
            debt_id = ''   
            error = 0
            message = 'Registration Succefull'
        except Exception as ex:
            debt_id = None
            error = 1
            message = 'Registration Failed'
            