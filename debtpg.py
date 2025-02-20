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
from models import db, DebtAccounts, DebtType
from sqlalchemy.orm import joinedload


@app.route('/api/debt-allpg/<int:accntid>', methods=['GET'])
def get_dept_all_pg(accntid:int):

    debt_account = (
        db.session.query(DebtAccounts)
        .options(
            joinedload(DebtAccounts.debt_type).joinedload(DebtType.parent)
        )
        .filter(DebtAccounts.id == accntid, DebtAccounts.deleted_at.is_(None))
        .first()
    )    

    debtaccounts = {
        "name": debt_account.name,
        "payor":debt_account.payor,        
        "note":debt_account.note        
    }

    debt_type = debt_account.debt_type
    if debt_type:            
        debtaccounts['debt_type']= debt_type.name
     
        
    debtaccounts['due_date_word'] = convertDateTostring(debt_account.due_date)
    debtaccounts['due_date'] = convertDateTostring(debt_account.due_date,'%Y-%m-%d')
    debtaccounts['start_date_word'] = convertDateTostring(debt_account.start_date)
    debtaccounts['start_date'] = convertDateTostring(debt_account.start_date,'%Y-%m-%d')
    

    key_to_search = 'value'
    value_to_search = int(debt_account.payoff_order)
    matching_dicts = next((dictionary for dictionary in PayoffOrder if dictionary.get(key_to_search) == value_to_search),None)    

    if matching_dicts:
        debtaccounts['payoff_order'] = matching_dicts['label']

    debtaccounts['balance'] = round(debt_account.balance,2)
    debtaccounts['highest_balance'] = round(debt_account.highest_balance,2)   
    debtaccounts['monthly_payment'] = round(debt_account.monthly_payment,2)
    debtaccounts['interest_rate'] = round(debt_account.interest_rate,2)
    debtaccounts['credit_limit'] = round(debt_account.credit_limit,2)
    debtaccounts['monthly_interest'] = round(debt_account.monthly_interest,2)
    


    key_to_search = 'value'
    value_to_search = int(debt_account.reminder_days)
    matching_dicts = next((dictionary for dictionary in ReminderDays if dictionary.get(key_to_search) == value_to_search),None)    
    if matching_dicts:
        debtaccounts['reminder_days'] = matching_dicts['label']

    debtaccounts['autopay'] = 'Yes'  if debt_account.autopay > 0 else 'No'
    debtaccounts['inlclude_payoff'] = 'Yes'  if debt_account.inlclude_payoff > 0 else 'No'
    
    paid_off_percentage = calculate_paid_off_percentage(debtaccounts['highest_balance'], debtaccounts['balance'])
    left_to_go = round(float(100) - float(paid_off_percentage),1)

    twelve_months_ago = datetime.now() - timedelta(days=365)

    
    

    return jsonify({
        "payLoads":{
            "debtaccounts":debtaccounts,
            "debttrasactions":[],        
            "left_to_go":left_to_go,
            "paid_off_percentage":paid_off_percentage            
        }        
    })



@app.route('/api/debt-transaction-dropdownpg', methods=['GET'])
def get_debt_transaction_dropdown_pg():


    return jsonify({
        "transaction_type":TransactionType,
        "transaction_month":TransactionMonth,
        "transaction_year":TransactionYear        
    })

