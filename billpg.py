import os
from flask import Flask,request,jsonify, json
from sqlalchemy import asc, desc, or_, select, update
#from flask_cors import CORS, cross_origin
from billtypepg import bill_type_dropdown_pg
from app import app
import re
from util import *
from datetime import datetime,timedelta
from pgutils import ReminderDays, RepeatFrequency, new_entry_option_data, ExtraType
from dbpg import db
from models import *
from sqlalchemy.orm import joinedload
from db import my_col
from billutil import generate_bill, get_freq_data
calender_data = my_col('calender_data')
@app.route('/api/billspg/<int:user_id>', methods=['POST'])
async def list_bills_pg(user_id: int):
    action = request.args.get('action', None)
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])

    # Construct SQLAlchemy filter query
    query = db.session.query(BillAccounts).filter(
        BillAccounts.user_id == user_id,
        BillAccounts.deleted_at == None,
        BillAccounts.closed_at == None
    )

    if action is not None:
        query = query.filter(
            BillAccounts.closed_at != None
        )

    if global_filter:
        
        bill_types_subquery_stmt = select(BillType.id).where(
            BillType.name.ilike(f"%{global_filter}%")
        )
        pattern_str = r'^\d{4}-\d{2}-\d{2}$'
        next_due_date = None
        if re.match(pattern_str, global_filter):
            next_due_date = convertStringTodate(global_filter)
        else:
            next_due_date = None

        query = query.filter(or_(
            BillAccounts.name.ilike(f'%{global_filter}%'),
            BillAccounts.bill_type_id.in_(bill_types_subquery_stmt),
            BillAccounts.next_due_date == next_due_date
            )
        )
        

    
    sort_params = []
    for sort in sort_by:
        sort_field = getattr(BillAccounts, sort["id"], None)
        if sort_field:
            sort_params.append(sort_field.desc() if sort["desc"] else sort_field.asc())

    if sort_params:
        query = query.order_by(*sort_params)

    # Pagination
    total_count = query.count()
    bills = (query.options(joinedload(BillAccounts.bill_type)).
    offset(page_index * page_size).
    limit(page_size).all()
    )

    data_list = []
    for bill in bills:
        bill_type = bill.bill_type
        bill_type_parent = bill_type.parent if bill_type and bill_type.parent else None

        matching_dict = next(
            (item for item in RepeatFrequency if item['value'] == bill.repeat_frequency),
            None
        )
        repeat_frequency = matching_dict['label'] if matching_dict else None

        matching_dict = next(
            (item for item in ReminderDays if item['value'] == bill.reminder_days),
            None
        )
        reminder_days = matching_dict['label'] if matching_dict else None

        bill_data = {
            'id': bill.id,
            'name': bill.name,
            'bill_type': bill_type.name if bill_type else None,
            'bill_type_parent': bill_type_parent.name if bill_type_parent else None,
            'next_due_date': convertDateTostring(bill.next_due_date),
            'repeat_frequency': repeat_frequency,
            'payor': bill.payor,
            'default_amount': bill.default_amount,
            'current_amount': bill.current_amount,
            'paid_total': bill.paid_total,
            'reminder_days': reminder_days,
            'note': bill.note,
            'created_at': convertDateTostring(bill.created_at),
            'updated_at': convertDateTostring(bill.updated_at)
        }
        
        data_list.append(bill_data)

    total_pages = (total_count + page_size - 1) // page_size

    return jsonify({
        'rows': data_list,
        'pageCount': total_pages,
        'totalRows': total_count
    })


