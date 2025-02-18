
import os
from flask import Flask,request,jsonify, json
from sqlalchemy import func
#from flask_cors import CORS, cross_origin
from payoffutil import calculate_amortization, sort_debts_payoff
from app import app
import re
from util import *
from datetime import datetime

from models import DebtAccounts, UserSettings, PayoffStrategy, PaymentBoost, DebtType
from dbpg import db


@app.route("/api/get-payoff-strategypg/<int:user_id>", methods=['GET'])
def get_payoff_strategy_pg(user_id: int):
    # Attempt to find the payoff strategy for the given user_id
    payoff_strategy = PayoffStrategy.query.filter_by(user_id=user_id).first()

    payoff_strategy_data= {}

    if payoff_strategy is None:
        # If no payoff strategy found, look for user settings as a fallback
        user_setting = UserSettings.query.filter_by(user_id=user_id).first()
        
        if user_setting:
            # If user settings exist, create a fallback payoff strategy response
            payoff_strategy_data = {
                'debt_payoff_method': user_setting.debt_payoff_method,
                'selected_month': {"value": 1, "label": "Use Current Month"},
                'monthly_budget': user_setting.monthly_budget
            }
        else:
            # If no user setting, return an appropriate empty response
            payoff_strategy_data = {}
    else:
        payoff_strategy_data = {
                'debt_payoff_method': payoff_strategy.debt_payoff_method,
                'selected_month': {"value": 1, "label": "Use Current Month"},
                'monthly_budget': payoff_strategy.monthly_budget
            }

    return jsonify({
        "payoff_strategy": payoff_strategy_data
    })



