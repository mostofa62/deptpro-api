from bson import ObjectId
from flask import json, jsonify, request
from util import MongoJSONEncoder, convertDateTostring
from app import app
from db import my_col
from datetime import datetime

from models import CalendarData
from dbpg import db

@app.route('/api/calender-datapg/<int:userid>/<string:month>', methods=['GET'])
@app.route('/api/calender-datapg/<int:userid>', methods=['GET'])
def calender_data_list_pg(userid: int, month: str = None):
    

    # Set the current month if not provided
    if month is None:
        month = convertDateTostring(datetime.now(), '%Y-%m')

    # Query for calendar data by user_id and month
    results = db.session.query(CalendarData).filter(
        CalendarData.user_id == userid,
        CalendarData.month == month
    ).all()

    # Serialize the results into JSON format
    data_list = [data.to_dict() for data in results]  # Assuming `to_dict` is a method in your model for conversion
    
    return jsonify({
        'rows': data_list
    })