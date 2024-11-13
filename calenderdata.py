from flask import json, jsonify, request
from util import MongoJSONEncoder
from app import app
from db import my_col

calender_data = my_col('calender_data')


@app.route('/api/calender-data/<string:month>', methods=['GET'])
def calender_data_list(month:str):
    c_data =  calender_data.find({
        'month':month
    })

    data_list  = list(c_data)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    return jsonify({
        'rows': data_obj        
    })