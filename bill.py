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

# repeat_count = [
#     {'value':0, 'label':'None'},
#     {'value':1, 'label':'1'},
#     {'value':2, 'label':'2'},
#     {'value':3, 'label':'3'},
#     {'value':4, 'label':'4'},
#     {'value':5, 'label':'5'},
#     {'value':6, 'label':'6'},
#     {'value':7, 'label':'7'},
#     {'value':8, 'label':'8'},
#     {'value':9, 'label':'9'},
#     {'value':10, 'label':'10'},
#     {'value':11, 'label':'11'},
#     {'value':12, 'label':'12'},

# ]

""" repeat_frequency = [
    {'value':0, 'label':'None'},
    {'value':1, 'label':'Week(s)'},
    {'value':2, 'label':'Month(s)'},
    {'value':3, 'label':'Year(s)'},    

] """

repeat_frequency = [
        {'value':0, 'label':'None'},
        {'label':'Daily','value':1},
        {'label':'Weekly','value':7},
        {'label':'BiWeekly','value':14},
        {'label':'Monthly','value':30},
        {'label': 'Quarterly', 'value': 90},
        {'label':'Annually','value':365}           
]

reminder_days = [
    {'value':0, 'label':'Disabled'},
    {'value':1, 'label':'1 days before'},
    {'value':2, 'label':'2 days before'},
    {'value':3, 'label':'3 days before'},
    {'value':4, 'label':'4 days before'},
    {'value':5, 'label':'5 days before'},
    {'value':6, 'label':'6 days before'},
    {'value':7, 'label':'7 days before'},
    {'value':8, 'label':'8 days before'},
    {'value':9, 'label':'9 days before'},
    {'value':10, 'label':'10 days before'},    

]



@app.route('/api/bill-summary/<string:accntid>', methods=['GET'])
def get_bill_summary(accntid:str):

    sort_params = [
    ('due_date',-1),
    ('updated_at',-1)
    ]

    billaccounts = bill_accounts.find_one(
        {"_id":ObjectId(accntid)},
        {
        "_id":0,
        'user_id':0,
        'latest_transaction_id':0        
        }        
        )

    query = {
        #'role':{'$gte':10}
        "bill_acc_id":ObjectId(accntid),
        "deleted_at":None
    }

    sort_params = [
    ('due_date',-1),
    ('updated_at',-1)
    ]
    page_size = 6

    cursor = bill_transactions.find(query,{
        '_id':0,
        'amount':1
        }).sort(sort_params).limit(page_size)

    monthTransaction = list(cursor)

    return jsonify({
        "currentBalance":billaccounts['current_amount'],
        "monthTransaction":monthTransaction,        
    })

@app.route('/api/billutils',methods=['GET'])
def get_bill_utils():

    return jsonify({        
        # "repeat_count":repeat_count,
        "repeat_frequency":repeat_frequency,
        "reminder_days":reminder_days
    })


@app.route('/api/bill/<string:accntid>', methods=['GET'])
def get_bill(accntid:str):

    billaccounts = bill_accounts.find_one(
        {"_id":ObjectId(accntid)},
        {"_id":0,'user_id':0,'latest_transaction_id':0}
        )
    
    bill_type = my_col('bill_type').find_one(
        {"_id":billaccounts['bill_type']['value']},
        {"_id":0,"name":1}
        )
    
    if bill_type!=None:    
        billaccounts['bill_type']['value'] = str(billaccounts['bill_type']['value'])
        billaccounts['bill_type']['label'] = bill_type['name']
    else:
        billaccounts['bill_type'] = None
    billaccounts['next_due_date'] = billaccounts['next_due_date'].strftime('%Y-%m-%d')

    """ key_to_search = 'value'
    value_to_search = int(billaccounts['repeat_count'])
    matching_dicts = next((dictionary for dictionary in repeat_count if dictionary.get(key_to_search) == value_to_search),None)    
    
    billaccounts['repeat_count'] = {
        'value':value_to_search,
        'label':matching_dicts['label']
    } """


    key_to_search = 'value'
    value_to_search = int(billaccounts['repeat_frequency'])
    matching_dicts = next((dictionary for dictionary in repeat_frequency if dictionary.get(key_to_search) == value_to_search),None)    
    
    billaccounts['repeat_frequency'] = {
        'value':value_to_search,
        'label':matching_dicts['label']
    }    


    key_to_search = 'value'
    value_to_search = int(billaccounts['reminder_days'])
    matching_dicts = next((dictionary for dictionary in reminder_days if dictionary.get(key_to_search) == value_to_search),None)    
    
    billaccounts['reminder_days'] = {
        'value':value_to_search,
        'label':matching_dicts['label']
    }
    


    return jsonify({
        "billaccounts":billaccounts,
        # "repeat_count":repeat_count,
        "repeat_frequency":repeat_frequency,
        "reminder_days":reminder_days
    })


