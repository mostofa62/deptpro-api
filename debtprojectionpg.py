import os
from flask import Flask,request,jsonify, json
from sqlalchemy import asc, func
#from flask_cors import CORS, cross_origin
from app import app

import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal

from models import DebtAccounts, DebtType, DebtTransactions
from dbpg import db

from db import my_col,mydb
debt_accounts_log = my_col('debt_accounts_log')

@app.route("/api/debt-projectionpg/<int:userid>", methods=['GET'])
def debt_projection_pg(userid:int):


    #allocation 
    # Get current month in 'YYYY-MM' format
    current_month_str = datetime.now().strftime("%Y-%m")
    session = db.session
    try:
        query = session.query(
            DebtAccounts.debt_type_id.label('id'),
            DebtType.name.label("name"),
            func.sum(DebtTransactions.amount).label("balance"),
            func.count(DebtAccounts.debt_type_id).label('count'),
        ).join(DebtAccounts, DebtTransactions.debt_acc_id == DebtAccounts.id) \
        .join(DebtType, DebtAccounts.debt_type_id == DebtType.id) \
        .filter(
            func.to_char(DebtTransactions.trans_date, 'YYYY-MM') == current_month_str,
            DebtAccounts.user_id == userid,  # Filter by user_id
            DebtAccounts.deleted_at == None,
            DebtAccounts.closed_at == None
        ) \
        .group_by(
            DebtAccounts.debt_type_id,
            DebtType.name
        )
        
        results = query.all()

        total_balance = 0
        total_bill_type = 0
        #debt_type_names = {}
        bill_type_bill_counts = []
        

        for row in results:
            total_balance += row.balance
            total_bill_type += 1
            #debt_type_names[row.id] = row.name
            bill_type_bill_counts.append({"id": row.id, "name": row.name, "balance": row.balance, "count": row.count})

        debt_types = session.query(DebtType.id, DebtType.name).all()
        debt_type_names = {str(d.id): d.name for d in debt_types}

        query = db.session.query(
            DebtAccounts.id,
            DebtAccounts.name,
            DebtAccounts.balance,
            DebtAccounts.monthly_interest,
            DebtAccounts.due_date,
            DebtAccounts.debt_type_id,        
        )\
        .filter(
            DebtAccounts.user_id == userid,
            DebtAccounts.deleted_at == None,
            DebtAccounts.closed_at == None
        )\
        .order_by(asc(DebtAccounts.due_date))
    
        data = {}

        debt_type_balances = {}

        debt_accounts_data = query.all()

        for account in debt_accounts_data:
            account_id = str(account.id)
            debt_type_id = str(account.debt_type_id)  # Get the debt type ID        
            dynamic_collection_name = f"debt_{account_id}"
            account_balance = float(account.balance+account.monthly_interest)

            # Accumulate balance for the same debt type
            if debt_type_id in debt_type_balances:
                debt_type_balances[debt_type_id] += account_balance
            else:
                debt_type_balances[debt_type_id] = account_balance

            # Check if the collection exists
            if dynamic_collection_name in mydb.list_collection_names():
                monthly_data = []
                # Step 3: Query the dynamic collection (debt_<id>) for balance and month
                dynamic_collection = mydb[dynamic_collection_name]
                sort_params = [('month_debt_free', 1)]
                try:
                    monthly_data = dynamic_collection.find({}, {'month': 1, 'month_debt_free': 1, 'balance': 1}).sort(sort_params)
                except Exception as e:
                    print(f"Error fetching data for collection {dynamic_collection_name}: {str(e)}")
                    continue  # Skip this account if there's an error

                # Step 4: Structure the data in the required format
                if monthly_data:  # If there's data, add it to the correct month
                    for record in monthly_data:
                        month = record.get('month')
                        amount = record.get('balance', 0)

                        # Initialize the month entry if not already present
                        if month not in data:
                            data[month] = {'month': month}

                        # Sum amounts for the same month and debt type
                        if debt_type_id in data[month]:
                            data[month][debt_type_id] += amount
                        else:
                            data[month][debt_type_id] = amount                                                  
        
        
        
        start_date = convertDateTostring(datetime.now(),'%b %Y')
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
            print('all months',all_months)

            # Initialize merged_data with all months and set missing values to debt_type_balances
            for month in all_months:
                merged_data[month] = {'month': month}
                for debt_type in debt_type_balances:  # Iterate over all debt types
                    if month == start_date:
                        # Use debt_type_balances for start_date
                        merged_data[month][debt_type] = debt_type_balances.get(debt_type, 0)
                    elif parse_month(month) < parse_month(start_date):
                        # For months before start_date, use debt_type_balances
                        merged_data[month][debt_type] = debt_type_balances.get(debt_type, 0)
                    else:
                        # For other months, check if data is present
                        if month in data and debt_type in data[month]:
                            merged_data[month][debt_type] = data[month][debt_type]
                        else:
                            # Fill missing month data with last known debt_type_balances
                            merged_data[month][debt_type] = merged_data[all_months[all_months.index(month)-1]].get(debt_type, debt_type_balances.get(debt_type, 0))

        # Convert to list of dicts for the frontend
        chart_data = list(merged_data.values()) if len(merged_data) > 0 else []

        return jsonify({
            "payLoads":{
                "debt_type_debt_counts":bill_type_bill_counts,
                "total_dept_type":total_bill_type,
                "total_balance":total_balance,
                "debt_type_names":debt_type_names,                            
                "debt_type_ammortization":chart_data,
                #"bill_type_ammortization":normalized_data,
                "data":[]                            
            }        
        })
    
    except Exception as e:
        #session.rollback()  # Rollback in case of error
        return jsonify({
            "payLoads":{
                "debt_type_debt_counts":0,
                "total_dept_type":0,
                "total_balance":0,
                "debt_type_names":{},                            
                "debt_type_ammortization":[],
                #"bill_type_ammortization":normalized_data,
                "data":[]                            
            }        
        })

    finally:
        session.close()