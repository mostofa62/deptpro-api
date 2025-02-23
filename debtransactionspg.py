
import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from app import app

import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal

from models import DebtAccounts, DebtType
from dbpg import db
from pgutils import PayoffOrder, ReminderDays, RepeatFrequency, new_entry_option_data, TransactionType, TransactionMonth, TransactionYear


from flask import request, jsonify
from datetime import datetime
from sqlalchemy import func, or_, select
from models import db, DebtAccounts, DebtType, DebtTransactions
from sqlalchemy.orm import joinedload
from db import my_col
debt_accounts_log = my_col('debt_accounts_log')

@app.route('/api/debt-transpg/<int:accntid>', methods=['POST'])
def get_debt_trans_pg(accntid:int):

    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    #global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])

    # Construct SQLAlchemy filter query

    
    '''
    query = DebtTransactions.query.with_entities(
        DebtTransactions.id,
        DebtTransactions.amount, 
        DebtTransactions.trans_date,
        DebtTransactions.type,
        DebtTransactions.previous_balance,
        DebtTransactions.new_balance,
        DebtTransactions.month,
        DebtTransactions.year,
        ).filter(
        DebtTransactions.debt_acc_id == accntid,
        DebtAccounts.deleted_at == None        
    )

    '''
    query = db.session.query( 
        DebtTransactions.id,
        DebtTransactions.amount, 
        DebtTransactions.trans_date,
        DebtTransactions.type,
        DebtTransactions.previous_balance,
        DebtTransactions.new_balance,
        DebtTransactions.month,
        DebtTransactions.year
        ).filter(
        DebtTransactions.debt_acc_id == accntid,
        DebtAccounts.deleted_at == None 
    )

    
    

    sort_params = []
    # Always append the default sort first
    default_sort = ('updated_at', -1)  # Sort by 'updated_at' in descending order by default
    if default_sort:
        sort_field = getattr(DebtTransactions, default_sort[0], None)
        if sort_field:
            sort_params.append(sort_field.desc() if default_sort[1] == -1 else sort_field.asc())

    # Append additional sorts from the sort_by list (if any)
    for sort in sort_by:
        sort_field = getattr(DebtTransactions, sort["id"], None)
        if sort_field:
            sort_params.append(sort_field.desc() if sort["desc"] else sort_field.asc())


    if sort_params:
        query = query.order_by(*sort_params)

    total_count = query.count()
    # Apply pagination
    query = query.offset(page_index * page_size).limit(page_size)


    # Pagination
    
    deebt_transactions = query.all()
    
    '''
    total_count = DebtTransactions.query.filter(
        DebtTransactions.debt_acc_id == accntid,
        DebtTransactions.deleted_at == None
    ).count()
    '''
    
    
    data_list = []
    for dtrans in deebt_transactions:
        todo = {
            'billing_month_year':f"{dtrans.month}, {dtrans.year}",
            'trans_date':convertDateTostring(dtrans.trans_date),
            'amount':round(dtrans.amount,2),
            'previous_balance':round(dtrans.previous_balance,2),
            'new_balance': round(dtrans.new_balance,2),
            'type':None,
            'month':None,
            'year':None
        }

       
        key_to_search = 'value'
        value_to_search = dtrans.type
        matching_dicts = next((dictionary for dictionary in TransactionType if dictionary.get(key_to_search) == value_to_search),None)            
        if matching_dicts:
            todo['type'] = matching_dicts['label']

        key_to_search = 'value'
        value_to_search = dtrans.month
        matching_dicts = next((dictionary for dictionary in TransactionMonth if dictionary.get(key_to_search) == value_to_search),None)            
        if matching_dicts:
            todo['month'] = matching_dicts['label']

        key_to_search = 'value'
        value_to_search = dtrans.year
        matching_dicts = next((dictionary for dictionary in TransactionYear if dictionary.get(key_to_search) == value_to_search),None)            
        if matching_dicts:
            todo['year'] = matching_dicts['label']
            
        data_list.append(todo)
    
    total_pages = (total_count + page_size - 1) // page_size

    return jsonify({
        'rows': data_list,
        'pageCount': total_pages,
        'totalRows': total_count
    })





@app.route("/api/save-debt-transactionpg/<int:accntid>", methods=['POST'])
def save_debt_transaction_pg(accntid:int):
    if request.method == 'POST':
        data = json.loads(request.data)
        debt_account_id = accntid
        debt_trans_id = None
        message = ''
        result = 0
        closed_at = None

        

        try:

            amount  = float(data['amount'])
            autopay = int(data['autopay']) if 'autopay' in data else 0 
            month = int(data['month']['value'])
            year =  int(data['year']['value'])
            type = int(data['type']['value'])                
            trans_date = datetime.strptime(data['trans_date'],"%Y-%m-%d")

            debt_account = (
                db.session.query(DebtAccounts)               
                .filter(DebtAccounts.id == accntid, DebtAccounts.deleted_at.is_(None))
                .first()
            )

            
            previous_balance = debt_account.balance
            new_balance = float(float(previous_balance) - float(amount)) if type > 1 else float(float(previous_balance) + float(amount))
            #end previous debt balance to update

            user_id = int(data['user_id'])

            #print(debt_account_id)
            #save debt transaction defaults
            debt_trans_data = DebtTransactions(                           
                amount=amount,
                previous_balance=previous_balance,
                new_balance=new_balance,                       
                trans_date=trans_date,
                type=type,
                month=month,
                year=year,               
                autopay=autopay,                                         
                created_at=datetime.now(),
                updated_at=datetime.now(),                        
                user_id=user_id,
                debt_acc_id=debt_account_id,
                payment_status=0,
                deleted_at=None
            )

            db.session.add(debt_trans_data)
            db.session.flush()

            debt_trans_id = debt_trans_data.id

            
            closed_at = datetime.now() if new_balance >= debt_account.highest_balance else None 
            debt_account.balance = new_balance
            debt_account.closed_at = closed_at
            debt_account.updated_at = datetime.now()

            debt_acc_query = {
                            "debt_id": debt_account_id,
                            "user_id":user_id
                }
            newvalues = { "$set": {                                  
                            'balance': new_balance,                            
                            'ammortization_at':None
                        } }
            debt_account_data = debt_accounts_log.update_one(debt_acc_query,newvalues,upsert=True)
            
            
            result = 1 if debt_account_id!=None and debt_trans_id!=None else 0
            message = 'Debt transaction added Succefull' if debt_account_id!=None and debt_trans_id!=None  else 'Debt transaction addition Failed!'
            db.session.commit()

            
        except Exception as ex:
            print('DEBT EXP: ',ex)
            debt_account_id = None
            debt_trans_id = None
            result = 0
            message = 'Debt transaction addition Failed!'
            db.session.rollback()
            closed_at = None


        return jsonify({
            "debt_account_id":debt_account_id,
            "debt_trans_id":debt_trans_id,
            "message":message,
            "result":result,
            "closed_at":closed_at
        })