@app.route("/api/save-payoff-strategypg", methods=['POST'])
def save_payoff_strategy_pg():
    if request.method == 'POST':
        data = json.loads(request.data)        
        payoff_strategy_id = None
        payoff_id = data['user_id']
        message = ''
        result = 0

        try:
            # Attempt to find the PayoffStrategy for the given user_id
            payoff_strategy = PayoffStrategy.query.filter_by(user_id=payoff_id).first()

            if payoff_strategy:
                # If the PayoffStrategy exists, update it
                payoff_strategy.selected_month = data['selected_month']
                payoff_strategy.monthly_budget = float(data['monthly_budget'])
                payoff_strategy.debt_payoff_method = data['debt_payoff_method']
                message = 'Settings updated!'
            else:
                # If no PayoffStrategy exists, create a new one
                payoff_strategy = PayoffStrategy(
                    user_id=payoff_id,
                    selected_month=data['selected_month'],
                    monthly_budget=float(data['monthly_budget']),
                    debt_payoff_method=data['debt_payoff_method']
                )
                db.session.add(payoff_strategy)
                message = 'Settings saved!'

            # Commit changes to the database
            db.session.commit()
            payoff_strategy_id = payoff_strategy.id  # Get the ID of the saved/updated strategy
            result = 1
            
        except Exception as ex:
            print('PAYOFF EXP: ', ex)
            payoff_strategy_id = None
            result = 0
            message = 'Settings Failed!'

        return jsonify({
            "payoff_strategy_id": payoff_strategy_id,
            "message": message,
            "result": result
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



@app.route("/api/get-payoff-strategy-accountpg/<int:user_id>", methods=['GET'])
def get_payoff_strategy_account_pg(user_id:int):
    # Default value for debt_payoff_method
    debt_payoff_method = 0
    # Attempt to fetch the payoff strategy for the user
    payoff_strategy = db.session.query(
        PayoffStrategy.debt_payoff_method,
        PayoffStrategy.monthly_budget
    ).filter(PayoffStrategy.user_id == user_id).first()

    payoff_strategy_data = {
        'debt_payoff_method':None,
        'monthly_budget':0
    }
    
    # If payoff_strategy is not found, fall back to user settings
    if payoff_strategy is None:
        user_setting = db.session.query(
            UserSettings.debt_payoff_method, 
            UserSettings.monthly_budget).filter(UserSettings.user_id==user_id).first()
        if user_setting:            
            # Use user settings to populate payoff_strategy and set debt_payoff_method
            payoff_strategy_data = {
                'debt_payoff_method': user_setting.debt_payoff_method,
                'monthly_budget': user_setting.monthly_budget
            }
            debt_payoff_method = user_setting.debt_payoff_method['value']
    else:
        payoff_strategy_data = {
                'debt_payoff_method': payoff_strategy.debt_payoff_method,
                'monthly_budget': payoff_strategy.monthly_budget
        }
        # If payoff_strategy is found, extract debt_payoff_method
        debt_payoff_method = payoff_strategy.debt_payoff_method['value']
            
    # Fetch debt types where deleted_at is None
    debt_type_query = db.session.query(DebtType.id, DebtType.name).filter(DebtType.deleted_at == None).all()

    # Create a dictionary for debt type names
    debt_type_names = {}
    for debt_type in debt_type_query:
        debt_type_names[debt_type.id] = debt_type.name        

    # Query for debt accounts based on the provided criteria
    deb_query = db.session.query(
        DebtAccounts.id,        
        DebtAccounts.name,
        DebtAccounts.balance,
        DebtAccounts.interest_rate,
        DebtAccounts.monthly_interest,
        DebtAccounts.monthly_payment,
        DebtAccounts.credit_limit,
        DebtAccounts.month_debt_free,
        DebtAccounts.months_to_payoff,
        DebtAccounts.total_interest_sum,
        DebtAccounts.total_payment_sum,
        DebtType.id.label('debt_type')
    ).filter(
        DebtAccounts.user_id == user_id,
        DebtAccounts.deleted_at == None,
        DebtAccounts.closed_at == None
    )

    # Add sorting based on the payoff method
    if debt_payoff_method == 3:
        deb_query = deb_query.order_by(DebtAccounts.custom_payoff_order.asc())

    # Fetch data from the database
    # Fetch data from the database and convert to a list of dictionaries
    # Initialize the total to 0
    total_monthly_payment = 0

    debt_accounts_list = [
        {
            'id': debt.id,
            'debt_type': debt.debt_type,
            'name': debt.name,
            'balance': debt.balance,
            'interest_rate': debt.interest_rate,
            'monthly_interest': debt.monthly_interest,
            'monthly_payment': debt.monthly_payment,
            'credit_limit': debt.credit_limit,
            'month_debt_free': debt.month_debt_free,
            'months_to_payoff': debt.months_to_payoff,
            'total_interest_sum': debt.total_interest_sum,
            'total_payment_sum': debt.total_payment_sum
        }
        for debt in deb_query.all()
    ]


    #print('debt_accounts_list',debt_accounts_list)

    # Sorting debts if payoff method is not 3
    if debt_payoff_method != 3:
        debt_accounts_list = sort_debts_payoff(debt_accounts_list, debt_payoff_method)

    
    
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

    #total_monthly_payment = round(sum(account["monthly_payment"] for account in debt_accounts_list),2)

    debt_accounts_list = distribute_amount(payoff_strategy_data['monthly_budget'], debt_accounts_list)

    for index,account in enumerate(debt_accounts_list):
        debt_id = str(account['id'])
        debt_names[str(index+1)+debt_id] =account['name']
        debt_id_types[debt_id] = account['debt_type']
        debt_id_list.append(debt_id)
        account_balance = float(account['balance']+account['monthly_interest'])
        debt_account_balances[debt_id]= {
            'balance':account_balance,            
        }
        debt_totals[debt_id] = {
            "total_payment": 0,
            "total_interest": 0,
            "month_debt_free": None,
            "months_to_payoff": None  # Initialize as None
        }
        # Accumulate balance for the same debt type        
        monthly_data = []
        try:
            monthly_data = calculate_amortization(account['balance'], account['interest_rate'],account['monthly_payment'], account['credit_limit'], initail_date,payoff_strategy_data['monthly_budget']) 
        except Exception as ex:
            print('Exception handling',ex)
        
        if len(monthly_data) > 0:  # If there's data, add it to the correct month
            for record in monthly_data:
                month = record.get('month')
                amount = record.get('balance', 0)
                total_payment = record.get('total_payment', 0)
                snowball_amount = record.get('snowball_amount', 0)
                interest = record.get('interest', 0)
                # Build the query to filter and aggregate for the total amount
                payment_boost_data = db.session.query(
                    func.sum(PaymentBoost.amount)
                ).filter(
                    PaymentBoost.month == month,  # Filter by the month
                    PaymentBoost.deleted_at == None  # Filter out deleted records
                ).scalar()  # Use scalar to get the result as a single value

                # If no data is found, set the total_month_wise_boost to 0
                total_month_wise_boost = payment_boost_data if payment_boost_data else 0
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
                        merged_data[month][debt_id] = merged_data[all_months[all_months.index(month)-1]].get(debt_id, 0)

    # Convert to list of dicts for the frontend
    all_data = list(merged_data.values()) if len(merged_data) > 0 else []
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
    seen = set()
    debt_ids = [key for entry in all_data for key in entry if key not in ["boost", "month"] and key not in seen and not seen.add(key)]
    # Process each entry
    for month_index, entry in enumerate(all_data, start=1):
        row = [entry["month"]]
        total_snowball = 0
        total_interest = 0
        total_balance = 0
        total_payment = 0
                
        for debt_id in debt_ids:

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

    #print('debt_id_types',debt_id_types)
    
    debt_accounts_clist =  [
        {
            "id": debt_id,
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
            'total_monthly_payment':total_monthly_payment,
            "debt_type_ammortization":chart_data,            
            "debt_type_names":debt_names,
            "all_data":output,
            'all_d':data,
            'all_d1':all_data            
        })

    