@app.route('/api/debtspg/<int:user_id>', methods=['POST'])
def list_debts_pg(user_id:int):

    action  = request.args.get('action', None)
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])

    # Construct SQLAlchemy filter query
    query = db.session.query(DebtAccounts).filter(
        DebtAccounts.user_id == user_id,
        DebtAccounts.deleted_at == None,
        DebtAccounts.closed_at == None
    )

    if action is not None:
        query = query.filter(
            DebtAccounts.closed_at != None
        )


    if global_filter:

        debt_type_subquery_stmt = select(DebtType.id).where(
            DebtType.name.ilike(f"%{global_filter}%")
        )
        
        pattern_str = r'^\d{4}-\d{2}-\d{2}$'
        due_date = None
        #try:
        if re.match(pattern_str, global_filter):
            due_date = convertStringTodate(global_filter)
        #except ValueError:
        else:
            due_date = None


        query = query.filter(or_(
            DebtAccounts.name.ilike(f'%{global_filter}%'),
            DebtAccounts.debt_type_id.in_(debt_type_subquery_stmt),
            DebtAccounts.due_date == due_date
            )
        )

    sort_params = []
    for sort in sort_by:
        sort_field = getattr(DebtAccounts, sort["id"], None)
        if sort_field:
            sort_params.append(sort_field.desc() if sort["desc"] else sort_field.asc())

    if sort_params:
        query = query.order_by(*sort_params)

    # Pagination
    total_count = query.count()
    debts = (query.options(joinedload(DebtAccounts.debt_type)).
    offset(page_index * page_size).
    limit(page_size).all()
    )

    data_list = []
    for debt in debts:
        debt_type = debt.debt_type
        debt_type_parent = debt_type.parent if debt_type and debt_type.parent else None
    
        # matching_dict = next(
        #     (item for item in ReminderDays if item['value'] == debt.reminder_days),
        #     None
        # )
        # reminder_days = matching_dict['label'] if matching_dict else None

        paid_off_percentage = calculate_paid_off_percentage(debt.highest_balance, debt.balance)
        left_to_go = round(float(100) - float(paid_off_percentage),1)

        debt_data = {
            "_id":debt.id,
            'name': debt.name,
            'debt_type': debt_type.name if debt_type else None,      
            'debt_type_parent': debt_type_parent.name if debt_type_parent else None,
            'payor': debt.payor,
            "balance":round(debt.balance,2),
            "interest_rate":debt.interest_rate,
            #"minimum_payment":round(todo["minimum_payment"],2),
            "monthly_payment":round(debt.monthly_payment,2),
            "monthly_interest":round(debt.monthly_interest,2),
            "due_date":convertDateTostring(debt.due_date),
            "left_to_go":left_to_go,
            "paid_off_percentage":paid_off_percentage            
            
        }
        
        
        data_list.append(debt_data)

    total_pages = (total_count + page_size - 1) // page_size    
   


    # Summing multiple fields in a single query
    totals = db.session.query(
        func.sum(DebtAccounts.balance).label('total_balance'),
        func.sum(DebtAccounts.highest_balance).label('total_highest_balance'),
        func.sum(DebtAccounts.monthly_payment).label('total_monthly_payment'),
        func.sum(DebtAccounts.monthly_interest).label('total_monthly_interest')
    ).one()

    # Extracting totals from the result
    total_balance = totals.total_balance or 0
    total_highest_balance = totals.total_highest_balance or 0
    total_monthly_payment = totals.total_monthly_payment or 0
    total_monthly_interest = totals.total_monthly_interest or 0
    # Calculate the paid-off percentage
    total_paid_off = calculate_paid_off_percentage(total_highest_balance, total_balance)
    #total_minimum_payment = result[0]['total_minimum_payment'] if result else 0

    return jsonify({
        'rows': data_list,
        'pageCount': total_pages,
        'totalRows': total_count,
        'extra_payload':{
            'total_balance':total_balance,
            'total_monthly_payment':total_monthly_payment,
            'total_monthly_interest':total_monthly_interest,
            'total_paid_off':total_paid_off,
            #'total_minimum_payment':total_minimum_payment
        }
        
    })




