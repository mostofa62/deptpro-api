import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from app import app
from db import my_col,myclient
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta


@app.route("/api/billtype-dropdown", methods=['GET'])
def bill_type_dropdown():
    cursor = my_col('bill_type').find(
        {"deleted_at":None},
        {'_id':1,'name':1}
        )
    list_cur = []
    for todo in cursor:               
        list_cur.append({'value':str(todo['_id']),'label':todo['name']})
    #list_cur = list(cursor)
    #data_json = MongoJSONEncoder().encode(list_cur)
    #data_obj = json.loads(data_json)
    return jsonify({
        "list":list_cur
    })