@app.route("/api/save-bill-accountpg", methods=['POST'])
def save_bill_account_pg():
    if request.method == 'POST':
        data = request.get_json()  # Get JSON data directly
        bill_account_id = None
        bill_trans_id = None
        message = ''
        result = 0

        try:
            amount = int(data['default_amount'])
            repeat_frequency = int(data['repeat_frequency']['value'])
            reminder_days = int(data['reminder_days']['value'])
            next_due_date = convertStringTodate(data['next_due_date'])
            op_type = ExtraType[0]['value']  # Assuming you fetch operation type somewhere
            
            # Get user and bill type
            user_id = data['user_id']
            admin_id = data['admin_id']
            bill_type_id = data['bill_type']['value']
            current_amount = amount
            current_datetime_now = datetime.now()
            current_billing_month = int(convertDateTostring(current_datetime_now,'%Y%m'))                        

            # Create BillAccount record
            bill_account = BillAccounts(
                name=data['name'],
                bill_type_id=bill_type_id,
                payor=data.get('payor', None),
                default_amount=current_amount,
                current_amount=current_amount,
                paid_total=0,
                next_due_date=next_due_date,
                repeat_frequency=repeat_frequency,
                reminder_days=reminder_days,
                note=data.get('note', None),
                created_at=current_datetime_now,
                updated_at=current_datetime_now,
                user_id=user_id,
                admin_id=admin_id,
                latest_transaction_id=None,  # Set later
                deleted_at=None,
                closed_at=None
            )
            db.session.add(bill_account)
            db.session.flush()  # Commit to get the bill_account ID
            bill_account_id = bill_account.id

            bill_trans_id = None
            no_repeat_next = 0
            total_monthly_unpaid_bill = 0
            total_monthly_unpaid_billf = 0            
            
            if repeat_frequency > 0:
                bill_transaction_generate = generate_bill(
                    amount,
                    next_due_date,
                    repeat_frequency,
                    user_id,
                    admin_id,
                    bill_account_id,
                    op_type                    
                )
                bill_transaction_list = bill_transaction_generate['bill_transaction']
                current_amount = bill_transaction_generate['current_amount']
                next_due_date = bill_transaction_generate['next_pay_date']
                is_single = bill_transaction_generate['is_single']
                total_monthly_unpaid_bill = bill_transaction_generate['total_monthly_unpaid_bill']
                current_next_due_month = int(convertDateTostring(next_due_date,'%Y%m'))
                if current_billing_month == current_next_due_month:
                    future_data = get_freq_data(next_due_date.date(),repeat_frequency,amount)
                    total_monthly_unpaid_billf = future_data['amount']
                bill_transaction = None
                if len(bill_transaction_list) > 0:
                    if is_single > 0:
                        bill_transaction = BillTransactions(**bill_transaction_list)
                        db.session.add(bill_transaction)
                    else:
                        bill_transaction = [BillTransactions(**txn) for txn in bill_transaction_list]
                        db.session.add_all(bill_transaction)



                # Create BillTransaction record
                if bill_transaction!=None:
                    db.session.flush()  # Commit to get the transaction ID
                    bill_trans_id = bill_transaction.id if is_single > 0 else bill_transaction[-1].id
            else:
                
                if next_due_date <= current_datetime_now:
                    no_repeat_next = 1
                    bill_transaction = BillTransactions(
                        amount=amount,
                        type=op_type,
                        payor=None,
                        note=None,
                        current_amount=amount,
                        pay_date = next_due_date,
                        due_date=next_due_date,
                        created_at=current_datetime_now,
                        updated_at=current_datetime_now,
                        user_id=user_id,
                        admin_id=admin_id,
                        bill_acc_id=bill_account.id,
                        payment_status=0,                        
                        repeat_frequency=repeat_frequency
                    )
                    db.session.add(bill_transaction)
                    db.session.flush()  # Commit to get the transaction ID
                    bill_trans_id = bill_transaction.id

                month = int(next_due_date.strftime("%Y%m"))
                if month == int(current_datetime_now.strftime('%Y%m')):                         
                    if next_due_date <= current_datetime_now:
                        total_monthly_unpaid_bill+=amount
                    elif  next_due_date > current_datetime_now:
                        total_monthly_unpaid_billf+=amount

            if repeat_frequency < 1 and no_repeat_next < 1:
                current_amount = 0
            # Update BillAccount with the latest_transaction_id
            bill_account.latest_transaction_id = bill_trans_id
            bill_account.current_amount = current_amount
            bill_account.updated_at = current_datetime_now
            bill_account.next_due_date = next_due_date
            bill_account.single_done = 1 if repeat_frequency < 1 and no_repeat_next > 0 else 0
            bill_account.auto_update = int(not no_repeat_next)
            
            app_data = db.session.query(AppData).filter(AppData.user_id == user_id).first()
            if app_data:
                # Update the existing record                    
                if app_data.current_billing_month_up!= None and app_data.current_billing_month_up == current_billing_month:
                    app_data.total_monthly_bill_unpaid += total_monthly_unpaid_bill
                    app_data.total_monthly_bill_unpaidf += total_monthly_unpaid_billf
                else:
                    app_data.total_monthly_bill_unpaid =  total_monthly_unpaid_bill
                    app_data.total_monthly_bill_unpaidf = total_monthly_unpaid_billf
                    app_data.current_billing_month_up = current_billing_month
                    app_data.current_billing_month_upf = current_billing_month                   
                    
                    
                    
            else:
                # Insert a new record if the user doesn't exist
                app_data = AppData(
                    user_id=user_id,
                    current_billing_month_up = current_billing_month,
                    total_monthly_bill_unpaid=total_monthly_unpaid_bill,
                    total_monthly_unpaid_billf=total_monthly_unpaid_billf,
                    current_billing_month_upf=current_billing_month                                                
                )

                
                db.session.add(app_data)
            db.session.commit()  # Commit the update

            result = 1 if bill_account_id else 0
            message = 'Bill account added successfully' if result else 'Bill account addition failed!'

        except Exception as ex:
            print(f'Error: {ex}')
            db.session.rollback()  # Rollback if something goes wrong
            result = 0
            message = 'Bill account addition failed!'

        finally:
            db.session.close()

        return jsonify({
            "bill_account_id": bill_account_id,
            "bill_trans_id": bill_trans_id,
            "message": message,
            "result": result
        })