@app.route('/api/debt-summarypg/<int:accntid>', methods=['GET'])
def get_dept_summary_pg(accntid:int):

    # Load the BillAccount along with related BillType and Parent BillType in one query
    debt_account = (
        db.session.query(DebtAccounts.highest_balance, DebtAccounts.balance)        
        .filter(DebtAccounts.id == accntid, DebtAccounts.deleted_at.is_(None))
        .first()
    )

    
    
    paid_off_percentage = calculate_paid_off_percentage(debt_account.highest_balance, debt_account.balance)
    left_to_go = round(float(100) - float(paid_off_percentage),1)
    

    return jsonify({
         "currentBalance":debt_account.balance,
        "left_to_go":left_to_go,
        "paid_off_percentage":paid_off_percentage      
    })

@app.route('/api/debtpg/<int:accntid>', methods=['GET'])
def get_debt_pg(accntid:int):

    # Load the BillAccount along with related BillType and Parent BillType in one query
    debt_account = (
        db.session.query(DebtAccounts)
        .options(
            joinedload(DebtAccounts.debt_type).joinedload(DebtType.parent)
        )
        .filter(DebtAccounts.id == accntid, DebtAccounts.deleted_at.is_(None))
        .first()
    )    

    debtaccounts = {
        "name": debt_account.name,
        "payor":debt_account.payor,
        "debt_type": {
            "value":None,
            "label":None
        },        
        "due_date": convertDateTostring(debt_account.due_date, '%Y-%m-%d'),
        "start_date":convertDateTostring(debt_account.start_date, '%Y-%m-%d'),
        "balance": round(debt_account.balance or 0, 2),
        "highest_balance": round(debt_account.highest_balance or 0, 2),
        "monthly_payment": round(debt_account.monthly_payment or 0, 2),
        "interest_rate": round(debt_account.interest_rate or 0, 2),
        "credit_limit": round(debt_account.credit_limit or 0, 2),
        "payoff_order":None,
        "reminder_days": None,
        "repeat_frequency": None,
        "note":debt_account.note
        
    }

    debt_type = debt_account.debt_type
    if debt_type:    
        debtaccounts['debt_type']['value'] = debt_type.id
        debtaccounts['debt_type']['label'] = debt_type.name
    
    key_to_search = 'value'
    value_to_search = debt_account.payoff_order
    matching_dicts = next((dictionary for dictionary in PayoffOrder if dictionary.get(key_to_search) == value_to_search),None)    
    if matching_dicts:
        debtaccounts['payoff_order'] = {
            'value':value_to_search,
            'label':matching_dicts['label']
        }
    

    key_to_search = 'value'
    value_to_search = debt_account.reminder_days
    matching_dicts = next((dictionary for dictionary in ReminderDays if dictionary.get(key_to_search) == value_to_search),None)    
    if matching_dicts:
        debtaccounts['reminder_days'] = {
            'value':value_to_search,
            'label':matching_dicts['label']
        }


    
    


    return jsonify({
        "debtaccounts":debtaccounts,
        "payoff_order":PayoffOrder,        
        "reminder_days":ReminderDays,
       
    })


