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
saving = my_col('saving')
bill_transactions = my_col('bill_transactions')

app_data = my_col('app_data')

@app.route('/api/header-summary-data/<string:user_id>', methods=['GET'])
def header_summary_data(user_id:str):


    # Get the current date
    current_date = datetime.now()

    
    # Aggregate query to sum the balance field
    pipeline = [
        {"$match": {"user_id": ObjectId(user_id),'deleted_at':None}},  # Filter by user_id
        # {
        #     '$addFields': {
        #         'total_monthly_minimum': {'$add': ['$monthly_payment', '$minimum_payment']}
        #     }
        # },

        {
            "$group": {
                "_id": None, 
                "total_balance": {"$sum": "$balance"},
                # "total_monthly_minimum": {"$sum": "$total_monthly_minimum"},
                "total_monthly_minimum": {"$sum": "$monthly_payment"},

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
    app_datas = app_data.find_one({'user_id':ObjectId(user_id)})    

    total_monthly_net_income = app_datas['total_current_net_income'] if  app_datas!=None and 'total_current_net_income' in app_datas else 0

    total_monthly_boost_income = app_datas['total_current_boost_income'] if  app_datas!=None and 'total_current_boost_income' in app_datas else 0

    total_monthly_net_income += total_monthly_boost_income


    # Aggregation pipeline
    pipeline = [
        {
            '$match': {
                'deleted_at': None,
                'closed_at': None
            }
        },
        {
            '$group': {
                '_id': None,
                'total_progress': { '$sum': '$progress' },
                'total_count': { '$sum': 1 }
            }
        },
        {
            '$project': {
                '_id': 0,
                'average_progress': { 
                    '$cond': { 
                        'if': { '$ne': [ '$total_count', 0 ] },
                        'then': { '$divide': [ '$total_progress', '$total_count' ] },
                        'else': 0
                    }
                }
            }
        }
    ]

    # Execute the aggregation pipeline
    saving_average = list(saving.aggregate(pipeline))

    saving_average_progress = saving_average[0]['average_progress'] if saving_average else 0

    # Extract the year and month
    target_year = current_date.year
    target_month = current_date.month


    # Extract the target year and month
    target_year = current_date.year
    target_month = current_date.month

    # Aggregation pipeline to sum the 'amount' field for the given month and year
    pipeline = [
        {
            '$match': {
                '$expr': {
                    '$and': [
                        { '$eq': [{ '$year': '$due_date' }, target_year] },
                        { '$eq': [{ '$month': '$due_date' }, target_month] }
                    ]
                }
            }
        },
        {
            '$group': {
                '_id': None,
                'total_amount': { '$sum': '$amount' }
            }
        }
    ]

    # Execute the aggregation
    result = list(bill_transactions.aggregate(pipeline))

    monthly_bill_totals = result[0]['total_amount'] if result else 0



    return jsonify({
        "saving_progress":saving_average_progress,
        "debt_total_balance":total_balance,
        'monthly_budget':monthly_budget,
        'total_monthly_minimum':total_monthly_minimum,
        'snowball_amount':snowball_amount,
        'total_paid_off':total_paid_off,
        'active_debt_account':active_debt_account,
        "month_debt_free":latest_month_debt_free,
        "total_monthly_net_income":total_monthly_net_income,
        "total_monthly_bill_expese":monthly_bill_totals             
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
