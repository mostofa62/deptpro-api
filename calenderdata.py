from bson import ObjectId
from flask import json, jsonify, request
from util import MongoJSONEncoder, convertDateTostring
from app import app
from db import my_col
from datetime import datetime

calender_data = my_col('calender_data')


@app.route('/api/calender-data/<string:userid>/<string:month>', methods=['GET'])
@app.route('/api/calender-data/<string:userid>', methods=['GET'])
def calender_data_list(userid:str,month:str=None):

    query = {
        'user_id':ObjectId(userid)
    }

    if month == None:
        month = convertDateTostring(datetime.now(),'%Y-%m')
        query['month'] = month
    
    
    c_data =  calender_data.find(query)

    data_list  = list(c_data)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    return jsonify({
        'rows': data_obj        
    })