@app.route("/api/save-debt-accountpg", methods=['POST'])
def save_debt_account_pg():
    if request.method == 'POST':
        data = json.loads(request.data)
        debt_id = None
        message = ''
        result = 0
        
        try:
            user_id = data["user_id"]
            total_count = db.session.query(func.count(DebtAccounts.id)).filter(
                DebtAccounts.user_id == user_id,
                DebtAccounts.deleted_at == None
            ).scalar()

            balance = float(data.get("balance", 0))
            interest_rate = float(data.get("interest_rate", 0))
            highest_balance = float(data.get("highest_balance", 0))
            highest_balance = highest_balance if highest_balance > 0 else balance
            closed_at = datetime.now() if balance >= highest_balance else None
            
            debt_account = DebtAccounts(
                name=data.get("name"),
                debt_type_id=new_entry_option_data(data['debt_type'], DebtType, user_id),
                payor=data.get("payor"), 
                balance=balance,                
                highest_balance=highest_balance,
                monthly_payment=float(data.get("monthly_payment", 0)),
                credit_limit=float(data.get("credit_limit", 0)),
                interest_rate=interest_rate,
                start_date=convertStringTodate(data['start_date']),
                due_date=convertStringTodate(data['due_date']),
                monthly_interest=calculate_monthly_interest(balance, interest_rate),
                note=None,
                promo_rate=0,
                deffered_interest=0,
                promo_interest_rate=0,
                promo_good_through_month=None,
                promo_good_through_year=None,
                promo_monthly_interest=0,
                autopay=0,
                inlclude_payoff=0,
                payoff_order=0,
                custom_payoff_order=total_count+1,
                reminder_days=0,
                monthly_payment_option=0,
                percentage=0,
                lowest_payment=0,
                user_id=user_id,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                deleted_at=None,
                closed_at=closed_at,
                months_to_payoff=0,
                month_debt_free=None,
                total_payment_sum=0,
                total_interest_sum=0
            )

            db.session.add(debt_account)
            db.session.commit()

            debt_id = debt_account.id
            result = 1 if debt_id else 0
            message = 'Debt account added successfully'
        
        except Exception as ex:
            print(ex)
            db.session.rollback()
            debt_id = None
            result = 0
            message = 'Debt account addition failed'

        return jsonify({
            "debt_id": debt_id,            
            "message": message,
            "result": result
        })




@app.route("/api/update-debt-accountpg/<int:accntid>", methods=['POST'])
def update_debt_account_pg(accntid:int):
    if request.method == 'POST':
        data = json.loads(request.data)
        debt_id = None
        message = ''
        result = 0
        
        try:

            user_id = data["user_id"]
            
            debtaccounts = (
                db.session.query(DebtAccounts)               
                .filter(DebtAccounts.id == accntid, DebtAccounts.deleted_at.is_(None))
                .first()
            )
            balance = float(data.get("balance", 0))
            interest_rate = float(data.get("interest_rate", 0))
            highest_balance =  float(data.get("highest_balance", 0))
            highest_balance = highest_balance if highest_balance > 0 else balance

            autopay = True if 'autopay' in data else False
            inlclude_payoff=True if 'inlclude_payoff' in data  else False
            print(autopay, inlclude_payoff)
            payoff_order = int(data['payoff_order']['value'])            
            reminder_days = int(data['reminder_days']['value'])
            
            monthly_interest =   debtaccounts.monthly_interest
            
            if interest_rate > 0 and are_floats_equal(interest_rate,debtaccounts.interest_rate) == False:
               monthly_interest = calculate_monthly_interest(balance,interest_rate)


            debtaccounts.name = data.get("name")
            debtaccounts.debt_type_id = new_entry_option_data(data['debt_type'], DebtType, user_id)
            debtaccounts.balance=balance
            debtaccounts.highest_balance= highest_balance              
            debtaccounts.monthly_payment= float(data.get("monthly_payment", 0))
            debtaccounts.credit_limit= float(data.get("credit_limit", 0))
            debtaccounts.interest_rate=interest_rate
            debtaccounts.monthly_interest=monthly_interest
            debtaccounts.due_date=convertStringTodate(data['due_date'])
            debtaccounts.start_date= convertStringTodate(data['start_date'])                            
            debtaccounts.inlclude_payoff=inlclude_payoff
            debtaccounts.payoff_order=payoff_order               
            debtaccounts.reminder_days=reminder_days
            debtaccounts.autopay=autopay
            debtaccounts.note=data['note'] if 'note' in data and data['note']!=""  else None                                     
            debtaccounts.updated_at=datetime.now()
            
           
                

            db.session.add(debtaccounts)
            db.session.commit()

            debt_id = debtaccounts.id
            result = 1 if debt_id else 0
            message = 'Debt account added successfully'
        
        except Exception as ex:
            print(ex)
            db.session.rollback()
            debt_id = None
            result = 0
            message = 'Debt account addition failed'

        return jsonify({
            "debt_id": debt_id,            
            "message": message,
            "result": result
        })