@app.route('/api/bills/<string:user_id>', methods=['POST'])
def list_bills(user_id:str):

    action  = request.args.get('action', None)

    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])

    # Construct MongoDB filter query
    query = {
        #'role':{'$gte':10}
        "user_id":ObjectId(user_id),
        "deleted_at":None,
        "closed_at":None
    }

    if action!=None:
        query = {
            "user_id": ObjectId(user_id),
            "deleted_at": None,
            "$or": [                
                {"closed_at": {"$ne": None}},    # or closed_at is not None
                
            ]
        }
    
    

    if global_filter:

        #bill type filter
        billtype = my_col('bill_type').find(
                {'name':{"$regex":global_filter,"$options":"i"}},
                {'_id':1}
            )
        billtype_list = list(billtype)
        billtype_id_list = [d.pop('_id') for d in billtype_list]
        #end bill type filter

        #next_due_date = datetime.strptime(global_filter,"%Y-%m-%d")
        #print(next_due_date)        
        pattern_str = r'^\d{4}-\d{2}-\d{2}$'
        next_due_date = None
        #try:
        if re.match(pattern_str, global_filter):
            next_due_date = datetime.strptime(global_filter,"%Y-%m-%d")
        #except ValueError:
        else:
            next_due_date = None

        query["$or"] = [
            {"name": {"$regex": global_filter, "$options": "i"}},
            {"bill_type.value": {"$in":billtype_id_list}},
            {"next_due_date":next_due_date}            
            # Add other fields here if needed
        ]

    # Construct MongoDB sort parameters
    sort_params = []
    for sort in sort_by:
        sort_field = sort['id']
        sort_direction = -1 if sort['desc'] else 1
        sort_params.append((sort_field, sort_direction))

    # Fetch data from MongoDB
    if sort_params:
        cursor = bill_accounts.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
    else:
        # Apply default sorting or skip sorting
        cursor = bill_accounts.find(query).skip(page_index * page_size).limit(page_size)

    total_count = bill_accounts.count_documents(query)
    data_list = []
    for todo in cursor:
        bill_type_id = todo['bill_type']['value']
        bill_type = my_col('bill_type').find_one(
        {"_id":bill_type_id},
        {"_id":0,"name":1,"parent":1}
        )

        bill_type_parent = None

        if bill_type['parent']!=None:
            bill_type_parent = my_col('bill_type').find_one(
            {"_id":bill_type['parent']},
            {"_id":0,"name":1}
            )

        #print(bill_type_parent)


        key_to_search = 'value'
        value_to_search = int(todo['repeat_frequency'])
        matching_dicts = next((dictionary for dictionary in repeat_frequency if dictionary.get(key_to_search) == value_to_search),None)    
        
        todo['repeat_frequency'] = matching_dicts['label'] 


        todo['bill_type'] = bill_type["name"] if bill_type!=None else None
        todo["bill_type_parent"] = bill_type_parent["name"] if bill_type_parent!=None else None

        todo['next_due_date'] = convertDateTostring(todo["next_due_date"])

        # entry = {
        #     "_id":todo["_id"],
        #     "name":todo["name"],
        #     "payor":todo["payor"],
        #     "bill_type":bill_type["name"] if bill_type!=None else None,
        #     "bill_type_parent":bill_type_parent["name"] if bill_type_parent!=None else None,
        #     "default_amount":todo["default_amount"],
        #     "current_amount":todo["current_amount"],
        #     "next_due_date":convertDateTostring(todo["next_due_date"]),
            
        #     #"repeat":todo["repeat"],
        #     "repeat_frequency":todo['repeat_frequency']
            
        # }
        data_list.append(todo)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size
    

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count
    })



