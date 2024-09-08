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


RepeatFrequency = [
        {'label':'Daily','value':1},
        {'label':'Weekly','value':2},
        {'label':'BiWeekly','value':3},
        {'label':'Monthly','value':4},
        {'label': 'Quarterly', 'value': 5},
        {'label':'Annual','value':6}           
]

@app.route("/api/incomesourceboost-dropdown/<string:user_id>", methods=['GET'])
def incomesourceboost_dropdown(user_id:str):
    income_source_types = my_col('income_source_types').find(
        {

            "deleted_at":None,
            "user_id": {"$in": [None, ObjectId(user_id)]}
        },
        {'_id': 1, 'name': 1, 'user_id': 1}
        )
    income_source_types_list = []
    for todo in income_source_types:               
        income_source_types_list.append({'value':str(todo['_id']),'label':todo['name']})



    income_boost_types = my_col('income_boost_types').find(
        {

            "deleted_at":None,
            "user_id": {"$in": [None, ObjectId(user_id)]}
        },
        {'_id': 1, 'name': 1, 'user_id': 1}
        )
    income_boost_types_list = []
    for todo in income_boost_types:               
        income_boost_types_list.append({'value':str(todo['_id']),'label':todo['name']})
    
    


    return jsonify({
        "payLoads":{
            'income_source':income_source_types_list,
            "income_boost_source":income_boost_types_list,
            'repeat_frequency':RepeatFrequency
        }
    })


@app.route("/api/savingcategory-dropdown/<string:user_id>", methods=['GET'])
def savingcategory_dropdown(user_id:str):
    category_types = my_col('category_types').find(
        {

            "deleted_at":None,
            "user_id": {"$in": [None, ObjectId(user_id)]}
        },
        {'_id': 1, 'name': 1, 'user_id': 1}
        )
    category_types_list = []
    for todo in category_types:               
        category_types_list.append({'value':str(todo['_id']),'label':todo['name']})



    
    
    


    return jsonify({
        "payLoads":{
            'category':category_types_list,            
            'repeat_frequency':RepeatFrequency
        }
    })