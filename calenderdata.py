from flask import json, jsonify, request
from util import MongoJSONEncoder, convertDateTostring
from app import app
from db import my_col
from datetime import datetime

calender_data = my_col('calender_data')


@app.route('/api/calender-data/<string:month>', methods=['GET'])
@app.route('/api/calender-data', methods=['GET'])
def calender_data_list(month:str=None):

    if month == None:
        month = convertDateTostring(datetime.now(),'%Y-%m')
    c_data =  calender_data.find({
        'month':month
    })

    data_list  = list(c_data)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    return jsonify({
        'rows': data_obj        
    })