@app.route("/api/update-bill/<string:accntid>", methods=['POST'])
def update_bill_transaction(accntid:str):
    if request.method == 'POST':
        data = json.loads(request.data)
        bill_account_id = accntid
        bill_trans_id = data['id']
        message = ''
        result = 0

        with client.start_session() as session:
                with session.start_transaction():
                    try:

                        amount  = int(data['amount'])
                       
                        next_due_date = datetime.strptime(data['due_date'],"%Y-%m-%d")
                    
                        

                        bill_trans_query = {
                            '_id':ObjectId(bill_trans_id)
                        }

                        newvalues = { "$set": {   
                            'amount':amount,                        
                            'due_date':next_due_date,               
                                                                                 
                            "updated_at":datetime.now()
                        } }

                        bill_trans_data = bill_transactions.update_one(bill_trans_query,newvalues,session=session)

                        bill_query = {
                                'bill_acc_id':ObjectId(bill_account_id)
                            }

                        latest_transactions = bill_transactions.find_one(bill_query,
                                                                        sort=[
                                                                            ('due_date', -1),
                                                                            ('updated_at', -1),
                                                                            ],
                                                                        session=session)
                        
                        #latest_trans_id = str(latest_transactions['_id'])

                        #if latest_trans_id == bill_trans_id:

                        bill_acc_query = {
                                "_id" :ObjectId(bill_account_id)
                            }

                        newvalues = { "$set": {   
                                "latest_transaction_id":ObjectId(latest_transactions["_id"]),
                                "next_due_date":latest_transactions['due_date'],                                
                                'current_amount':latest_transactions['amount'],                                     
                                "updated_at":datetime.now()
                            } }
                        bill_account_data = bill_accounts.update_one(bill_acc_query,newvalues,session=session)

                        result = 1 if bill_trans_data.modified_count and bill_account_data.modified_count else 0
                        message = 'Bill updated Succefull' if bill_trans_data.modified_count and bill_account_data.modified_count else 'Bill update Failed!'

                        session.commit_transaction()
                    except Exception as ex:

                        print('BILL UPDATE EX: ',ex)

                        bill_trans_id = None
                        result = 0
                        message = 'Bill update Failed!'
                        session.abort_transaction()


                    return jsonify({
                        "bill_account_id":bill_account_id,
                        "bill_trans_id":bill_trans_id,
                        "message":message,
                        "result":result
                    })


@app.route("/api/save-bill/<string:accntid>", methods=['POST'])
def save_bill(accntid:str):
    if request.method == 'POST':
        data = json.loads(request.data)
        bill_account_id = accntid
        bill_trans_id = None
        message = ''
        result = 0

        

        with client.start_session() as session:
            with session.start_transaction():
                try:
                            amount  = int(data['amount'])
                            
                            next_due_date = datetime.strptime(data['due_date'],"%Y-%m-%d")

                            #save bill transactions
                            bill_trans_data = bill_transactions.insert_one({                           
                                'amount':amount,                        
                                'due_date':next_due_date,               
                                                                         
                                "created_at":datetime.now(),
                                "updated_at":datetime.now(),                        
                                "user_id":ObjectId(data["user_id"]),
                                "bill_acc_id":ObjectId(bill_account_id),                                
                                "payment_status":0,
                                "deleted_at":None
                            },session=session)

                            bill_trans_id = str(bill_trans_data.inserted_id)

                            bill_query = {
                                'bill_acc_id':ObjectId(bill_account_id)
                            }

                            latest_transactions = bill_transactions.find_one(bill_query,
                                                                            sort=[
                                                                                ('due_date', -1),
                                                                                ('updated_at', -1),
                                                                                ],
                                                                            session=session)
                            print('LATEST TRANSACTION: ',latest_transactions)

                            bill_acc_query = {
                                "_id" :ObjectId(bill_account_id)
                            }
                            newvalues = { "$set": {   
                                "latest_transaction_id":ObjectId(latest_transactions["_id"]),
                                "next_due_date":latest_transactions['due_date'],                                
                                'current_amount':latest_transactions['amount'],                                     
                                "updated_at":datetime.now()
                            } }
                            bill_account_data = bill_accounts.update_one(bill_acc_query,newvalues,session=session)


                            result = 1 if bill_trans_id!=None and bill_account_data.modified_count else 0
                            message = 'Bill added Succefull' if bill_trans_id!=None and bill_account_data.modified_count else 'Bill addition Failed!'
                            session.commit_transaction()
                except Exception as ex:

                    print('BILL SAVE EX: ',ex)

                    bill_trans_id = None
                    result = 0
                    message = 'Bill addition Failed!'
                    session.abort_transaction()


                return jsonify({
                    "bill_account_id":bill_account_id,
                    "bill_trans_id":bill_trans_id,
                    "message":message,
                    "result":result
                })


