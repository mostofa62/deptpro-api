
import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from payoffutil import calculate_amortization, sort_debts_payoff
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




def distribute_amount(amount, debt_accounts):
    remaining_amount = amount

    while remaining_amount > 0:
        for account in debt_accounts:
            if remaining_amount == 0:
                break

            # Get the initial monthly payment of the account
            initial_payment = account["monthly_payment"]

            # Allocate up to the initial payment or the remaining amount
            allocation = min(initial_payment, remaining_amount)
            account["monthly_payment"] += allocation
            remaining_amount -= allocation

    return debt_accounts


debt_types_collection = my_col('debt_type')
payment_boost = my_col('payment_boost')
@app.route("/api/get-payoff-strategy-account/<user_id>", methods=['GET'])
def get_payoff_strategy_account(user_id:str):


    debt_payoff_method = 0
    

    payoff_strategy = payoffstrategy.find_one({'user_id':ObjectId(user_id)},{'_id':0,'user_id':0})
    if payoff_strategy == None:
        user_setting = usersetting.find_one({'user_id':ObjectId(user_id)},{'_id':0,'user_id':0})
        if user_setting!=None:
            #payoff_strategy = {'debt_payoff_method':user_setting['debt_payoff_method'],'selected_month':{"value":1  ,"label":"Use Current Month"}, 'monthly_budget':user_setting['monthly_budget']}
            payoff_strategy = {'debt_payoff_method':user_setting['debt_payoff_method'], 'monthly_budget':user_setting['monthly_budget']}
            debt_payoff_method = payoff_strategy['debt_payoff_method']['value']
            

    else:
        debt_payoff_method = payoff_strategy['debt_payoff_method']['value']
        


    # Fetch the debt type cursor
    debt_type_cursor = debt_types_collection.find(
        {"deleted_at": None},
        {'_id': 1, 'name': 1, 'parent': 1}
    )

    
    # Create a list of _id values
    debt_type_names = {}
    #debttype_id_list = []
    for d in debt_type_cursor:
        debt_type_names[str(d['_id'])] = d['name']
        #debttype_id_list.append(d['_id'])
    

   

    

    deb_query = {        
        "user_id":ObjectId(user_id),        
        "deleted_at":None,
        "closed_at":None
    }

    sort_params = []

    if debt_payoff_method == 3:
        sort_params.append(('custom_payoff_order',1)) 

    filter_column = {
        '_id': 1,
        'debt_type':1, 
        'name': 1, 
        'balance':1,
        'interest_rate':1,
        'monthly_interest':1,
        'monthly_payment':1,
        'credit_limit':1,
        'month_debt_free':1,
        'months_to_payoff':1,
        'total_interest_sum':1,
        'total_payment_sum':1,
    }

    debt_accounts_data = None

    if sort_params:
        debt_accounts_data = debt_accounts.find(deb_query,filter_column).sort(sort_params)
    else:    
        debt_accounts_data = debt_accounts.find(deb_query,filter_column)

    debt_accounts_list = list(debt_accounts_data)
   
    
    
    if debt_payoff_method < 3 or debt_payoff_method > 3:
        debt_accounts_list = sort_debts_payoff(debt_accounts_list, debt_payoff_method)

    
    data_json = MongoJSONEncoder().encode(debt_accounts_list)
    debt_accounts_list = json.loads(data_json)

    

    
    
    
    initail_date = datetime.now()
    start_date = convertDateTostring(initail_date,'%b %Y')
    paid_off = None
    max_months_to_payoff = 0
    total_paid_amount = 0
    total_interest_amount = 0
    

    # Initialize a dictionary to store the final result
    data = {}
    #debt_type_balances = {}
    debt_account_balances = {}

    debt_names = {}
    debt_id_types = {}
    debt_id_list = []

    debt_accounts_clist = []

    debt_totals = {}

    total_monthly_payment = round(sum(account["monthly_payment"] for account in debt_accounts_list),2)

    debt_accounts_list = distribute_amount(payoff_strategy['monthly_budget'], debt_accounts_list)

    for index,account in enumerate(debt_accounts_list):
        debt_id = str(account['_id'])
        debt_names[str(index+1)+debt_id] =account['name']
        debt_id_types[debt_id] = account['debt_type']['value']
        debt_id_list.append(debt_id)
        #debt_type_id = str(account['debt_type']['value'])  # Get the debt type ID
        
        account_balance = float(account['balance']+account['monthly_interest'])

        debt_account_balances[debt_id]= {
            'balance':account_balance,
            # 'total_payment':0, 
            # 'snowball_amount':0,
            # 'interest':0
        }

        debt_totals[debt_id] = {
            "total_payment": 0,
            "total_interest": 0,
            "month_debt_free": None,
            "months_to_payoff": None  # Initialize as None
        }

        # if debt_id in debt_account_balances:
        #     debt_account_balances[debt_id]['balance'] +=account_balance
        #     debt_account_balances[debt_id]['total_payment'] +=account['total_payment_sum']
        #     debt_account_balances[debt_id]['interest'] +=account['total_interest_sum']
        #     debt_account_balances[debt_id]['snowball_amount'] +=payoff_strategy['monthly_budget']
        # else:
        #     debt_account_balances[debt_id]['balance'] = account_balance
        #     debt_account_balances[debt_id]['total_payment'] =account['total_payment_sum']
        #     debt_account_balances[debt_id]['interest'] =account['total_interest_sum']
        #     debt_account_balances[debt_id]['snowball_amount'] =payoff_strategy['monthly_budget']

        
        

        # Accumulate balance for the same debt type
        
        monthly_data = []

        try:
            monthly_data = calculate_amortization(account['balance'], account['interest_rate'],account['monthly_payment'], account['credit_limit'], initail_date,payoff_strategy['monthly_budget']) 
        except Exception as ex:
            print('Exception handling',ex)
        
        #print(debt_id,'monthly_data',monthly_data)

        if len(monthly_data) > 0:  # If there's data, add it to the correct month
            for record in monthly_data:
                month = record.get('month')
                amount = record.get('balance', 0)
                total_payment = record.get('total_payment', 0)
                snowball_amount = record.get('snowball_amount', 0)
                interest = record.get('interest', 0)
                #print('month',month)

                pipeline_boost = [
                    # Step 1: Match documents with debt_type.value in debttype_id_list
                    {
                        "$match": {
                            "month": month,
                            "deleted_at": None
                        }
                    },
                    {
                        "$group": {
                            "_id": "$month",  # Group by the formatted month-year
                            "total_amount": {"$sum": "$amount"},                        
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,                           # Remove the _id field
                            #"total_count": 1,                   # Include the total count
                            #"total_balance_net": 1,
                            #"total_balance_gross":1,                 # Include the total balance
                            "total_amount": 1                # Include the grouped results
                        }
                    }
                ]
                

                payment_boost_data = list(payment_boost.aggregate(pipeline_boost))

                total_month_wise_boost = payment_boost_data[0]['total_amount'] if payment_boost_data else 0

                #print('total_month_wise_boost',total_month_wise_boost)

                # Initialize the month entry if not already present
                if month not in data:
                    data[month] = {'month': month, 'boost':total_month_wise_boost}

                # Sum amounts for the same month and debt type
                data[month][debt_id] = {
                    'balance':0,
                    'total_payment':0, 
                    'snowball_amount':0,
                    'interest':0
                }
                if debt_id in data[month]:
                    data[month][debt_id]['balance'] +=amount
                    data[month][debt_id]['total_payment'] +=total_payment
                    data[month][debt_id]['snowball_amount'] +=snowball_amount
                    data[month][debt_id]['interest'] +=interest
                else:
                    data[month][debt_id]['balance'] = amount
                    data[month][debt_id]['total_payment'] =total_payment
                    data[month][debt_id]['snowball_amount'] =snowball_amount
                    data[month][debt_id]['interest'] =interest

                

    # Merge data by month and debt type
    # Prepare data for Recharts - merge months across all debt types
    merged_data = {}

    if len(data) > 0:

        # Find all unique months
        all_months = set(data.keys())
        all_months.add(start_date)

        # Sort all months by date
        def parse_month(month_str):
            try:
                return datetime.strptime(month_str, '%b %Y')
            except ValueError:
                return datetime.min  # Default to a minimal date if parsing fails

        all_months = sorted(all_months, key=parse_month)
        #print('all months',all_months)

        # Initialize merged_data with all months and set missing values to debt_type_balances
        for month in all_months:
            boost = data[month]['boost']
            merged_data[month] = {'month': month,'boost':boost}
           
            for debt_id in debt_account_balances:  # Iterate over all debt types
                if month == start_date:
                    # Use debt_type_balances for start_date
                    #merged_data[month][debt_id] = debt_account_balances.get(debt_id, 0)
                    merged_data[month][debt_id] = {
                        'balance':data[month][debt_id]['balance'],
                        'interest':data[month][debt_id]['interest'],
                        'total_payment':data[month][debt_id]['total_payment'],
                        'snowball_amount':data[month][debt_id]['snowball_amount']
                    }
                elif parse_month(month) < parse_month(start_date):
                    # For months before start_date, use debt_type_balances
                    #merged_data[month][debt_id] = debt_account_balances.get(debt_id, 0)
                    merged_data[month][debt_id] = {
                        'balance':data[month][debt_id]['balance'],
                        'interest':data[month][debt_id]['interest'],
                        'total_payment':data[month][debt_id]['total_payment'],
                        'snowball_amount':data[month][debt_id]['snowball_amount']
                    }
                else:
                    # For other months, check if data is present
                    if month in data and debt_id in data[month]:
                        merged_data[month][debt_id] = data[month][debt_id]
                    else:
                        # Fill missing month data with last known debt_type_balances
                        #merged_data[month][debt_id] = merged_data[all_months[all_months.index(month)-1]].get(debt_id, debt_account_balances.get(debt_id, 0))
                        merged_data[month][debt_id] = merged_data[all_months[all_months.index(month)-1]].get(debt_id, 0)
        

    # Convert to list of dicts for the frontend
    all_data = list(merged_data.values()) if len(merged_data) > 0 else []

    #print('debt_id_list',debt_id_list)

    chart_data = []

    if len(all_data) > 0:
        chart_data = [
        {
                "month": entry["month"],
                "boost":entry["boost"],
                **{
                    str(debt_id_list.index(key)+1)+key: details["balance"]
                    for key, details in entry.items()
                    if isinstance(details, dict) and "balance" in details
                }
            }
            for entry in all_data
        ]
    #print('all data',all_data)
    
    output = []
    #debt_ids = debt_id_list
    #debt_ids = {key for entry in all_data for key in entry if key not in ["boost", "month"]}
    #ordered_debt_ids = [debt_id for debt_id in debt_id_list if debt_id in debt_ids]
    #print('all_data',all_data)
    seen = set()
    debt_ids = [key for entry in all_data for key in entry if key not in ["boost", "month"] and key not in seen and not seen.add(key)]

    

    # Process each entry
    for month_index, entry in enumerate(all_data, start=1):
        row = [entry["month"]]
        total_snowball = 0
        total_interest = 0
        total_balance = 0
        total_payment = 0
        
        
        # Add balances for each debt ID dynamically
        #print('entry',entry)
        
        
        for debt_id in debt_ids:
            # balance = entry.get(debt_id, {}).get("balance", 0)
            # snowball_amount = entry.get(debt_id, {}).get("snowball_amount", 0)
            # interest = entry.get(debt_id, {}).get("interest", 0)
            # payment = entry.get(debt_id, {}).get("total_payment", 0)

            balance = entry[debt_id]["balance"]
            snowball_amount = entry[debt_id]["snowball_amount"]
            interest = entry[debt_id]["interest"]
            payment = entry[debt_id]["total_payment"]

            
            
            row.append(balance)
            total_snowball += snowball_amount
            total_interest += interest
            total_balance += balance
            total_payment += payment

            total_snowball = round(total_snowball,2)
            total_interest = round(total_interest,2)
            total_balance = round(total_balance,2)
            total_payment = round(total_payment,2)

            

            # Only add to totals if balance is not yet paid off
            if debt_totals[debt_id]["month_debt_free"] is None:
                debt_totals[debt_id]["total_payment"] += payment
                debt_totals[debt_id]["total_interest"] += interest

                # Check if the debt is fully paid off this month
                if balance <= 0:
                    debt_totals[debt_id]["month_debt_free"] = entry["month"]
                    debt_totals[debt_id]["months_to_payoff"] = month_index
            

            
            
             
    
        total_paid_amount += total_payment
        total_interest_amount += total_interest
        
        # Add total snowball amount, boost, and total interest to the row
        row.extend([total_snowball, entry["boost"], total_interest,total_balance,total_payment])
        output.append(row)
        paid_off = entry["month"]
        max_months_to_payoff += 1

    # Add headers for display
    headers = ["month"] + [str(debt_id_list.index(debt_id)+1)+f"{debt_id}" for debt_id in debt_ids] + ["total_snowball", "boost", "total_interest","total_balance","total_payment"]
    headers_below = [""] + [debt_account_balances[debt_id]['balance'] for debt_id in debt_account_balances] + ["", "", "","",""]
    output.insert(0, headers)
    output.insert(1, headers_below)

    total_paid_amount = round(total_paid_amount,2)
    total_interest_amount = round(total_interest_amount,2)
    
    debt_accounts_clist =  [
        {
            "_id": debt_id,
            "name":debt_names[str(debt_id_list.index(debt_id)+1)+debt_id],
            "total_payment_sum": round(totals["total_payment"], 2),
            "total_interest_sum": round(totals["total_interest"], 2),
            
            "months_to_payoff":totals['months_to_payoff'],
            "month_debt_free_word":totals['month_debt_free'],
            "dept_type_word":debt_type_names[debt_id_types[debt_id]]
        }
        for debt_id, totals in debt_totals.items()
    ]

    return jsonify({
            "total_paid":total_paid_amount,
            "total_interest":total_interest_amount,
            "paid_off":paid_off,
            "max_months_to_payoff":max_months_to_payoff,
            "debt_accounts_list":debt_accounts_clist,
            'debt_accounts_clist':debt_accounts_list,
            #"sorted_month_wise":sorted_month_wise,
            'total_monthly_payment':total_monthly_payment,
            "debt_type_ammortization":chart_data,
            #"data":data,
            "debt_type_names":debt_names,
            "all_data":output,
            'all_d':data,
            'all_d1':all_data            
        })

    

