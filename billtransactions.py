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
from decimal import Decimal
from billextra import extra_type
client = myclient
bill_accounts = my_col('bill_accounts')
bill_transactions = my_col('bill_transactions')


@app.route("/api/save-bill-transaction", methods=['POST'])
def save_bill_transactions():

    if request.method == 'POST':
        data = json.loads(request.data)
        bill_account_id = ObjectId(data['bill']['value'])
        user_id = ObjectId(data["user_id"])
        bill_trans_id = None
        message = ''
        result = 0

        current_amount = 0

        bill_acc_query = {
            "_id" :bill_account_id
        }

        previous_bill_acc = bill_accounts.find_one(bill_acc_query)
        if previous_bill_acc !=None:
            current_amount = previous_bill_acc['current_amount']


        with client.start_session() as session:
            with session.start_transaction():
                try:

                    amount = float(data.get("amount", 0))
                    due_date = convertStringTodate(data['due_date'])
                    op_type = data['type']['value']

                    current_amount = current_amount - amount if op_type > 1 else current_amount + amount 

                    bill_trans_data = bill_transactions.insert_one({                           
                        'amount':amount, 
                        'type':op_type,                       
                        'due_date':due_date,                                                                              
                        "created_at":datetime.now(),
                        "updated_at":datetime.now(),                        
                        "user_id":user_id,
                        "bill_acc_id":bill_account_id,
                        "payment_status":0,
                        "deleted_at":None,
                        "closed_at":None
                    },session=session)

                    bill_trans_id = str(bill_trans_data.inserted_id)

                    newvalues = { "$set": {  
                        'current_amount':current_amount,                            
                        'latest_transaction_id':ObjectId(bill_trans_id),                                     
                        "updated_at":datetime.now()
                    } }
                    bill_account_data = bill_accounts.update_one(bill_acc_query,newvalues,session=session)

                    result = 1 if bill_account_id!=None and bill_trans_id!=None and bill_account_data.modified_count else 0
                    if result:
                        bill_account_id = str(bill_account_id)
                        session.commit_transaction()
                        message = 'Bill Transaction Succefull'
                    else:
                        bill_account_id = None
                        bill_trans_id = None
                        session.abort_transaction()
                        message = 'Bill Transaction Failed!'

                except Exception as ex:
                    print('BILL EXP: ',ex)
                    bill_account_id = None
                    bill_trans_id = None
                    result = 0
                    message = 'Bill Transaction Failed!'
                    session.abort_transaction()



        return jsonify({
                    "bill_account_id":bill_account_id,
                    "bill_trans_id":bill_trans_id,
                    "message":message,
                    "result":result
                })
    



@app.route('/api/bill-extras/<string:bill_id>', methods=['POST'])
def list_extras(bill_id:str):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    #global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])

    # Construct MongoDB filter query
    query = {
        #'role':{'$gte':10}
        "bill_acc_id":ObjectId(bill_id),
        "deleted_at":None
    }
    # if global_filter:

    #     pattern_str = r'^\d{4}-\d{2}-\d{2}$'
    #     pay_date_extra = None        
    #     #try:
    #     if re.match(pattern_str, global_filter):
    #         pay_date_extra = datetime.strptime(global_filter,"%Y-%m-%d")            
    #     #except ValueError:
    #     else:
    #         pay_date_extra = None

        

    #     query["$or"] = [
            
    #         {"due_date":pay_date_extra},
    #         {"amount": {"$regex": global_filter, "$options": "i"}},            
                           
    #         # Add other fields here if needed
    #     ]

    # Construct MongoDB sort parameters
    sort_params = [
        ('created_at',-1)
    ]
    for sort in sort_by:
        sort_field = sort['id']
        sort_direction = -1 if sort['desc'] else 1
        sort_params.append((sort_field, sort_direction))

    # Fetch data from MongoDB
    if sort_params:
        cursor = bill_transactions.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
    else:
        # Apply default sorting or skip sorting
        cursor = bill_transactions.find(query).skip(page_index * page_size).limit(page_size)

    total_count = bill_transactions.count_documents(query)
    #data_list = list(cursor)
    data_list = []



    for todo in cursor:
        #bill_ac = bill_accounts.find_one({'_id':todo['bill']['value']})
        
        #todo['billing_month_year'] = f"{todo['month']['label']}, {todo['year']['value']}"
        todo['due_date_word'] = todo['due_date'].strftime('%d %b, %Y') 
        todo['due_date'] = convertDateTostring(todo['due_date'],'%Y-%m-%d')

        key_to_search = 'value'
        value_to_search = int(todo['type'])
        matching_dicts = next((dictionary for dictionary in extra_type if dictionary.get(key_to_search) == value_to_search),None)
        todo['type'] =  matching_dicts['label']
        data_list.append(todo)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size


    

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count,
        
    })