@app.route("/api/save-bill-account", methods=['POST'])
def save_bill_account():
    if request.method == 'POST':
        data = json.loads(request.data)
        bill_account_id = None
        bill_trans_id = None
        message = ''
        result = 0
        

        with client.start_session() as session:
            with session.start_transaction():

                try:

                    amount  = int(data['default_amount'])
                    
                    #repeat=int(data['repeat']) if 'repeat' in data else 0
                    # repeat_count = 0
                    repeat_frequency = int(data['repeat_frequency']['value'])
                    reminder_days = int(data['reminder_days']['value'])

                    next_due_date = convertStringTodate(data['next_due_date'])

                    op_type = extra_type[0]['value']
                    #create bill account
                    bill_acc_data = bill_accounts.insert_one({           
                        'name':data['name'],
                        'bill_type':{
                        'value':ObjectId(data['bill_type']['value'])
                        },
                        'payor':data['payor'] if 'payor' in  data else None,
                        'default_amount':amount,
                        'current_amount':amount, 
                        'paid_total':0,
                        'next_due_date':next_due_date,
                        #'repeat':repeat, 
                        # 'repeat_count':repeat_count,
                        'repeat_frequency':repeat_frequency, 
                        'reminder_days':reminder_days,                         
                        'note':data['note'] if 'note' in data else None,                          
                        "created_at":datetime.now(),
                        "updated_at":datetime.now(),                        
                        "user_id":ObjectId(data["user_id"]),
                        "latest_transaction_id":None,
                        "deleted_at":None,
                        "closed_at":None
                    },session=session)

                    bill_account_id = str(bill_acc_data.inserted_id)

                    #print(bill_account_id)
                    #save bill transaction defaults
                    bill_trans_data = bill_transactions.insert_one({                           
                        'amount':amount,
                        'type':op_type,
                        'payor':None,
                        'note':None,
                        'current_amount':amount,                        
                        'due_date':next_due_date,                                                                              
                        "created_at":datetime.now(),
                        "updated_at":datetime.now(),                        
                        "user_id":ObjectId(data["user_id"]),
                        "bill_acc_id":ObjectId(bill_account_id),
                        "payment_status":0,
                        "deleted_at":None,
                        "closed_at":None
                    },session=session)

                    bill_trans_id = str(bill_trans_data.inserted_id)

                    bill_acc_query = {
                        "_id" :ObjectId(bill_account_id)
                    }
                    newvalues = { "$set": {                                   
                        'latest_transaction_id':ObjectId(bill_trans_id),                                     
                        "updated_at":datetime.now()
                    } }
                    bill_account_data = bill_accounts.update_one(bill_acc_query,newvalues,session=session)


                    result = 1 if bill_account_id!=None and bill_trans_id!=None and bill_account_data.modified_count else 0
                    message = 'Bill account added Succefull' if bill_account_id!=None and bill_trans_id!=None and bill_account_data.modified_count else 'Bill account addition Failed!'
                    session.commit_transaction()
                except Exception as ex:
                    print('BILL EXP: ',ex)
                    bill_account_id = None
                    bill_trans_id = None
                    result = 0
                    message = 'Bill account addition Failed!'
                    session.abort_transaction()


                return jsonify({
                    "bill_account_id":bill_account_id,
                    "bill_trans_id":bill_trans_id,
                    "message":message,
                    "result":result
                })




