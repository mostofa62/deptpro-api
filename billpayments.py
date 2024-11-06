import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from app import app
from db import my_col,myclient
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta
from billextra import extra_type


client = myclient
bill_accounts = my_col('bill_accounts')
bill_transactions = my_col('bill_transactions')
bill_payment = my_col('bill_payment')

@app.route('/api/bill-trans/<string:accntid>', methods=['POST'])
def get_bill_trans(accntid:str):

    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)    

    op_type = extra_type[0]['value']

    query = {
        #'role':{'$gte':10}
        "bill_acc_id":ObjectId(accntid),
        'type':op_type,
        "deleted_at":None
    }

    sort_params = [
    #('due_date',-1),
    ('created_at',-1)
    ]

    cursor = bill_transactions.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
    data_list = []
    
    for todo in cursor:
        #print(todo)
        todo['due_date_word'] = todo['due_date'].strftime('%B %d, %Y')
        todo['due_date'] = todo['due_date'].strftime('%Y-%m-%d')
        print(todo['_id'])

        payments = []
        bill_payment_data = bill_payment.find({
            'bill_trans_id':todo['_id'],            
            'deleted_at':None
            }).sort([
           ('pay_date',-1) 
        ])
        for pay in bill_payment_data:
            pay['pay_date_word'] = pay['pay_date'].strftime('%B %d, %Y')
            pay['pay_date'] = pay['pay_date'].strftime('%Y-%m-%d')
            payments.append(pay)


        todo['payments'] = payments        
        data_list.append(todo)

    total_count = bill_transactions.count_documents(query)
    #data_list = list(cursor)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count
    })



#payment
@app.route("/api/pay-bill/<string:accntid>", methods=['POST'])
def pay_bill_transaction(accntid:str):
    if request.method == 'POST':
        data = json.loads(request.data)
        bill_trans_id = data['trans_id']
        bill_account_id = accntid
        trans_payment_id = None
        message = ''
        result = 0
        

        

        with client.start_session() as session:
            with session.start_transaction():
                try:
                    amount  = float(data['amount'])
                    pay_date =  convertStringTodate(data['pay_date'])
                    trans_payment_data = bill_payment.insert_one({                           
                        'amount':amount,                        
                        'pay_date':pay_date,                                                                              
                        "created_at":datetime.now(),
                        "updated_at":datetime.now(),                        
                        "bill_trans_id":ObjectId(bill_trans_id),
                        "bill_account_id":ObjectId(bill_account_id),                        
                        "deleted_at":None
                    },session=session)

                    trans_payment_id = str(trans_payment_data.inserted_id)

                    bill_trans_query = {
                        '_id':ObjectId(bill_trans_id)
                    }

                    bill_transactions_row = bill_transactions.find_one(bill_trans_query,
                                                                        {'_id':0,'amount':1,'bill_acc_id':1,'current_amount':1},
                                                                    session=session)
                    
                    #check previous 
                    previous_amount  = float(bill_transactions_row['amount'])

                    current_trans_amount = float(bill_transactions_row['current_amount'])

                    #payment_status =  0 if amount < previous_amount else 1

                    
                    current_trans_amount -= amount

                    payment_status =  1 if current_trans_amount <= 0  else 0
                    
                    

                    #bill_account_id = str(bill_transactions_row['bill_acc_id'])

                    newvalues = { "$set": {  
                        'current_amount': current_trans_amount,
                        "payment_status":payment_status,
                        "latest_payment_id":ObjectId(trans_payment_id),                                                       
                        #"updated_at":datetime.now()
                    } }
                    bill_transactions_data = bill_transactions.update_one(bill_trans_query,newvalues,session=session)

                    ####
                    ## bill account balance
                    
                    bill_acc_query = {
                        "_id" :ObjectId(bill_account_id)
                    }

                    bill_account_row = bill_accounts.find_one(bill_acc_query, session=session)
                    ## current amount or balance
                    current_amount = bill_account_row['current_amount']

                    # reduce current amount from paid amount
                    current_amount = abs(current_amount - amount)

                    newvalues = { "$set": {   
                        "current_amount":current_amount,                                                            
                        "updated_at":datetime.now()
                    } }
                    bill_account_data = bill_accounts.update_one(bill_acc_query,newvalues,session=session)
                    ### end bill account update

                    result = 1 if trans_payment_id!=None and bill_account_data.modified_count and bill_transactions_data.modified_count else 0
                    message = 'Bill payment Succefull' if trans_payment_id!=None and bill_account_data.modified_count and bill_transactions_data.modified_count else 'Bill payment Failed!'
                    session.commit_transaction()

                except Exception as ex:

                    print('BILL SAVE PAYMENT ERROR: ',ex)

                    bill_account_id = None
                    trans_payment_id = None
                    result = 0
                    message = 'Bill payment Failed!'
                    session.abort_transaction()

                print(message, result, bill_account_id, bill_trans_id, trans_payment_id)
                return jsonify({
                    "bill_account_id":bill_account_id,
                    "bill_trans_id":bill_trans_id,
                    "trans_payment_id":trans_payment_id,
                    "message":message,
                    "result":result
                })