@app.route("/api/update-bill-accountpg/<int:accntid>", methods=['POST'])
def update_bill_pg(accntid:int):
    if request.method == 'POST':
        data = json.loads(request.data)
        bill_account_id = accntid
        message = ''
        result = 0

        admin_id = data['admin_id']
        data.pop('created_at', None)
        data.pop('updated_at', None)

        amount  = float(data['default_amount'])            
        repeat_frequency = safe_nested_int(data, 'repeat_frequency')
        reminder_days = safe_nested_int(data, 'reminder_days')


        bill_account = BillAccounts.query.filter_by(id=accntid).first()
        previous_frequency = bill_account.repeat_frequency
        previous_amount = bill_account.default_amount
        latest_transaction = bill_account.latest_transaction
        payment_count = latest_transaction.payments.count()
        paid_total = bill_account.paid_total
        previous_due_date = bill_account.next_due_date
        

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        valid = True
        change_found_amount = False if are_floats_equal(amount, previous_amount) else True
        current_amount = amount  if payment_count < 1 and change_found_amount else bill_account.current_amount
        

        if previous_frequency < 1:
            
            if repeat_frequency >  previous_frequency:
                valid = False
                message = 'Non-repeat accounts cannot be upgraded to repeat accounts. Please create a new account instead.'
            if payment_count > 0 and change_found_amount:
                valid = False
                message = f'This account has already been settled with a payment of {paid_total}; modifying the amount {amount} is not permitted.'
            if previous_due_date <= today and reminder_days > 0:
                valid = False
                message = 'Reminders cannot be set for past due dates in non-recurring accounts.'

            
        if not valid:    
            return jsonify({
                "bill_account_id":bill_account_id,            
                "message":message,
                "result":0
            })           
        
        

        try:            

            stmt = update(BillAccounts).where(BillAccounts.id == bill_account_id).values(
                    name=data['name'],
                    bill_type_id=data['bill_type']['value'],
                    payor=data['payor'] if 'payor' in  data else None,
                    default_amount=amount,
                    current_amount=current_amount,                      
                    repeat_frequency=repeat_frequency,
                    reminder_days = reminder_days,
                    note=data['note'] if 'note' in data and data['note']!=None else None,
                    updated_at=datetime.now(),
                    admin_id=admin_id
                )
            
            db.session.execute(stmt)

            if previous_frequency < 1 and change_found_amount:
                latest_transaction.amount = amount
                latest_transaction.current_amount = amount
                latest_transaction.admin_id = admin_id
                db.session.add(latest_transaction)

            db.session.commit()
            result = 1 
            message = 'Bill account updated successfully'

        except Exception as ex:

            print('BILL UPDATE EX: ',ex)

            bill_account_id = None            
            result = 0
            message = 'Bill account update Failed!'
            db.session.rollback()

        finally:
            db.session.close()


        return jsonify({
            "bill_account_id":bill_account_id,            
            "message":message,
            "result":result
        })

@app.route('/api/bill-allpg/<int:accntid>', methods=['GET'])
def get_bill_all_pg(accntid: int):
    # Load the BillAccount along with related BillType and Parent BillType in one query
    bill_account = (
        db.session.query(BillAccounts)
        .options(
            joinedload(BillAccounts.bill_type).joinedload(BillType.parent)
        )
        .filter(BillAccounts.id == accntid, BillAccounts.deleted_at.is_(None))
        .first()
    )
   
    # Get Bill Type and its Parent
    bill_type = bill_account.bill_type
    bill_type_name = bill_type.name if bill_type else None
    bill_type_parent_name = bill_type.parent.name if bill_type and bill_type.parent else None

    # Prepare the response object
    billaccounts = {
        "name": bill_account.name,
        "bill_type": bill_type_name,
        "bill_type_parent": bill_type_parent_name,
        "next_due_date_word": convertDateTostring(bill_account.next_due_date),
        "next_due_date": convertDateTostring(bill_account.next_due_date, '%Y-%m-%d'),
        "default_amount": round(bill_account.default_amount or 0, 2),
        "current_amount": round(bill_account.current_amount or 0, 2),
        "reminder_days": next(
            (d['label'] for d in ReminderDays if d['value'] == bill_account.reminder_days),
            None
        ),
        "repeat_frequency": next(
            (d['label'] for d in RepeatFrequency if d['value'] == bill_account.repeat_frequency),
            None
        ),
        "created_at":convertDateTostring(bill_account.created_at,"%d %b, %Y %H:%M"),
        "updated_at":convertDateTostring(bill_account.updated_at,"%d %b, %Y %H:%M")
    }

    # Get Bill Payments for the last 12 months
    twelve_months_ago = datetime.now() - timedelta(days=365)
    bill_payments = (
        db.session.query(BillPayments)
        .filter(
            BillPayments.bill_account_id == accntid,
            BillPayments.pay_date >= twelve_months_ago,
            BillPayments.deleted_at.is_(None)
        )
        .all()
    )

    # Prepare payments data
    billpayments = [
        {
            "pay_date_word": payment.pay_date.strftime('%d %b, %Y'),
            "pay_date": payment.pay_date.strftime('%Y-%m-%d'),
            "amount": round(payment.amount, 2)
        }
        for payment in bill_payments
    ]

    # JSON response
    return jsonify({
        "payLoads": {
            "billaccounts": billaccounts,
            "billpayments": billpayments,
        }
    })



