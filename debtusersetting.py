import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from app import app
from db import my_col,myclient,mydb
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal

client = myclient
debt_accounts = my_col('debt_accounts')
usersetting = my_col('user_settings')




#save debt user settings 
@app.route("/api/get-user-settings/<user_id>", methods=['GET'])
def get_user_settings(user_id:str):

    user_setting = usersetting.find_one({'user_id':ObjectId(user_id)},{'_id':0,'user_id':0})

    pipeline = [
            {
                "$match": {
                    "user_id": ObjectId(user_id),
                    'deleted_at':None
                }
            },  # Filter by user_id
        
            {
                "$group": {
                    "_id": None, 
                    "monthly_payment": {"$sum": "$monthly_payment"},

                }
            
            } 
        ]

    # Execute the aggregation pipeline
    debt_result = list(debt_accounts.aggregate(pipeline))
    total_monthly_payment = debt_result[0]['monthly_payment'] if debt_result else 0

    user_setting['minimum_payments'] = total_monthly_payment

    return jsonify({
           
            "user_setting":user_setting            
        })


@app.route("/api/save-user-settings", methods=['POST'])
def save_user_settings():
    if request.method == 'POST':
        data = json.loads(request.data)        
        user_setting_id = None

        user_id = data['user_id']
        message = ''
        result = 0

        try:

            filter_query = {
                "user_id" :ObjectId(user_id)
            }

            update_document = {'$set': {
                #'minimum_payments': float(data['minimum_payments']),
                'monthly_budget': float(data['monthly_budget']), 
                'debt_payoff_method': data['debt_payoff_method']}} 

            user_settings = usersetting.update_one(filter_query, update_document, upsert=True)
            if user_settings.upserted_id:
                
                user_setting_id = str(user_settings.upserted_id)
                message = 'Settings saved!'
                result = 1
            else:
                user_setting_id = user_settings.upserted_id
                message = 'Settings updated!'
                result = 1

           
            
                
        
        except Exception as ex:
            print('DEBT EXP: ',ex)
            user_setting_id = None
            result = 0
            message = 'Debt transaction addition Failed!'

        

            


        return jsonify({
           
            "user_setting_id":user_setting_id,
            "message":message,
            "result":result
        })