@app.route("/api/update-bill-account/<string:accntid>", methods=['POST'])
def update_bill(accntid:str):
    if request.method == 'POST':
        data = json.loads(request.data)
        bill_account_id = accntid
        message = ''
        result = 0

        try:

            bill_acc_query = {
                        "_id" :ObjectId(bill_account_id)
                    }
            amount  = int(data['default_amount'])
            
            #repeat=int(data['repeat']) if 'repeat' in data else 0
            # repeat_count = int(data['repeat_count']['value'])
            repeat_frequency = int(data['repeat_frequency']['value'])
            reminder_days = int(data['reminder_days']['value'])
            newvalues = { "$set": {
                'name':data['name'],
                'bill_type':{
                    'value':ObjectId(data['bill_type']['value'])
                },
                'payor':data['payor'] if 'payor' in  data else None,                    
                'default_amount':amount,                            
                #'repeat':repeat, 
                # 'repeat_count':repeat_count,
                'repeat_frequency':repeat_frequency, 
                'reminder_days':reminder_days, 
                
                'note':data['note'] if 'note' in data and data['note']!=""  else None,                                     
                "updated_at":datetime.now()
            } }
            bill_account_data = bill_accounts.update_one(bill_acc_query,newvalues)


            result = 1 if bill_account_data.modified_count else 0
            message = 'Bill account updated Succefull' if bill_account_data.modified_count else 'Bill account update Failed!'

        except Exception as ex:

            print('BILL UPDATE EX: ',ex)

            bill_account_id = None            
            result = 0
            message = 'Bill account update Failed!'


        return jsonify({
            "bill_account_id":bill_account_id,            
            "message":message,
            "result":result
        })    



@app.route('/api/delete-bill', methods=['POST'])
def delete_bill():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']
        key = data['key']
        action = 'Deleted' if key < 2 else 'Closed'
        field = 'deleted_at' if key < 2 else 'closed_at'

        bill_account_id = None
        message = None
        error = 0
        deleted_done = 0

        try:
            myquery = { "_id" :ObjectId(id)}

            newvalues = { "$set": {                                     
                            field:datetime.now()                
                        } }
            bill_account_data =  bill_accounts.update_one(myquery, newvalues)
            bill_account_id = id if bill_account_data.modified_count else None
            error = 0 if bill_account_data.modified_count else 1
            deleted_done = 1 if bill_account_data.modified_count else 0
            if deleted_done:
                message = f'Bill account {action} Successfully'
                
            else:
                message = f'Bill account {action} Failed' 

        except Exception as ex:
            bill_account_id = None
            print('Bill account Save Exception: ',ex)
            message = f'Bill account {action} Failed' 
            error  = 1
            deleted_done = 0
        
        return jsonify({
            "bill_account_id":bill_account_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })

