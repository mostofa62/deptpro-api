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
debt_transactions = my_col('debt_transactions')
debt_accounts = my_col('debt_accounts')
usersetting = my_col('user_settings')



@app.route('/api/debtpayoff/<string:user_id>', methods=['POST'])
def debtpayoff(user_id:str):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
   

    # Construct MongoDB filter query
    query = {
        #'role':{'$gte':10}
        "user_id":ObjectId(user_id),
        "deleted_at":None,
        "closed_at":None
    }
    
    

    
    # Construct MongoDB sort parameters
    sort_params = [
        ('custom_payoff_order',1),
        
        
    ]
    

   
    cursor = debt_accounts.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
    

    total_count = debt_accounts.count_documents(query)
    data_list = []
    for todo in cursor:
        debt_type_id = todo['debt_type']['value']
        debt_type = my_col('debt_type').find_one(
        {"_id":debt_type_id},
        {"_id":0,"name":1}
        )

        
        
        entry = {
            "_id":todo["_id"],
            "name":todo["name"],
            "debt_type":debt_type["name"] if debt_type!=None else None,
            "payor":todo["payor"],
            "balance":round(todo["balance"],2),
            "interest_rate":todo["interest_rate"],
            #"minimum_payment":round(todo["minimum_payment"],2),
            "monthly_payment":round(todo["monthly_payment"],2),
            "monthly_interest":round(todo["monthly_interest"],2),
            "due_date":convertDateTostring(todo["due_date"]),
            "custom_payoff_order":todo['custom_payoff_order']
                      
            
        }
        data_list.append(entry)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size


   

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count,
        
        
    })



@app.route('/api/update-payoff-order', methods=['POST'])
def update_payoff_order():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Iterate over the updated rows and update the `custom_payoff_order` field in MongoDB
    for item in data:
        debt_accounts.update_one(
            {"_id": ObjectId(item["_id"])},
            {"$set": {"custom_payoff_order": item["custom_payoff_order"]}}
        )

    return jsonify({'message': 'Custom payoff order updated successfully'}), 200