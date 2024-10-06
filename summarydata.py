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
income_transactions = my_col('income_transactions')
income_boost_transaction = my_col('income_boost_transactions')

@app.route('/api/header-summary-data/<string:user_id>', methods=['GET'])
def header_summary_data(user_id:str):

    
    # Aggregate query to sum the balance field
    pipeline = [
        {"$match": {"user_id": ObjectId(user_id),'deleted_at':None}},  # Filter by user_id
        {
            '$addFields': {
                'total_monthly_minimum': {'$add': ['$monthly_payment', '$minimum_payment']}
            }
        },

        {
            "$group": {
                "_id": None, 
                "total_balance": {"$sum": "$balance"},
                "total_monthly_minimum": {"$sum": "$total_monthly_minimum"},

                "total_balance": {"$sum": "$balance"},
                "total_highest_balance":{"$sum": "$highest_balance"},
                "latest_month_debt_free": {"$max": "$month_debt_free"}

            }
        
        }  # Sum the balance
    ]

    # Execute the aggregation pipeline
    result = list(debt_accounts.aggregate(pipeline))

    # Extract the total balance from the result
    total_balance = result[0]['total_balance'] if result else 0

    total_monthly_minimum = round(result[0]['total_monthly_minimum'],2) if result else 0

    total_balance = result[0]['total_balance'] if result else 0
    total_highest_balance = result[0]['total_highest_balance'] if result else 0
    total_paid_off = calculate_paid_off_percentage(total_highest_balance,total_balance)

    user_setting = usersetting.find_one({'user_id':ObjectId(user_id)},{'debt_payoff_method':1,'monthly_budget':1})

    monthly_budget = 0

    if user_setting:
        monthly_budget = round(user_setting['monthly_budget'],2)
    
    snowball_amount = round(monthly_budget - total_monthly_minimum,2)

    active_debt_account = debt_accounts.count_documents({'user_id':ObjectId(user_id),'deleted_at':None})

    latest_month_debt_free = result[0]['latest_month_debt_free'].strftime('%b %Y') if result and 'latest_month_debt_free' in result[0] and result[0]['latest_month_debt_free']!=None else ''


    #income and incomeboost
    current_monnt = datetime.now().strftime('%Y-%m')

    pipeline = [
        # Step 1: Match documents with pay_date in the last 12 months and not deleted
        {
            "$match": {
                "month": current_monnt,
                "deleted_at": None,
                "closed_at":None
            }
        },
        
        # Step 2: Project to extract year and month from pay_date
        {
            "$project": {
                "base_net_income": 1,
                "base_gross_income": 1,
                #"month_word":1,
                "month":1            
            }
        },

        # Step 3: Group by year_month and sum the balance
        {
            "$group": {
                "_id": "$month",  # Group by the formatted month-year
                "total_balance_net": {"$sum": "$base_net_income"},
                "total_balance_gross": {"$sum": "$base_gross_income"},
                #"month_word": {"$first": "$month_word"},  # Include the year
                "month": {"$first": "$month"}   # Include the month
            }
        },

        # Step 4: Create the formatted year_month_word
        {
            "$project": {
                "_id": 1,
                "total_balance_net": 1,
                "total_balance_gross":1,
                # "month_word":1            
            }
        },


       
    ]

    month_wise_all = list(income_transactions.aggregate(pipeline))

    total_monthly_net_income = month_wise_all[0]['total_balance_net'] if month_wise_all else 0



    return jsonify({
        "debt_total_balance":total_balance,
        'monthly_budget':monthly_budget,
        'total_monthly_minimum':total_monthly_minimum,
        'snowball_amount':snowball_amount,
        'total_paid_off':total_paid_off,
        'active_debt_account':active_debt_account,
        "month_debt_free":latest_month_debt_free,
        "total_monthly_net_income":total_monthly_net_income,
        "total_monthly_bill_expese":2300             
    })



@app.route('/api/dashboard-data/<string:user_id>', methods=['GET'])
def get_dashboard_data(user_id:str):

    page_size = 5
    query = {
        'user_id':ObjectId(user_id),
        'deleted_at':None
    }

    sort_params = [
    ('updated_at',-1)
    ]

    debt_list = []
    
    cursor = debt_accounts.find(query,{"user_id":0}).sort(sort_params).limit(page_size)

    for todo in cursor:
        paid_off_percentage = calculate_paid_off_percentage(todo['highest_balance'], todo['balance'])
        left_to_go = round(float(100) - float(paid_off_percentage),1)
        entry = {
            '_id':str(todo['_id']),
            'title':todo['name'],
            'progress':left_to_go,
            'amount':todo['balance']
        }
        debt_list.append(entry)
        
    data_json = MongoJSONEncoder().encode(debt_list)
    data_obj = json.loads(data_json)
    

    return jsonify({
        "debt_list":data_obj,             
    })
