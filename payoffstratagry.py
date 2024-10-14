
import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from payoffutil import sort_debts_payoff
from app import app
from db import my_col,myclient
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta

payoffstrategy = my_col('payoff_strategy')
usersetting = my_col('user_settings')
debt_accounts = my_col('debt_accounts')
#save debt user settings 
@app.route("/api/get-payoff-strategy/<user_id>", methods=['GET'])
def get_payoff_strategy(user_id:str):

    payoff_strategy = payoffstrategy.find_one({'user_id':ObjectId(user_id)},{'_id':0,'user_id':0})
    if payoff_strategy == None:
        user_setting = usersetting.find_one({'user_id':ObjectId(user_id)},{'_id':0,'user_id':0})
        if user_setting!=None:
            payoff_strategy = {'debt_payoff_method':user_setting['debt_payoff_method'],'selected_month':{"value":1  ,"label":"Use Current Month"}, 'monthly_budget':user_setting['monthly_budget']}

    return jsonify({
           
            "payoff_strategy":payoff_strategy            
        })



@app.route("/api/save-payoff-strategy", methods=['POST'])
def save_payoff_strategy():
    if request.method == 'POST':
        data = json.loads(request.data)        
        payoff_strategy_id = None

        payoff_id = data['user_id']
        message = ''
        result = 0

        try:

            filter_query = {
                "user_id" :ObjectId(payoff_id)
            }

            update_document = {'$set': {'selected_month': data['selected_month'],'monthly_budget': float(data['monthly_budget']), 'debt_payoff_method': data['debt_payoff_method']}} 

            payoff_strategy = payoffstrategy.update_one(filter_query, update_document, upsert=True)
            if payoff_strategy.upserted_id:
                
                payoff_strategy_id = str(payoff_strategy.upserted_id)
                message = 'Settings saved!'
                result = 1
            else:
                payoff_strategy_id = payoff_strategy.upserted_id
                message = 'Settings updated!'
                result = 1

           
            
                
        
        except Exception as ex:
            print('DEBT EXP: ',ex)
            payoff_strategy_id = None
            result = 0
            message = 'Debt transaction addition Failed!'

        

            


        return jsonify({
           
            "payoff_strategy_id":payoff_strategy_id,
            "message":message,
            "result":result
        })






@app.route("/api/get-payoff-strategy-account/<user_id>", methods=['GET'])
def get_payoff_strategy_account(user_id:str):

    debt_payoff_method = 0

    payoff_strategy = payoffstrategy.find_one({'user_id':ObjectId(user_id)},{'_id':0,'user_id':0})
    if payoff_strategy == None:
        user_setting = usersetting.find_one({'user_id':ObjectId(user_id)},{'_id':0,'user_id':0})
        if user_setting!=None:
            payoff_strategy = {'debt_payoff_method':user_setting['debt_payoff_method'],'selected_month':{"value":1  ,"label":"Use Current Month"}, 'monthly_budget':user_setting['monthly_budget']}
            debt_payoff_method = payoff_strategy['debt_payoff_method']['value']

    else:
        debt_payoff_method = payoff_strategy['debt_payoff_method']['value']

    

    deb_query = {
        "user_id":ObjectId(user_id),        
        "deleted_at":None
    }

    debt_accounts_data = debt_accounts.find(deb_query, {'_id': 1, 'name': 1, 'balance':1,'interest_rate':1,'monthly_payment':1,'credit_limit':1})

    debt_accounts_list = list(debt_accounts_data)

    

    debt_accounts_list = sort_debts_payoff(debt_accounts_list, debt_payoff_method)


    data_json = MongoJSONEncoder().encode(debt_accounts_list)
    debt_accounts_list = json.loads(data_json)

    return jsonify({
           
            "debt_accounts_list":debt_accounts_list            
        })

    