@app.route("/api/delete-bill-transaction/<string:accntid>", methods=['POST'])
def delete_bill_transaction(accntid:str):
    if request.method == 'POST':
        data = json.loads(request.data)
        bill_account_id = accntid
        bill_trans_id = data['id']
        message = None
        error = 0
        deleted_done = 0

        with client.start_session() as session:
                with session.start_transaction():
                    try:                       
                    
                        

                        bill_trans_query = {
                            '_id':ObjectId(bill_trans_id)
                        }

                        newvalues = { "$set": {                                                                                 
                            "deleted_at":datetime.now()
                        } }

                        bill_trans_data = bill_transactions.update_one(bill_trans_query,newvalues,session=session)

                        bill_query = {
                                'bill_acc_id':ObjectId(bill_account_id)
                            }

                        latest_transactions = bill_transactions.find_one(bill_query,
                                                                        sort=[
                                                                            ('due_date', -1),
                                                                            ('updated_at', -1),
                                                                            ],
                                                                        session=session)
                                               

                        bill_acc_query = {
                                "_id" :ObjectId(bill_account_id)
                            }

                        newvalues = { "$set": {   
                                "latest_transaction_id":ObjectId(latest_transactions["_id"]),
                                "next_due_date":latest_transactions['due_date'],                                
                                'current_amount':latest_transactions['amount'],                                     
                                "updated_at":datetime.now()
                            } }
                        bill_account_data = bill_accounts.update_one(bill_acc_query,newvalues,session=session)

                        bill_pay_query = {
                                "bill_trans_id" :ObjectId(bill_trans_id)
                        }

                        bill_payment_cursor = bill_payment.find(bill_pay_query,{'_id':1})
                        bill_payment_ids = [ObjectId(doc['_id']) for doc in bill_payment_cursor]

                        if len(bill_payment_ids) > 0:
                            bill_payment.update_many({
                                "_id": { "$in": bill_payment_ids } }, 
                                { 
                                    "$set": { "deleted_at" : datetime.now() } 
                                },
                                session=session 
                                )


                        error = 0 if bill_trans_data.modified_count and bill_account_data.modified_count else 1
                        deleted_done = 1 if bill_trans_data.modified_count and bill_account_data.modified_count else 0
                        message = 'Bill delete Succefully' if bill_trans_data.modified_count and bill_account_data.modified_count else 'Bill deletion Failed!'

                        session.commit_transaction()
                    except Exception as ex:

                        print('BILL UPDATE EX: ',ex)

                        bill_trans_id = None
                        deleted_done = 0
                        message = 'Bill deletion Failed!'
                        session.abort_transaction()


                    return jsonify({
                        "bill_account_id":bill_account_id,
                        "message":message,
                        "error":error,
                        "deleted_done":deleted_done
                    })





bill_types_collection = my_col('bill_type')
@app.route('/api/bill-typewise-info', methods=['GET'])
def get_typewise_bill_info():
    # Fetch the bill type cursor
    bill_type_cursor = bill_types_collection.find(
        {"deleted_at": None},
        {'_id': 1, 'name': 1, 'parent': 1}
    )

    # Create a list of _id values
    billtype_id_list = [item['_id'] for item in bill_type_cursor]

    pipeline = [
        # Step 1: Match documents with bill_type.value in billtype_id_list
        {
            "$match": {
                "bill_type.value": {"$in": billtype_id_list},
                "deleted_at": None,
                "closed_at":None
            }
        },

        # Step 2: Lookup to join bill_type collection to get the name (label)
        {
            "$lookup": {
                "from": "bill_type",                # The collection to join
                "localField": "bill_type.value",    # Field from the current collection
                "foreignField": "_id",              # Field from the bill_type collection
                "as": "bill_info"                   # Resulting array field for joined data
            }
        },

        # Step 3: Unwind the bill_info array to flatten it
        {"$unwind": "$bill_info"},

        # Step 4: Group by bill_type.value and count occurrences, include bill_type name
        {
            "$group": {
                "_id": "$bill_type.value",          # Group by bill_type.value
                "count": {"$sum": 1},               # Count occurrences per bill type
                "balance": {"$sum": "$current_amount"},  # Sum balance and monthly_interest
                "name": {"$first": "$bill_info.name"}  # Get the first name (label)
            }
        },

        # Step 5: Calculate the total count and total balance by summing up all the individual counts and balances
        {
            "$group": {
                "_id": None,                        # No specific grouping field, aggregate the entire collection
                "total_count": {"$sum": "$count"},  # Sum all the 'count' values from the grouped results
                "total_balance": {"$sum": "$balance"},  # Sum the already calculated balance (which includes balance and monthly_interest)
                "grouped_results": {"$push": "$$ROOT"}  # Preserve all grouped results in an array
            }
        },

        # Step 6: Use $project to format the output
        {
            "$project": {
                "_id": 0,                           # Remove the _id field
                "total_count": 1,                   # Include the total count
                "total_balance": 1,                 # Include the total balance
                "grouped_results": 1                # Include the grouped results
            }
        }
    ]


    # Perform the aggregation
    bill_type_bill_all = list(bill_accounts.aggregate(pipeline))

    bill_type_bill_counts = bill_type_bill_all[0]['grouped_results'] if bill_type_bill_all else []
    total_dept_type = bill_type_bill_all[0]['total_count'] if bill_type_bill_all else 0
    total_balance = bill_type_bill_all[0]['total_balance'] if bill_type_bill_all else 0
    if len(bill_type_bill_counts) > 0:
        data_json = MongoJSONEncoder().encode(bill_type_bill_counts)
        bill_type_bill_counts = json.loads(data_json)

     # Fetch bill type names
    bill_types = bill_types_collection.find({'_id': {'$in': billtype_id_list}})    
    bill_type_names = {str(d['_id']): d['name'] for d in bill_types}
    #print(bill_type_names)

    return jsonify({
        "payLoads":{            
            "bill_type_bill_counts":bill_type_bill_counts,
            "total_dept_type":total_dept_type,
            "total_balance":total_balance,
            "bill_type_names":bill_type_names            
        }        
    })






