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


def calculate_amortization(balance, interest_rate, monthly_payment, credit_limit, current_date, monthly_budget):
    amortization_schedule = []
    
    # Convert interest rate to decimal
    interest_rate_decimal = interest_rate / 100
       
    
    while balance > 0:
        balance = min(balance, credit_limit)
        
        # Calculate interest for the current balance
        interest = balance * interest_rate_decimal / 12
        
        # Calculate the maximum payment we can make considering the monthly budget
        payment = min(monthly_payment, monthly_budget)
        
        # Calculate snowball amount
        snowball_amount = min(payment, balance + interest) - interest
        
        # Calculate principal payment
        principle = snowball_amount
        principle = min(principle, balance)
        balance -= principle
        
        if balance < 0:
            balance = 0
        
        # Calculate total payment (principle + interest)
        total_payment = principle + interest
        
        # Record this month's data
        amortization_schedule.append({
            'month': current_date.strftime("%b %Y"),
            'balance': round(balance, 2),
            'total_payment': round(total_payment, 2),
            'snowball_amount': round(snowball_amount, 2),
            'interest': round(interest, 2),
            'principle': round(principle, 2)
        })
        
        # Move to the next month
        current_date += timedelta(days=30)
    
    return amortization_schedule





# Define sorting method (for example, Debt Snowball - lowest balance first)
def sort_debts(debts, method):
    if method == 1:  # Debt Snowball - lowest balance first
        return sorted(debts, key=lambda x: x['balance'])
    elif method == 2:  # Debt Avalanche - highest interest rate first
        return sorted(debts, key=lambda x: x['interest_rate'], reverse=True)
    elif method == 11:  # Hybrid (Debt Ratio)
        return sorted(debts, key=lambda x: x['balance'] / (x['interest_rate'] + 1))
    elif method == 13:  # Cash Flow Index (CFI)
        return sorted(debts, key=lambda x: x['balance'] / (x['monthly_payment'] + 1))
    elif method == 3:  # Custom - highest sort number first
        return sorted(debts, key=lambda x: x['balance'], reverse=True)
    elif method == 4:  # Custom - lowest sort number first
        return sorted(debts, key=lambda x: x['balance'])
    elif method == 5:  # Highest monthly payment first
        return sorted(debts, key=lambda x: x['monthly_payment'], reverse=True)
    elif method == 8:  # Highest credit utilization first
        return sorted(debts, key=lambda x: x['balance'] / (x['credit_limit'] + 1), reverse=True)
    elif method == 10:  # Highest monthly interest paid first
        return sorted(debts, key=lambda x: x['monthly_interest'], reverse=True)
    elif method == 12:  # Lowest interest rate paid first
        return sorted(debts, key=lambda x: x['interest_rate'])
    else:
        raise ValueError("Unknown debt payoff method")


@app.route('/api/debt-amortization/<string:accntid>', methods=['POST'])
def get_dept_amortization(accntid:str):

    debtaccounts = debt_accounts.find_one(
        {"_id":ObjectId(accntid)},
        {
        "_id":0,                
        }        
        )

    balance = debtaccounts['balance']
    #highest_balance = debtaccounts['highest_balance']
    monthly_payment = debtaccounts['monthly_payment']
    interest_rate = debtaccounts['interest_rate']
    #monthly_interest = debtaccounts['monthly_interest']
    credit_limit = debtaccounts['credit_limit']
    current_date = debtaccounts['due_date']
    #print(interest_rate)

    user_setting = usersetting.find_one({'user_id':debtaccounts['user_id']},{'debt_payoff_method':1,'monthly_budget':1})
    monthly_budget = user_setting['monthly_budget']
    


    debt = {        
        'balance': balance,
        'interest_rate': interest_rate,
        'monthly_payment': monthly_payment,
        'credit_limit': credit_limit,
        'current_date': current_date,
        'monthly_budget': monthly_budget
    }

    schedule = calculate_amortization(
        balance=debt['balance'],
        interest_rate=debt['interest_rate'],
        monthly_payment=debt['monthly_payment'],
        credit_limit=debt['credit_limit'],
        current_date=debt['current_date'],
        monthly_budget=debt['monthly_budget']
    )

    # Add amortization schedule to debt dictionary
    debt['amortization_schedule'] = schedule

    # List of debts (single debt in this case)
    debts = [debt]

    debt_payoff_method = user_setting['debt_payoff_method']['value']
    sorted_debts = sort_debts(debts, debt_payoff_method)

    return jsonify({
        'rows':sorted_debts[0]['amortization_schedule']
    })


@app.route('/api/debt-amortization-dynamically/<string:accntid>', methods=['POST'])
def get_dept_amortization_dynamic(accntid:str):
    collection_name = f"debt_{accntid}"
    if collection_name not in mydb.list_collection_names():
        return jsonify({
            'rows': [],
            'pageCount': 0,
            'totalRows': 0
        })
    
    else:
        collection = my_col(collection_name)
        data = request.get_json()
        page_index = data.get('pageIndex', 0)
        page_size = data.get('pageSize', 10)
        

        query = {
            
        }
        cursor = collection.find(query).skip(page_index * page_size).limit(page_size)

        total_count = collection.count_documents(query)
        data_list = list(cursor)
        data_json = MongoJSONEncoder().encode(data_list)
        data_obj = json.loads(data_json)

        # Calculate total pages
        total_pages = (total_count + page_size - 1) // page_size

        pipeline = [
        {"$match": query},  # Filter by user_id
        {"$group": {"_id": None, 
                    "total_projected_payment": {"$sum": "$total_payment"},
                    "total_snowball_amount":{"$sum": "$snowball_amount"},
                    "total_interest":{"$sum": "$interest"},                    
                    "total_principle":{"$sum": "$principle"}                    
                    }}  # Sum the balance
        ]

        # Execute the aggregation pipeline
        result = list(collection.aggregate(pipeline))

        # Extract the total balance from the result
        total_projected_payment = result[0]['total_projected_payment'] if result else 0
        total_snowball_amount = result[0]['total_snowball_amount'] if result else 0
        total_interest = result[0]['total_interest'] if result else 0
        total_principle = result[0]['total_principle'] if result else 0
        

        return jsonify({
            'rows': data_obj,
            'pageCount': total_pages,
            'totalRows': total_count,
            'extra_payload':{
                'total_payment':total_projected_payment,
                'total_snowball_amount':total_snowball_amount,
                'total_interest':total_interest,
                'total_principle':total_principle
            }
        })
    
