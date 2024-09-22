import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from app import app
from db import my_col,myclient,mydb
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal

client = myclient
debt_transactions = my_col('debt_transactions')
debt_accounts = my_col('debt_accounts')
usersetting = my_col('user_settings')

payoff_order = [
    {'value':0, 'label':'0'},
    {'value':1, 'label':'1'}    

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

transaction_type = [
    {'value':0, 'label':'None'},
    {'value':1, 'label':'Payment'},
    {'value':2, 'label':'Purchase'}    

]

transaction_month = [
    {'value': i, 'label': month}
    for i, month in enumerate([
        'January', 'February', 'March', 'April', 'May', 'June', 
        'July', 'August', 'September', 'October', 'November', 'December'
    ], start=1)
]

current_year = datetime.now().year - 1
years_range = 12

transaction_year = [
    {'value': year, 'label': str(year)}
    for year in range(current_year, current_year + years_range + 1)
]


def newEntryOptionData(data_obj:any, collectionName:str, user_id:str):

    

    if data_obj == None:
        return data_obj

    if '__isNew__' in data_obj:
        collecObj =  my_col(collectionName).insert_one({
            'name':data_obj['label'],
            'parent':None,
            'deleted_at':None,
            'user_id':ObjectId(user_id)
        })

        if collecObj.inserted_id != None:
            return {'value': collecObj.inserted_id}
    else:

        if data_obj['value'] == '':
            return None        
        else:
            return {'value': ObjectId(data_obj['value'])}

#debt transaction summary

@app.route("/api/delete-debt-transaction/<string:accntid>", methods=['POST'])
def delete_debt_transaction(accntid:str):
    if request.method == 'POST':
        data = json.loads(request.data)
        debt_account_id = accntid
        debt_trans_id = data['id']
        message = None
        error = 0
        deleted_done = 0

        with client.start_session() as session:
                with session.start_transaction():
                    try:                       
                                        
                        debt_trans_query = {
                            '_id':ObjectId(debt_trans_id)
                        }

                        newvalues = { "$set": {                                                                                 
                            "deleted_at":datetime.now()
                        } }

                        debt_trans_data = debt_transactions.update_one(debt_trans_query,newvalues,session=session)
                        
                        debttransactions = debt_transactions.find_one(
                        debt_trans_query,
                        {
                        'amount':1,
                        'type':1                                                    
                        },
                        session=session        
                        )

                        amount  = float(debttransactions['amount'])
                        type = int(debttransactions['type'])                                               

                        debt_acc_query = {
                            "_id" :ObjectId(debt_account_id)
                        }
                        debtaccounts = debt_accounts.find_one(
                        debt_acc_query,
                        {
                        'balance':1,
                        'highest_balance':1                    
                                
                        },
                        session=session        
                        )
                        previous_balance = debtaccounts['balance']
                        new_balance = float(float(previous_balance) - float(amount)) if type > 1 else float(float(previous_balance) + float(amount))

                        newvalues = { "$set": {                                  
                                "balance":new_balance,                                                                                                     
                                "updated_at":datetime.now()
                            } }
                        debt_account_data = debt_accounts.update_one(debt_acc_query,newvalues,session=session)

                        
                        error = 0 if debt_trans_data.modified_count and debt_account_data.modified_count else 1
                        deleted_done = 1 if debt_trans_data.modified_count and debt_account_data.modified_count else 0
                        message = 'Debt delete Succefully' if debt_trans_data.modified_count and debt_account_data.modified_count else 'Debt deletion Failed!'

                        session.commit_transaction()
                    except Exception as ex:

                        print('DEBT UPDATE EX: ',ex)

                        debt_trans_id = None
                        deleted_done = 0
                        message = 'Debt deletion Failed!'
                        session.abort_transaction()


                    return jsonify({
                        "debt_account_id":debt_account_id,
                        "message":message,
                        "error":error,
                        "deleted_done":deleted_done
                    })


@app.route('/api/debt-trans/<string:accntid>', methods=['POST'])
def get_debt_trans(accntid:str):

    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    #global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])

    query = {
        #'role':{'$gte':10}
        "debt_acc_id":ObjectId(accntid),
        "deleted_at":None
    }

    # Construct MongoDB sort parameters
    sort_params = [('updated_at',-1)]
    for sort in sort_by:
        sort_field = sort['id']
        sort_direction = -1 if sort['desc'] else 1
        sort_params.append((sort_field, sort_direction))

    # Fetch data from MongoDB
    if sort_params:
        cursor = debt_transactions.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
    else:
        # Apply default sorting or skip sorting
        cursor = debt_transactions.find(query).skip(page_index * page_size).limit(page_size)

    
    data_list = []
    for todo in cursor:
        #print(todo)
        key_to_search = 'value'
        value_to_search = int(todo['type'])
        matching_dicts = next((dictionary for dictionary in transaction_type if dictionary.get(key_to_search) == value_to_search),None)            
        todo['type'] = matching_dicts['label']

        key_to_search = 'value'
        value_to_search = int(todo['month'])
        matching_dicts = next((dictionary for dictionary in transaction_month if dictionary.get(key_to_search) == value_to_search),None)            
        todo['month'] = matching_dicts['label']

        key_to_search = 'value'
        value_to_search = int(todo['year'])
        matching_dicts = next((dictionary for dictionary in transaction_year if dictionary.get(key_to_search) == value_to_search),None)            
        todo['year'] = matching_dicts['label']

        todo['billing_month_year'] = f"{todo['month']}, {todo['year']}"
        todo['trans_date'] = todo['trans_date'].strftime('%Y-%m-%d')
        todo['amount'] = round(todo['amount'],2)
        todo['previous_balance'] = round(todo['previous_balance'],2)
        todo['new_balance'] = round(todo['new_balance'],2)        
        data_list.append(todo)

    total_count = debt_transactions.count_documents(query)
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


@app.route('/api/debt-transaction-dropdown', methods=['GET'])
def get_debt_transaction_dropdown():

    
    

    return jsonify({
        "transaction_type":transaction_type,
        "transaction_month":transaction_month,
        "transaction_year":transaction_year        
    })



@app.route("/api/save-debt-transaction/<string:accntid>", methods=['POST'])
def save_debt_transaction(accntid:str):
    if request.method == 'POST':
        data = json.loads(request.data)
        debt_account_id = accntid
        debt_trans_id = None
        message = ''
        result = 0

        with client.start_session() as session:
            with session.start_transaction():

                try:

                    amount  = float(data['amount'])
                    autopay = int(data['autopay']) if 'autopay' in data else 0 
                    month = int(data['month']['value'])
                    year =  int(data['year']['value'])
                    type = int(data['type']['value'])                
                    trans_date = datetime.strptime(data['trans_date'],"%Y-%m-%d")

                    debt_acc_query = {
                        "_id" :ObjectId(debt_account_id)
                    }
                    #query previous debt balance to update
                    debtaccounts = debt_accounts.find_one(
                    debt_acc_query,
                    {
                    'balance':1,
                    'highest_balance':1                    
                               
                    },
                    session=session        
                    )
                    previous_balance = debtaccounts['balance']
                    new_balance = float(float(previous_balance) - float(amount)) if type > 1 else float(float(previous_balance) + float(amount))
                    #end previous debt balance to update

                    #print(debt_account_id)
                    #save debt transaction defaults
                    debt_trans_data = debt_transactions.insert_one({                           
                        'amount':amount,
                        'previous_balance':previous_balance,
                        'new_balance':new_balance,                       
                        'trans_date':trans_date,
                        'type':type,
                        'month':month,
                        'year':year,               
                        'autopay':autopay,                                         
                        "created_at":datetime.now(),
                        "updated_at":datetime.now(),                        
                        "user_id":ObjectId(data["user_id"]),
                        "debt_acc_id":ObjectId(debt_account_id),
                        "payment_status":0,
                        "deleted_at":None
                    },session=session)

                    debt_trans_id = str(debt_trans_data.inserted_id)

                    
                    
                    
                    newvalues = { "$set": {
                        "balance":new_balance,                                                                                                
                        "updated_at":datetime.now()
                    } }
                    debt_account_data = debt_accounts.update_one(debt_acc_query,newvalues,session=session)


                    result = 1 if debt_account_id!=None and debt_trans_id!=None and debt_account_data.modified_count else 0
                    message = 'Debt transaction added Succefull' if debt_account_id!=None and debt_trans_id!=None and debt_account_data.modified_count else 'Debt transaction addition Failed!'
                    session.commit_transaction()
                except Exception as ex:
                    print('DEBT EXP: ',ex)
                    debt_account_id = None
                    debt_trans_id = None
                    result = 0
                    message = 'Debt transaction addition Failed!'
                    session.abort_transaction()


                return jsonify({
                    "debt_account_id":debt_account_id,
                    "debt_trans_id":debt_trans_id,
                    "message":message,
                    "result":result
                })






#end debt transactions

@app.route('/api/delete-debt', methods=['POST'])
def delete_debt():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']

        debt_account_id = None
        message = None
        error = 0
        deleted_done = 0

        try:
            myquery = { "_id" :ObjectId(id)}

            newvalues = { "$set": {                                     
                "deleted_at":datetime.now()                
            } }
            debt_account_data =  debt_accounts.update_one(myquery, newvalues)
            debt_account_id = id if debt_account_data.modified_count else None
            error = 0 if debt_account_data.modified_count else 1
            deleted_done = 1 if debt_account_data.modified_count else 0
            message = 'Debt account Deleted Successfully'if debt_account_data.modified_count else 'Debt account Deletion Failed'

        except Exception as ex:
            debt_account_id = None
            print('Debt account Save Exception: ',ex)
            message = 'Debt account Deletion Failed'
            error  = 1
            deleted_done = 0
        
        return jsonify({
            "debt_account_id":debt_account_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })

debt_types_collection = my_col('debt_type')
@app.route('/api/debt-typewise-info', methods=['GET'])
def get_typewise_dept_info():


    

    # Fetch the debt type cursor
    debt_type_cursor = my_col('debt_type').find(
        {"deleted_at": None},
        {'_id': 1, 'name': 1, 'parent': 1}
    )
    
    # Create a list of _id values
    debttype_id_list = [item['_id'] for item in debt_type_cursor]
   

    pipeline = [
        # Step 1: Match documents with debt_type.value in debttype_id_list
        {
            "$match": {
                "debt_type.value": {"$in": debttype_id_list},
                "deleted_at": None
            }
        },

        # Step 2: Lookup to join debt_type collection to get the name (label)
        {
            "$lookup": {
                "from": "debt_type",                # The collection to join
                "localField": "debt_type.value",    # Field from the current collection
                "foreignField": "_id",              # Field from the debt_type collection
                "as": "debt_info"                   # Resulting array field for joined data
            }
        },

        # Step 3: Unwind the debt_info array to flatten it
        {"$unwind": "$debt_info"},

        # Step 4: Group by debt_type.value and count occurrences, include debt_type name
        {
            "$group": {
                "_id": "$debt_type.value",          # Group by debt_type.value
                "count": {"$sum": 1},               # Count occurrences per debt type
                "balance": {"$sum": {"$add": ["$balance", "$monthly_interest"]}},  # Sum balance and monthly_interest
                "name": {"$first": "$debt_info.name"}  # Get the first name (label)
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
    debt_type_debt_all = list(debt_accounts.aggregate(pipeline))

    debt_type_debt_counts = debt_type_debt_all[0]['grouped_results'] if debt_type_debt_all else []
    total_dept_type = debt_type_debt_all[0]['total_count'] if debt_type_debt_all else 0
    total_balance = debt_type_debt_all[0]['total_balance'] if debt_type_debt_all else 0
    if len(debt_type_debt_counts) > 0:
        data_json = MongoJSONEncoder().encode(debt_type_debt_counts)
        debt_type_debt_counts = json.loads(data_json)

    


    ## to find typewise account and there ammortization


    

    # Query to get debt accounts along with debt_type
    sort_params = [('due_date', 1)]
    deb_query = {
        "debt_type.value": {"$in": debttype_id_list},
        "deleted_at":None
    }
    debt_type_balances = {}

    # min_start_date_doc = debt_accounts.find_one(sort=[('start_date', 1)])
    
    # if min_start_date_doc:
    #     start_date = convertDateTostring(min_start_date_doc['start_date'],'%b %Y')
    # else:
    #     start_date = convertDateTostring(datetime.now(),'%b %Y')

    start_date = convertDateTostring(datetime.now(),'%b %Y')
    print('Minimum',start_date)

    
    debt_accounts_data = debt_accounts.find(deb_query, {'_id': 1, 'name': 1, 'debt_type': 1,'balance':1,'monthly_interest':1,'due_date':1}).sort(sort_params)

    # Fetch debt type names
    debt_types = debt_types_collection.find({'_id': {'$in': debttype_id_list}})    
    debt_type_names = {str(d['_id']): d['name'] for d in debt_types}
    #print(debt_type_names)

    # Initialize a dictionary to store the final result
    data = {}

    # Step 2: Iterate over each debt account and retrieve data from corresponding dynamic collections
    for account in debt_accounts_data:
        account_id = str(account['_id'])  # Convert ObjectId to string
        debt_type_id = str(account['debt_type']['value'])  # Get the debt type ID        
        dynamic_collection_name = f"debt_{account_id}"  # Dynamic collection name

        account_balance = float(account['balance']+account['monthly_interest'])
        print('balance',account_balance)

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

    # Print or return the final chart data
    #print("Final Chart Data:", chart_data)


    return jsonify({
        "payLoads":{            
            "debt_type_debt_counts":debt_type_debt_counts,
            "total_dept_type":total_dept_type,
            "total_balance":total_balance,
            "debt_type_ammortization":chart_data,
            #"debt_type_ammortization":normalized_data,
            "data":data,
            "debt_type_names":debt_type_names
        }        
    })


@app.route('/api/debt-all/<string:accntid>', methods=['GET'])
def get_dept_all(accntid:str):
    
    debtaccounts = debt_accounts.find_one(
        {"_id":ObjectId(accntid)},
        {
        "_id":0,
        'user_id':0,        
        }        
        )
    
    debt_type = my_col('debt_type').find_one(
        {"_id":debtaccounts['debt_type']['value']},
        {"_id":0,"name":1}
        )
    
    #debtaccounts['debt_type']['value'] = str(debtaccounts['debt_type']['value'])
    #debtaccounts['debt_type']['label'] = debt_type['name']
    debtaccounts['debt_type'] = debt_type['name']
    debtaccounts['due_date_word'] = debtaccounts['due_date'].strftime('%d %b, %Y')
    debtaccounts['due_date'] = debtaccounts['due_date'].strftime('%Y-%m-%d')
    debtaccounts['start_date_word'] = debtaccounts['start_date'].strftime('%d %b, %Y')
    debtaccounts['start_date'] = debtaccounts['start_date'].strftime('%Y-%m-%d')
    

    key_to_search = 'value'
    value_to_search = int(debtaccounts['payoff_order'])
    matching_dicts = next((dictionary for dictionary in payoff_order if dictionary.get(key_to_search) == value_to_search),None)    
    
    # debtaccounts['payoff_order'] = {
    #     'value':value_to_search,
    #     'label':matching_dicts['label']
    # }

    debtaccounts['payoff_order'] = matching_dicts['label']

    debtaccounts['balance'] = round(debtaccounts['balance'],2)
    debtaccounts['highest_balance'] = round(debtaccounts['highest_balance'],2)
    debtaccounts['minimum_payment'] = round(debtaccounts['minimum_payment'],2)
    debtaccounts['monthly_payment'] = round(debtaccounts['monthly_payment'],2)
    debtaccounts['interest_rate'] = round(debtaccounts['interest_rate'],2)
    debtaccounts['credit_limit'] = round(debtaccounts['credit_limit'],2)

    


    key_to_search = 'value'
    value_to_search = int(debtaccounts['reminder_days'])
    matching_dicts = next((dictionary for dictionary in reminder_days if dictionary.get(key_to_search) == value_to_search),None)    
    
    # debtaccounts['reminder_days'] = {
    #     'value':value_to_search,
    #     'label':matching_dicts['label']
    # }

    debtaccounts['reminder_days'] = matching_dicts['label']

    debtaccounts['autopay'] = 'Yes'  if debtaccounts['autopay'] > 0 else 'No'
    debtaccounts['inlclude_payoff'] = 'Yes'  if debtaccounts['inlclude_payoff'] > 0 else 'No'
    
    paid_off_percentage = calculate_paid_off_percentage(debtaccounts['highest_balance'], debtaccounts['balance'])
    left_to_go = round(float(100) - float(paid_off_percentage),1)

    twelve_months_ago = datetime.now() - timedelta(days=365)

    query = {
        #'role':{'$gte':10}
        "debt_acc_id":ObjectId(accntid),
        "created_at": {"$gte": twelve_months_ago},
        "deleted_at":None
    }
    cursor = debt_transactions.find(query,{
        '_id':0,
        'month':1,
        'year':1,
        'trans_date':1,
        'amount':1,
        'previous_balance':1,
        'new_balance':1
    })

    data_list = []
    for todo in cursor:
        #print(todo)
        

        #todo['billing_month_year'] = f"{todo['month']}, {todo['year']}"
        todo['trans_date'] = todo['trans_date'].strftime('%Y-%m-%d')
        todo['amount'] = round(todo['amount'],2)
        todo['previous_balance'] = round(todo['previous_balance'],2)
        todo['new_balance'] = round(todo['new_balance'],2)        
        data_list.append(todo)

    #total_count = debt_transactions.count_documents(query)
    #data_list = list(cursor)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    #print(data_obj)
    

    return jsonify({
        "payLoads":{
            "debtaccounts":debtaccounts,
            "debttrasactions":data_obj,        
            "left_to_go":left_to_go,
            "paid_off_percentage":paid_off_percentage            
        }        
    })


@app.route('/api/debt-summary/<string:accntid>', methods=['GET'])
def get_dept_summary(accntid:str):

    
    debtaccounts = debt_accounts.find_one(
        {"_id":ObjectId(accntid)},
        {
        "_id":0,
        'user_id':0        
        }        
        )
    
    paid_off_percentage = calculate_paid_off_percentage(debtaccounts['highest_balance'], debtaccounts['balance'])
    left_to_go = round(float(100) - float(paid_off_percentage),1)
    

    return jsonify({
        "currentBalance":debtaccounts['balance'],
        "left_to_go":left_to_go,
        "paid_off_percentage":paid_off_percentage        
    })

@app.route('/api/debt/<string:accntid>', methods=['GET'])
def get_debt(accntid:str):

    debtaccounts = debt_accounts.find_one(
        {"_id":ObjectId(accntid)},
        {"_id":0,'user_id':0}
        )
    
    debt_type = my_col('debt_type').find_one(
        {"_id":debtaccounts['debt_type']['value']},
        {"_id":0,"name":1}
        )


    if debt_type!=None:    
        debtaccounts['debt_type']['value'] = str(debtaccounts['debt_type']['value'])
        debtaccounts['debt_type']['label'] = debt_type['name']
    else:
        debtaccounts['debt_type'] = None

    debtaccounts['due_date'] = debtaccounts['due_date'].strftime('%Y-%m-%d')
    debtaccounts['start_date'] = debtaccounts['start_date'].strftime('%Y-%m-%d')

    key_to_search = 'value'
    value_to_search = int(debtaccounts['payoff_order'])
    matching_dicts = next((dictionary for dictionary in payoff_order if dictionary.get(key_to_search) == value_to_search),None)    
    
    debtaccounts['payoff_order'] = {
        'value':value_to_search,
        'label':matching_dicts['label']
    }

    debtaccounts['balance'] = round(debtaccounts['balance'],2)
    debtaccounts['highest_balance'] = round(debtaccounts['highest_balance'],2)
    debtaccounts['minimum_payment'] = round(debtaccounts['minimum_payment'],2)
    debtaccounts['monthly_payment'] = round(debtaccounts['monthly_payment'],2)
    debtaccounts['interest_rate'] = round(debtaccounts['interest_rate'],2)
    debtaccounts['credit_limit'] = round(debtaccounts['credit_limit'],2)

    


    key_to_search = 'value'
    value_to_search = int(debtaccounts['reminder_days'])
    matching_dicts = next((dictionary for dictionary in reminder_days if dictionary.get(key_to_search) == value_to_search),None)    
    
    debtaccounts['reminder_days'] = {
        'value':value_to_search,
        'label':matching_dicts['label']
    }
    


    return jsonify({
        "debtaccounts":debtaccounts,
        "payoff_order":payoff_order,        
        "reminder_days":reminder_days
    })
@app.route("/api/save-debt-account", methods=['POST'])
def save_debt_account():
    if request.method == 'POST':
        data = json.loads(request.data)
        debt_id = None
        message = ''
        result = 0
        user_id = data["user_id"]
        try:
            balance = float(data.get("balance", 0))
            interest_rate = float(data.get("interest_rate", 0))
            highest_balance =  float(data.get("highest_balance", 0))
            highest_balance = highest_balance if highest_balance > 0 else balance
            
            debt = {
                "name": data.get("name"),                
                # 'debt_type':{
                #     'value':ObjectId(data['debt_type']['value'])
                # },
                'debt_type':newEntryOptionData(data['debt_type'],'debt_type',user_id),
                "payor": data.get("payor"), 
                "balance":balance ,                
                "highest_balance": highest_balance,
                "minimum_payment": float(data.get("minimum_payment", 0)),                
                "monthly_payment": float(data.get("monthly_payment", 0)),
                "credit_limit": float(data.get("credit_limit", 0)),
                "interest_rate": interest_rate,
                "start_date": datetime.strptime(data['start_date'],"%Y-%m-%d"),                
                "due_date": datetime.strptime(data['due_date'],"%Y-%m-%d"),
                "monthly_interest":calculate_monthly_interest(balance,interest_rate),
                'notes':None,
                'promo_rate':0,
                'deffered_interest':0,
                'promo_interest_rate':0,
                'promo_good_through_month':None,
                'promo_good_through_year':None,
                'promo_monthly_interest':0,
                
                'autopay':0,
                'inlclude_payoff':0,
                'payoff_order':0,
                'reminder_days':0,

                'monthly_payment_option':0,
                'percentage':0,
                'lowest_payment':0,

                "user_id":ObjectId(user_id),
                "created_at":datetime.now(),
                "updated_at":datetime.now(),
                "deleted_at":None                
            }

          
    
    

   
            debt_account_data = debt_accounts.insert_one(debt)

            debt_id = str(debt_account_data.inserted_id)  
            result = 1 if debt_id!=None else 0
            message = 'Debt account added Succefull'
        except Exception as ex:
            print(ex)
            debt_id = None
            result = 0
            message = 'Debt account addition Failed'

        return jsonify({
            "debt_id":debt_id,            
            "message":message,
            "result":result
        })
            

@app.route("/api/update-debt-account/<string:accntid>", methods=['POST'])
def update_debt(accntid:str):
    if request.method == 'POST':
        data = json.loads(request.data)
        debt_account_id = accntid
        message = ''
        result = 0

        user_id = data['user_id']

        try:

            debt_acc_query = {
                "_id" :ObjectId(debt_account_id)
            }
            debtaccounts = debt_accounts.find_one(
                debt_acc_query,
                {'interest_rate':1, 'monthly_interest':1}
            )
            
            balance = float(data.get("balance", 0))
            interest_rate = float(data.get("interest_rate", 0))
            highest_balance =  float(data.get("highest_balance", 0))
            highest_balance = highest_balance if highest_balance > 0 else balance

            autopay = int(data['autopay']) if 'autopay' in data else 0
            inlclude_payoff=int(data['inlclude_payoff']) if 'inlclude_payoff' in data else 0
            payoff_order = int(data['payoff_order']['value'])            
            reminder_days = int(data['reminder_days']['value'])
            
            monthly_interest =   debtaccounts['monthly_interest']
            
            if are_floats_equal(interest_rate,debtaccounts['interest_rate']) == False:
               monthly_interest = calculate_monthly_interest(balance,interest_rate)
                         
                

            
            newvalues = { "$set": {
                "name": data.get("name"), 
                # 'debt_type':{
                #     'value':ObjectId(data['debt_type']['value'])
                # },
                'debt_type':newEntryOptionData(data['debt_type'],'debt_type',user_id),                   
                'balance':balance,
                "highest_balance": highest_balance,                
                "minimum_payment": float(data.get("minimum_payment", 0)),
                "monthly_payment": float(data.get("monthly_payment", 0)),
                "credit_limit": float(data.get("credit_limit", 0)),
                'interest_rate':interest_rate,
                "monthly_interest":monthly_interest,
                "due_date": datetime.strptime(data['due_date'],"%Y-%m-%d"),
                "start_date": datetime.strptime(data['start_date'],"%Y-%m-%d"),                             
                'inlclude_payoff':inlclude_payoff, 
                'payoff_order':payoff_order,                
                'reminder_days':reminder_days, 
                'autopay':autopay,
                'notes':data['notes'] if 'notes' in data and data['notes']!=""  else None,                                     
                "updated_at":datetime.now()
            } }
            debt_account_data = debt_accounts.update_one(debt_acc_query,newvalues)


            result = 1 if debt_account_data.modified_count else 0
            message = 'Debt account updated Succefull' if debt_account_data.modified_count else 'Debt account update Failed!'

        except Exception as ex:

            print('DEBT UPDATE EX: ',ex)

            debt_account_id = None            
            result = 0
            message = 'Debt account update Failed!'


        return jsonify({
            "debt_account_id":debt_account_id,
            "monthly_interest":monthly_interest,            
            "message":message,
            "result":result
        })


@app.route('/api/debts/<string:user_id>', methods=['POST'])
def list_debts(user_id:str):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])

    # Construct MongoDB filter query
    query = {
        #'role':{'$gte':10}
        "user_id":ObjectId(user_id),
        "deleted_at":None
    }
    
    

    if global_filter:

        #debt type filter
        debttype = my_col('debt_type').find(
                {'name':{"$regex":global_filter,"$options":"i"}},
                {'_id':1}
            )
        debttype_list = list(debttype)
        debttype_id_list = [d.pop('_id') for d in debttype_list]
        #end debt type filter

        #due_date = datetime.strptime(global_filter,"%Y-%m-%d")
        #print(due_date)        
        pattern_str = r'^\d{4}-\d{2}-\d{2}$'
        due_date = None
        #try:
        if re.match(pattern_str, global_filter):
            due_date = datetime.strptime(global_filter,"%Y-%m-%d")
        #except ValueError:
        else:
            due_date = None

        query["$or"] = [
            {"name": {"$regex": global_filter, "$options": "i"}},
            {"debt_type.value": {"$in":debttype_id_list}},
            {"due_date":due_date}            
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
        cursor = debt_accounts.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
    else:
        # Apply default sorting or skip sorting
        cursor = debt_accounts.find(query).skip(page_index * page_size).limit(page_size)

    total_count = debt_accounts.count_documents(query)
    data_list = []
    for todo in cursor:
        debt_type_id = todo['debt_type']['value']
        debt_type = my_col('debt_type').find_one(
        {"_id":debt_type_id},
        {"_id":0,"name":1}
        )

        paid_off_percentage = calculate_paid_off_percentage(todo['highest_balance'], todo['balance'])
        left_to_go = round(float(100) - float(paid_off_percentage),1)
        
        entry = {
            "_id":todo["_id"],
            "name":todo["name"],
            "debt_type":debt_type["name"] if debt_type!=None else None,
            "payor":todo["payor"],
            "balance":round(todo["balance"],2),
            "interest_rate":todo["interest_rate"],
            "monthly_payment":round(todo["monthly_payment"],2),
            "monthly_interest":round(todo["monthly_interest"],2),
            "due_date":todo["due_date"].strftime('%Y-%m-%d'),
            "left_to_go":left_to_go,
            "paid_off_percentage":paid_off_percentage            
            
        }
        data_list.append(entry)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size


    #total balance , interest, monthly intereset paid off
    # Aggregate query to sum the balance field
    pipeline = [
        {"$match": query},  # Filter by user_id
        {"$group": {"_id": None, 
                    "total_balance": {"$sum": "$balance"},
                    "total_highest_balance":{"$sum": "$highest_balance"},
                    "total_monthly_payment":{"$sum": "$monthly_payment"},                    
                    "total_monthly_interest":{"$sum": "$monthly_interest"},
                    "total_minimum_payment":{"$sum": "$minimum_payment"},
                    }}  # Sum the balance
    ]

    # Execute the aggregation pipeline
    result = list(debt_accounts.aggregate(pipeline))

    # Extract the total balance from the result
    total_balance = result[0]['total_balance'] if result else 0
    total_highest_balance = result[0]['total_highest_balance'] if result else 0
    total_monthly_payment = result[0]['total_monthly_payment'] if result else 0
    total_monthly_interest = result[0]['total_monthly_interest'] if result else 0
    total_paid_off = calculate_paid_off_percentage(total_highest_balance,total_balance)
    total_minimum_payment = result[0]['total_minimum_payment'] if result else 0

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count,
        'extra_payload':{
            'total_balance':total_balance,
            'total_monthly_payment':total_monthly_payment,
            'total_monthly_interest':total_monthly_interest,
            'total_paid_off':total_paid_off,
            'total_minimum_payment':total_minimum_payment
        }
        
    })



@app.route('/api/debt-header-data/<string:user_id>', methods=['GET'])
def get_dept_header_data(user_id:str):

    
    # Aggregate query to sum the balance field
    pipeline = [
        {"$match": {"user_id": ObjectId(user_id),'deleted_at':None}},  # Filter by user_id
        {
            '$addFields': {
                'total_monthly_minimum': {'$add': ['$monthly_payment', '$minimum_payment']}
            }
        },

        {
            "$group": {
                "_id": None, 
                "total_balance": {"$sum": "$balance"},
                "total_monthly_minimum": {"$sum": "$total_monthly_minimum"},

                "total_balance": {"$sum": "$balance"},
                "total_highest_balance":{"$sum": "$highest_balance"},
                "latest_month_debt_free": {"$max": "$month_debt_free"}

            }
        
        }  # Sum the balance
    ]

    # Execute the aggregation pipeline
    result = list(debt_accounts.aggregate(pipeline))

    # Extract the total balance from the result
    total_balance = result[0]['total_balance'] if result else 0

    total_monthly_minimum = round(result[0]['total_monthly_minimum'],2) if result else 0

    total_balance = result[0]['total_balance'] if result else 0
    total_highest_balance = result[0]['total_highest_balance'] if result else 0
    total_paid_off = calculate_paid_off_percentage(total_highest_balance,total_balance)

    user_setting = usersetting.find_one({'user_id':ObjectId(user_id)},{'debt_payoff_method':1,'monthly_budget':1})

    monthly_budget = 0

    if user_setting:
        monthly_budget = round(user_setting['monthly_budget'],2)
    
    snowball_amount = round(monthly_budget - total_monthly_minimum,2)

    active_debt_account = debt_accounts.count_documents({'user_id':ObjectId(user_id),'deleted_at':None})

    latest_month_debt_free = result[0]['latest_month_debt_free'].strftime('%b %Y') if result and 'latest_month_debt_free' in result[0] and result[0]['latest_month_debt_free']!=None else ''

    return jsonify({
        "debt_total_balance":total_balance,
        'monthly_budget':monthly_budget,
        'total_monthly_minimum':total_monthly_minimum,
        'snowball_amount':snowball_amount,
        'total_paid_off':total_paid_off,
        'active_debt_account':active_debt_account,
        "month_debt_free":latest_month_debt_free,
        "total_monthly_net_income":4200,
        "total_monthly_bill_expese":2300             
    })



@app.route('/api/debt-dashboard-data/<string:user_id>', methods=['GET'])
def get_dept_dashboard_data(user_id:str):

    page_size = 5
    query = {
        'user_id':ObjectId(user_id),
        'deleted_at':None
    }

    sort_params = [
    ('updated_at',-1)
    ]

    debt_list = []
    
    cursor = debt_accounts.find(query,{"user_id":0}).sort(sort_params).limit(page_size)

    for todo in cursor:
        paid_off_percentage = calculate_paid_off_percentage(todo['highest_balance'], todo['balance'])
        left_to_go = round(float(100) - float(paid_off_percentage),1)
        entry = {
            '_id':str(todo['_id']),
            'title':todo['name'],
            'progress':left_to_go,
            'amount':todo['balance']
        }
        debt_list.append(entry)
        
    data_json = MongoJSONEncoder().encode(debt_list)
    data_obj = json.loads(data_json)
    

    return jsonify({
        "debt_list":data_obj,             
    })


#save debt user settings 
@app.route("/api/get-user-settings/<user_id>", methods=['GET'])
def get_user_settings(user_id:str):

    user_setting = usersetting.find_one({'user_id':ObjectId(user_id)},{'_id':0,'user_id':0})

    return jsonify({
           
            "user_setting":user_setting            
        })


@app.route("/api/save-user-settings", methods=['POST'])
def save_user_settings():
    if request.method == 'POST':
        data = json.loads(request.data)        
        user_setting_id = None

        user_id = data['user_id']
        message = ''
        result = 0

        try:

            filter_query = {
                "user_id" :ObjectId(user_id)
            }

            update_document = {'$set': {'minimum_payments': float(data['minimum_payments']),'monthly_budget': float(data['monthly_budget']), 'debt_payoff_method': data['debt_payoff_method']}} 

            user_settings = usersetting.update_one(filter_query, update_document, upsert=True)
            if user_settings.upserted_id:
                
                user_setting_id = str(user_settings.upserted_id)
                message = 'Settings saved!'
                result = 1
            else:
                user_setting_id = user_settings.upserted_id
                message = 'Settings updated!'
                result = 1

           
            
                
        
        except Exception as ex:
            print('DEBT EXP: ',ex)
            user_setting_id = None
            result = 0
            message = 'Debt transaction addition Failed!'

        

            


        return jsonify({
           
            "user_setting_id":user_setting_id,
            "message":message,
            "result":result
        })


