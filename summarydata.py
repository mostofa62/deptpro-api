import os
from flask import Flask,request,jsonify, json
from dateutil.relativedelta import relativedelta
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
bill_account = my_col('bill_accounts')
income_ac = my_col('income')
debt_types = my_col('debt_type')
saving_category = my_col('category_types')

app_data = my_col('app_data')

@app.route('/api/header-summary-data/<string:user_id>', methods=['GET'])
def header_summary_data(user_id:str):

    app_datas = app_data.find_one({
        'user_id':ObjectId(user_id)
    })


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

                #"total_balance": {"$sum": "$balance"},
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
      

    total_monthly_net_income = app_datas['total_monthly_net_income'] if  app_datas!=None and 'total_monthly_net_income' in app_datas else 0

    
    


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

    financial_frdom_date = convertDateTostring(datetime.now()+relativedelta(years=1),"%b %Y")

    financial_frdom_target = 100000000

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
        "total_monthly_bill_expese":monthly_bill_totals,
        "financial_frdom_date":  financial_frdom_date,
        "financial_frdom_target":financial_frdom_target           
    })



@app.route('/api/dashboard-data/<string:user_id>', methods=['GET'])
def get_dashboard_data(user_id:str):

    app_datas = app_data.find_one({
        'user_id':ObjectId(user_id)
    })

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

    if len(debt_list) > 0:    
        data_json = MongoJSONEncoder().encode(debt_list)
        debt_list = json.loads(data_json)

    saving_list = []

    cursor = saving.find(query,{"user_id":0}).sort(sort_params).limit(page_size)

    for todo in cursor:

        entry = {
            '_id':str(todo['_id']),
            'title':todo['saver'],
            'progress':todo['progress'],
            'amount':todo['total_balance']
        }
        saving_list.append(entry)

    if len(saving_list) > 0:    
        data_json = MongoJSONEncoder().encode(saving_list)
        saving_list = json.loads(data_json)
        


    #summary data debt 

    # Aggregate query to sum the balance field
    pipeline = [
        {"$match": {"user_id": ObjectId(user_id),'deleted_at':None}},  # Filter by user_id
      
        {
            "$group": {
                "_id": None, 
                "debt_total_balance": {"$sum": "$balance"},

            }
        
        } 
    ]

    # Execute the aggregation pipeline
    debt_result = list(debt_accounts.aggregate(pipeline))
    debt_total_balance = debt_result[0]['debt_total_balance'] if debt_result else 0


    pipeline = [
        {"$match": {"user_id": ObjectId(user_id),'deleted_at':None}},  # Filter by user_id
       
        {
            "$group": {
                "_id": None, 
                "bill_paid_total": {"$sum": "$paid_total"},

            }
        
        }  
    ]

    # Execute the aggregation pipeline
    bill_result = list(bill_account.aggregate(pipeline))
    bill_paid_total = bill_result[0]['bill_paid_total'] if bill_result else 0


    # Aggregate query to sum the balance field
    '''
    pipeline = [
        {"$match": {"user_id": ObjectId(user_id),'deleted_at':None}},  # Filter by user_id
       

        {
            "$group": {
                "_id": None, 
                "total_net_income": {"$sum": "$total_net_income"},

            }
        
        } 
    ]

    # Execute the aggregation pipeline
    income_result = list(income_ac.aggregate(pipeline))
    total_net_income = income_result[0]['total_net_income'] if income_result else 0
    '''

    total_net_income = app_datas['total_monthly_net_income'] if app_datas != None and 'total_monthly_net_income' in app_datas else 0

    
    total_saving = app_datas['total_monthly_saving'] if app_datas != None and 'total_monthly_saving' in app_datas else 0

    total_wealth = round((total_net_income + total_saving) - (debt_total_balance + bill_paid_total),2)


    ##debt to wealth actual calculation
    remaining_income = total_net_income - ( debt_total_balance + bill_paid_total + total_saving )
    saving_ratio = (total_saving / total_net_income ) * 100
    remaining_income_ratio = ( remaining_income / total_net_income ) * 100

    ##end debt to wealth actual collectin

    debt_to_wealth = round(( saving_ratio * 0.5) + ( remaining_income_ratio * 0.5 ),0)
    


    debttype_id_list = []
    #credit utilization
    debt_type_cursor = debt_types.find(
        {"deleted_at": None,"in_calculation":1},
        {'_id': 1, 'name': 1, 'parent': 1}
    )

    # Create a list of _id values
    debttype_id_list = [item['_id'] for item in debt_type_cursor]

    # Aggregate query to sum the balance field
    pipeline = [
        {
            "$match": {
                "user_id": ObjectId(user_id),
                'deleted_at':None,
                'debt_type.value':{'$in':debttype_id_list}
            }
        },  

        {
            "$group": {
                "_id": None, 
                "credit_total_balance": {"$sum": "$balance"},
                "credit_total_limit": {"$sum": "$credit_limit"},

            }
        
        }  # Sum the balance
    ]

    # Execute the aggregation pipeline
    debt_result_credit = list(debt_accounts.aggregate(pipeline))
    credit_total_balance = debt_result_credit[0]['credit_total_balance'] if debt_result_credit else 0
    credit_total_limit = debt_result_credit[0]['credit_total_limit'] if debt_result_credit else 0
    credit_ratio = 0
    if credit_total_balance > 0 and credit_total_limit > 0:
        credit_ratio = round((credit_total_balance * 100) / credit_total_limit,2)


    #total allocation calculation
    total_emergency_saving = 0 
    emergency_saving = saving_category.find_one({
        'in_dashboard_cal':1
    },{'_id':1})

    if emergency_saving!=None:

        pipeline = [
        {
            "$match": {
                "user_id": ObjectId(user_id),
                'deleted_at':None,
                "category.value":emergency_saving['_id']
        }},  # Filter by user_id
       

        {
            "$group": {
                "_id": None,
                "total_saving": {"$sum": "$total_balance"},

            }
        
        }
    ]

    # Execute the aggregation pipeline
    saving_result = list(saving.aggregate(pipeline))
    total_emergency_saving = saving_result[0]['total_saving'] if saving_result else 0
        

    total_allocation_data = [
            ["Modules", "Data"],

    ]     

    total_allocation = total_net_income + total_saving + debt_total_balance + bill_paid_total + total_emergency_saving
    if total_allocation > 0:
        total_allocation_data = [
            ["Modules", "Data"],
            ['Bills',round(bill_paid_total * 100 / total_allocation,0) ],
            ['Debts',round(debt_total_balance * 100 / total_allocation,0) ],
            ['Total Net Income',round(total_net_income * 100 / total_allocation,0) ],
            ['Total Savings',round(total_saving * 100 / total_allocation,0) ],
            ['Emergency Saving', round(total_emergency_saving * 100 / total_allocation,0)]
        ]


    return jsonify({

        "debt_list":debt_list,
        'debt_total_balance':debt_total_balance,
        'total_net_income':total_net_income ,
        'bill_paid_total':bill_paid_total ,           
        "debt_list":debt_list,
        "saving_list":saving_list,
        'total_wealth':total_wealth,
        'debt_to_wealth':debt_to_wealth,
        'credit_ratio':credit_ratio,
        'total_saving':total_saving,
        'total_allocation_data':total_allocation_data             
    })
