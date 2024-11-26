import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from billfunctions import calculate_future_bill
from app import app
from db import my_col,myclient
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal
from billextra import extra_type
client = myclient
bill_accounts = my_col('bill_accounts')
bill_transactions = my_col('bill_transactions')
bill_payment = my_col('bill_payment')
bill_type_list = my_col('bill_type')
import calendar

def get_month_key(month_year):
    month, year = month_year.split(', ')
    month_number = list(calendar.month_abbr).index(month)
    return (int(year), month_number)

# Sort all months by date
def parse_month(month_str):
    try:
        return datetime.strptime(month_str, '%b %Y')
    except ValueError:
        return datetime.min  # Default to a minimal date if parsing fails

@app.route("/api/bill-projection/<string:userid>", methods=['GET'])
def bill_projection(userid:None):

    # Fetch the bill type cursor
    bill_type_cursor = bill_type_list.find(
        {"deleted_at": None},
        {'_id': 1, 'name': 1, 'parent': 1}
    )
    
    # Create a list of _id values
    billtype_id_list = [item['_id'] for item in bill_type_cursor]


    # Query to get bill accounts along with bill_type
    sort_params = [('next_due_date', 1)]
    bill_query = {
        "bill_type.value": {"$in": billtype_id_list},
        "deleted_at":None
    }
    bill_type_balances = {}

    if userid!=None:
        bill_query['user_id'] = ObjectId(userid)

    start_date = convertDateTostring(datetime.now(),'%b %Y')

    bill_accounts_data = bill_accounts.find(bill_query, {'_id': 1, 'name': 1, 'bill_type': 1,'default_amount':1,'next_due_date':1,'repeat_frequency':1}).sort(sort_params)


    # Fetch bill type names
    bill_types = bill_type_list.find({'_id': {'$in': billtype_id_list}})    
    bill_type_names = {str(d['_id']): d['name'] for d in bill_types}

    # Initialize a dictionary to store the final result
    data = {}

    #start_date = datetime.now()

    for account in bill_accounts_data:
        account_id = str(account['_id'])  # Convert ObjectId to string
        bill_type_id = str(account['bill_type']['value'])  # Get the bill type ID 
        frequency = account['repeat_frequency']       
        

        account_balance = float(account['default_amount'])
        #print('balance',account_balance)

        # Accumulate balance for the same bill type
        if bill_type_id in bill_type_balances:
            bill_type_balances[bill_type_id] += account_balance
        else:
            bill_type_balances[bill_type_id] = account_balance        
        

        projection_data =  calculate_future_bill(initial_amount=account_balance,start_date=account['next_due_date'],frequency=frequency)
        monthly_data = projection_data['breakdown']

        #print('monthly_data',monthly_data)


        if monthly_data:  # If there's data, add it to the correct month
                for record in monthly_data:
                    month = record.get('month_word')
                    amount = record.get('balance', 0)

                    #print(month, amount)

                    # Initialize the month entry if not already present
                    if month not in data:
                        data[month] = {'month': month}

                    # Sum amounts for the same month and bill type
                    if bill_type_id in data[month]:
                        data[month][bill_type_id] += amount
                    else:
                        data[month][bill_type_id] = amount

    #print('data',data)

    merged_data = {}

    if len(data) > 0:
        merged_data = dict(sorted(data.items(), key=lambda item: get_month_key(item[0])))

        
        

    # Convert to list of dicts for the frontend
    chart_data = list(merged_data.values()) if len(merged_data) > 0 else []


    return jsonify({
        "payLoads":{            
            
            "bill_type_ammortization":chart_data,
            #"bill_type_ammortization":normalized_data,
            "data":data,
            "bill_type_names":bill_type_names
            
        }        
    })