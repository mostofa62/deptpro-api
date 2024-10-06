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
        {'label':'Weekly','value':7},
        {'label':'BiWeekly','value':14},
        {'label':'Monthly','value':30},
        {'label': 'Quarterly', 'value': 90},
        {'label':'Annually','value':365}           
]


SavingInterestType = [
    {'label':'Simple','value':1},
    {'label':'Compound','value':2}
]

SavingStrategyType = [
    {'label':'Fixed Contribution','value':1},
    {'label':'Savings Challenge','value':2},
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
            'repeat_frequency':RepeatFrequency,
           
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


    saving_boost_types = my_col('saving_boost_types').find(
        {

            "deleted_at":None,
            "user_id": {"$in": [None, ObjectId(user_id)]}
        },
        {'_id': 1, 'name': 1, 'user_id': 1}
        )
    saving_boost_types_list = []
    for todo in saving_boost_types:               
        saving_boost_types_list.append({'value':str(todo['_id']),'label':todo['name']})



    
    
    


    return jsonify({
        "payLoads":{
            'category':category_types_list,
            "saving_boost_source":saving_boost_types_list,            
            'repeat_frequency':RepeatFrequency,
            'saving_interest_type':SavingInterestType,
            'saving_strategy_type':SavingStrategyType
        }
    })