@app.route('/api/billpg/<int:accntid>', methods=['GET'])
def get_bill_pg(accntid:int):

    # Load the BillAccount along with related BillType and Parent BillType in one query
    bill_account = db.session.query(BillAccounts)\
        .options(
            joinedload(BillAccounts.bill_type).joinedload(BillType.parent)
        )\
        .filter(BillAccounts.id == accntid, BillAccounts.deleted_at.is_(None))\
        .first()
    

    user_id = bill_account.user_id

    billaccounts = {
        "name": bill_account.name,
        "payor":bill_account.payor,
        "bill_type": {
            "value":None,
            "label":None
        },
        "next_due_date_word": convertDateTostring(bill_account.next_due_date),
        "next_due_date": convertDateTostring(bill_account.next_due_date, '%Y-%m-%d'),
        "default_amount": round(bill_account.default_amount or 0, 2),
        "current_amount": round(bill_account.current_amount or 0, 2),
        "reminder_days": None,
        "repeat_frequency": None,
        "note":bill_account.note,
        'created_at':convertDateTostring(bill_account.created_at,'%d %b, %Y %H:%M'),
        'updated_at':convertDateTostring(bill_account.updated_at,'%d %b, %Y %H:%M')
    }

    bill_type = bill_account.bill_type
    if bill_type:    
        billaccounts['bill_type']['value'] = bill_type.id
        billaccounts['bill_type']['label'] = bill_type.name
    

    key_to_search = 'value'
    value_to_search = bill_account.repeat_frequency
    matching_dicts = next((dictionary for dictionary in RepeatFrequency if dictionary.get(key_to_search) == value_to_search),None)    

    if matching_dicts:
    
        billaccounts['repeat_frequency'] = {
            'value':value_to_search,
            'label':matching_dicts['label']
        }    


    key_to_search = 'value'
    value_to_search = bill_account.reminder_days
    matching_dicts = next((dictionary for dictionary in ReminderDays if dictionary.get(key_to_search) == value_to_search),None)    
    if matching_dicts:
        billaccounts['reminder_days'] = {
            'value':value_to_search,
            'label':matching_dicts['label']
        }

    
    
    
    
    bill_types = bill_type_dropdown_pg(user_id,1)



    return jsonify({
        "billaccounts":billaccounts,        
        "repeat_frequency":RepeatFrequency,
        "reminder_days":ReminderDays,
        "bill_types":bill_types,
        "current_balance":billaccounts['current_amount']
    })





@app.route('/api/delete-billpg', methods=['POST'])
def delete_bill_pg():
    if request.method == 'POST':
        data = json.loads(request.data)

        bill_account_id = data['id']
        key = data['key']
        action = 'Deleted' if key < 2 else 'Closed'
        field = 'deleted_at' if key < 2 else 'closed_at'

        admin_id = data['admin_id']

        message = None
        error = 0
        deleted_done = 0

        try:
            # Get the bill account object by ID
            bill_account = BillAccounts.query.filter_by(id=bill_account_id).first()

            if not bill_account:
                message = f'Bill account {action} Failed: Account not found'
                error = 1
                deleted_done = 0
            else:
                # Update the appropriate field based on the 'key'
                setattr(bill_account, field, datetime.now())               
                setattr(bill_account,'admin_id',admin_id)
                #bill_account.calender_at = None
                result = calender_data.delete_one({'module_id': 'bill', 'data.data_id': bill_account_id} )                  
               
                db.session.commit()  # Commit the changes to the database
                message = f'Bill account {action} Successfully'
                deleted_done = 1
               

        except Exception as ex:
            print('Bill account Save Exception: ', ex)
            message = f'Bill account {action} Failed'
            error = 1
            deleted_done = 0
            db.session.rollback()  # Rollback the transaction in case of error

        return jsonify({
            "bill_account_id": bill_account_id if bill_account else None,
            "message": message,
            "error": error,
            "deleted_done": deleted_done
        })
