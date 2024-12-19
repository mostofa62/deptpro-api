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

BoostOperationType = [

    {'label':'Deposit','value':1},
    {'label':'Withdraw','value':2},
]

@app.route('/api/delete-income-source', methods=['POST'])
def delete_income_source():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']
        key = data['key']
        action = 'Deleted' if key < 2 else 'Closed'
        field = 'deleted_at' if key < 2 else 'closed_at'

        income_source_id = None
        message = None
        error = 0
        deleted_done = 0

        income_count = my_col('income').count_documents({
            'income_source.value':ObjectId(id),
        })
        
        if income_count > 0:

            income_source_id = None                
            message = f'Income source has {income_count} data!'
            error  = 1
            deleted_done = 0


            return jsonify({
                "income_source_id":income_source_id,
                "message":message,
                "error":error,
                "deleted_done":deleted_done
            })

        

        
        
        try:

            

            myquery = { "_id" :ObjectId(id)}

            newvalues = { "$set": {                                     
                field:datetime.now()                
            } }
            income_source_data =  my_col('income_source_types').update_one(myquery, newvalues)
            income_source_id = id if income_source_data.modified_count else None


           


            error = 0 if income_source_data.modified_count  else 1
            deleted_done = 1 if income_source_data.modified_count else 0
            
            

            if deleted_done:
                message = f'Income source {action} Successfully'
                
            else:
                message = f'Income source {action} Failed'
                

        except Exception as ex:
            income_source_id = None
            print('Income source Save Exception: ',ex)
            message = f'Income source {action} Failed'
            error  = 1
            deleted_done = 0           
        
        return jsonify({
            "income_source_id":income_source_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })



@app.route("/api/incomesourceboost-dropdown/<string:user_id>", methods=['GET'])
def incomesourceboost_dropdown(user_id:str):
    income_source_types = my_col('income_source_types').find(
        {

            "deleted_at":None,
            "user_id": {"$in": [None, ObjectId(user_id)]}
        },
        {'_id': 1, 'name': 1, 'user_id': 1,'bysystem':1}
        )
    income_source_types_list = []
    for todo in income_source_types:               
        income_source_types_list.append({'value':str(todo['_id']),'label':todo['name'],'bysystem':todo['bysystem']})



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


    incomes = my_col('income').find(
        {

            "deleted_at":None,
            "user_id": ObjectId(user_id),            
            "closed_at":None,
        },
        {
            '_id': 1, 
            'earner': 1, 
            'user_id': 1, 
            'repeat':1, 
            'next_pay_date':1
        }
        )


    income_list = []
    for todo in incomes:
        #print(todo)
        name  =  todo['earner']              
        income_list.append({
            'value':str(todo['_id']),
            'label':name,
            'repeat_boost':todo['repeat'],            
            'pay_date_boost':convertDateTostring(todo['next_pay_date'],"%Y-%m-%d")
            })
    
    


    return jsonify({
        "payLoads":{
            'income_source':income_source_types_list,
            "income_boost_source":income_boost_types_list,
            'repeat_frequency':RepeatFrequency,
            'income_list':income_list
           
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


    savings = my_col('saving').find(
        {

            "deleted_at":None,
            "user_id": ObjectId(user_id),
            'goal_reached':None,
            "closed_at":None,
        },
        {
            '_id': 1, 
            'saver': 1, 
            'user_id': 1, 
            'repeat':1, 
            'next_contribution_date':1
        }
        )
    saving_list = []
    for todo in savings:
        #print(todo)
        name  =  todo['saver']              
        saving_list.append({
            'value':str(todo['_id']),
            'label':name,
            'repeat_boost':todo['repeat'],            
            'pay_date_boost':convertDateTostring(todo['next_contribution_date'],"%Y-%m-%d")
            })


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
            'saving_strategy_type':SavingStrategyType,
            'saving_list':saving_list,
            'boost_operation_type':BoostOperationType
        }
    })