@app.route('/api/bill-all/<string:accntid>', methods=['GET'])
def get_bill_all(accntid:str):
    
    billaccounts = bill_accounts.find_one(
        {"_id":ObjectId(accntid)},
        {
        "_id":0,
        'user_id':0,
        'latest_transaction_id':0        
        }        
        )
    
    bill_type = my_col('bill_type').find_one(
        {"_id":billaccounts['bill_type']['value']},
        {"_id":0,"name":1,"parent":1}
        )
    
    bill_type_parent = None

    if bill_type['parent']!=None:
        bill_type_parent = my_col('bill_type').find_one(
        {"_id":bill_type['parent']},
        {"_id":0,"name":1}
        )
    
    billaccounts['bill_type_parent'] = bill_type_parent['name'] if bill_type_parent!=None else None
    
    #billaccounts['bill_type']['value'] = str(billaccounts['bill_type']['value'])
    #billaccounts['bill_type']['label'] = bill_type['name']
    billaccounts['bill_type'] = bill_type['name']
    billaccounts['next_due_date_word'] = convertDateTostring(billaccounts['next_due_date'])
    billaccounts['next_due_date'] = convertDateTostring(billaccounts['next_due_date'],'%Y-%m-%d')    
        

    billaccounts['default_amount'] = round(billaccounts['default_amount'],2)
    billaccounts['current_amount'] = round(billaccounts['current_amount'],2)
    

    key_to_search = 'value'
    value_to_search = int(billaccounts['reminder_days'])
    matching_dicts = next((dictionary for dictionary in reminder_days if dictionary.get(key_to_search) == value_to_search),None)    
    
    # billaccounts['reminder_days'] = {
    #     'value':value_to_search,
    #     'label':matching_dicts['label']
    # }

    billaccounts['reminder_days'] = matching_dicts['label']

    
    # billaccounts['repeat'] = 'Yes'  if billaccounts['repeat'] > 0 else 'No'


    key_to_search = 'value'
    value_to_search = int(billaccounts['repeat_frequency'])
    matching_dicts = next((dictionary for dictionary in repeat_frequency if dictionary.get(key_to_search) == value_to_search),None)    
    
    billaccounts['repeat_frequency'] = matching_dicts['label']    

    twelve_months_ago = datetime.now() - timedelta(days=365)

    query = {
        #'role':{'$gte':10}
        "bill_account_id":ObjectId(accntid),
        "pay_date": {"$gte": twelve_months_ago},
        "deleted_at":None
    }
    cursor = bill_payment.find(query,{
        '_id':0,
        'pay_date':1,        
        'amount':1,        
    })

    data_list = []
    for todo in cursor:
        #print(todo)
        

        #todo['billing_month_year'] = f"{todo['month']}, {todo['year']}"
        todo['pay_date_word'] = todo['pay_date'].strftime('%d %b, %Y')
        todo['pay_date'] = todo['pay_date'].strftime('%Y-%m-%d')        
        todo['amount'] = round(todo['amount'],2)              
        data_list.append(todo)

    #total_count = bill_payments.count_documents(query)
    #data_list = list(cursor)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    #print(data_obj)
    

    return jsonify({
        "payLoads":{
            "billaccounts":billaccounts,
            "billpayments":data_obj,                           
        }        
    })