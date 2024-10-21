import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from incomeutil import calculate_total_income_for_sepecific_month, generate_new_transaction_data_for_income
from app import app
from db import my_col,myclient
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal


client = myclient
collection = my_col('income')
income_source_types = my_col('income_source_types')
income_transaction = my_col('income_transactions')
usersettings = my_col('user_settings')


@app.route('/api/delete-income', methods=['POST'])
def delete_income():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']
        key = data['key']
        action = 'Deleted' if key < 2 else 'Closed'
        field = 'deleted_at' if key < 2 else 'closed_at'

        income_account_id = None
        message = None
        error = 0
        deleted_done = 0

        myquery = { "_id" :ObjectId(id)}
        previous_income = collection.find_one(myquery,{'commit':1})
        previous_commit = previous_income['commit']

        with client.start_session() as session:
                with session.start_transaction():
                    
                    try:
                        myquery = { "_id" :ObjectId(id)}

                        newvalues = { "$set": {                                     
                            field:datetime.now()                
                        } }
                        income_account_data =  collection.update_one(myquery, newvalues, session=session)
                        income_account_id = id if income_account_data.modified_count else None


                        #delete previous commits data
                        income_data_delete = income_transaction.update_many({
                            'income_id':ObjectId(income_account_id),
                            'commit':previous_commit
                        },{
                            "$set":{
                                field:datetime.now()
                            }
                        },session=session)


                        error = 0 if income_account_data.modified_count and income_data_delete.modified_count else 1
                        deleted_done = 1 if income_account_data.modified_count and income_data_delete.modified_count else 0
                        
                        

                        if deleted_done:
                            message = f'Income account {action} Successfully'
                            session.commit_transaction()
                        else:
                            message = f'Income account {action} Failed'
                            session.abort_transaction()

                    except Exception as ex:
                        income_account_id = None
                        print('Income account Save Exception: ',ex)
                        message = f'Income account {action} Failed'
                        error  = 1
                        deleted_done = 0
                        session.abort_transaction()
        
        return jsonify({
            "income_account_id":income_account_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })


@app.route("/api/income-all/<string:id>", methods=['GET'])
def get_income_all(id:str):
    income = collection.find_one(
        {"_id":ObjectId(id)},
        {"_id":0}
        )
    
    income['pay_date_word'] = income['pay_date'].strftime('%d %b, %Y')
    income['pay_date'] = convertDateTostring(income['pay_date'],"%Y-%m-%d")

    income['next_pay_date_word'] = income['next_pay_date'].strftime('%d %b, %Y')
    income['next_pay_date'] = convertDateTostring(income['next_pay_date'],"%Y-%m-%d")
   
    income['user_id'] = str(income['user_id'])

    
    income_source_type = my_col('income_source_types').find_one(
        {"_id":income['income_source']['value']},
        {"_id":0,"name":1}
        )
    
    
    income['income_source'] = income_source_type['name']

    income['repeat'] = income['repeat']['label']
    
    

    return jsonify({
        "payLoads":{
            "income":income
        }
    })

@app.route("/api/income/<string:id>", methods=['GET'])
def view_incomes(id:str):
    income = collection.find_one(
        {"_id":ObjectId(id)},
        {
            "_id":0,
            "commit":0,
            "next_pay_date":0, 
            #"total_gross_income":0, 
            #"total_net_income":0,
            "created_at":0,
            "updated_at":0,
            "deleted_at":0,
            "closed_at":0
        }
        )
    
    
    income['pay_date'] = convertDateTostring(income['pay_date'],"%Y-%m-%d")
    
    income['user_id'] = str(income['user_id'])

    
    income_source_type = my_col('income_source_types').find_one(
        {"_id":income['income_source']['value']},
        {"_id":0,"name":1}
        )
    
    income['income_source']['value'] = str(income['income_source']['value'])
    income['income_source']['label'] = income_source_type['name']

    
    

    return jsonify({
        "income":income
    })

@app.route('/api/income/<string:user_id>', methods=['POST'])
def list_income(user_id:str):
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
    if global_filter:

        #income type filter
        income_source_types = my_col('income_source_types').find(
                {'name':{"$regex":global_filter,"$options":"i"}},
                {'_id':1}
            )
        income_source_types_list = list(income_source_types)
        income_source_types_id_list = [d.pop('_id') for d in income_source_types_list]

        pattern_str = r'^\d{4}-\d{2}-\d{2}$'
        pay_date = None
        
        #try:
        if re.match(pattern_str, global_filter):
            pay_date = datetime.strptime(global_filter,"%Y-%m-%d")
            
        #except ValueError:
        else:
            pay_date = None
            

        query["$or"] = [
            
            {"earner": {"$regex": global_filter, "$options": "i"}},            
            {"pay_date":pay_date},           
            {"income_source.value": {"$in":income_source_types_id_list}},                 
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
        cursor = collection.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
    else:
        # Apply default sorting or skip sorting
        cursor = collection.find(query).skip(page_index * page_size).limit(page_size)

    total_count = collection.count_documents(query)
    #data_list = list(cursor)
    data_list = []

    for todo in cursor:
        if todo['income_source']!=None:
            income_source_id = todo['income_source']['value']
            income_source_type = my_col('income_source_types').find_one(
            {"_id":income_source_id},
            {"_id":0,"name":1}
            )
            todo['income_source'] =  income_source_type['name']

        

        todo['pay_date'] = convertDateTostring(todo['pay_date'])
        todo['next_pay_date'] = convertDateTostring(todo['next_pay_date'])

        


        data_list.append(todo)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size


    #total balance , interest, monthly intereset paid off
    # Aggregate query to sum the balance field
    pipeline = [
        {"$match": query},  # Filter by user_id
        # {
        #     '$addFields': {
        #         'total_monthly_income': {'$add': ['$gross_income', '$income_boost']}
        #     }
        # },
        {"$group": {"_id": None, 
                    "total_net_income": {"$sum": "$net_income"},
                    "total_gross_income":{"$sum": "$gross_income"},                                                        
                    }}  # Sum the balance
    ]

    # Execute the aggregation pipeline
    result = list(collection.aggregate(pipeline))

     # Extract the total balance from the result
    total_net_income = result[0]['total_net_income'] if result else 0
    total_gross_income = result[0]['total_gross_income'] if result else 0
    
    

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count,
        'extra_payload':{
            'total_net_income':total_net_income,
            'total_gross_income':total_gross_income,             
        }
    })


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



@app.route('/api/save-income-account/<string:id>', methods=['POST'])
async def update_income(id:str):
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']

        income_id = id
        message = ''
        result = 0
        

        myquery = { "_id" :ObjectId(income_id)}
        previous_income = collection.find_one(myquery)

        net_income = float(data.get("net_income", 0))
        gross_income = float(data.get("gross_income", 0))
        
        repeat = data['repeat']['value'] if data['repeat']['value'] > 0 else None

        previous_gross_income = float(previous_income['gross_income'])
        previous_net_income = float(previous_income['net_income'])
        previous_repeat = previous_income['repeat']['value'] if previous_income['repeat']['value'] > 0 else None
        previous_commit = previous_income['commit']
        pay_date = previous_income['pay_date']

        change_found_gross = False if are_floats_equal(previous_gross_income, gross_income) else True
        change_found_net = False if are_floats_equal(previous_net_income, net_income) else True
        change_found_repat = False if previous_repeat == repeat else True

        any_change = change_found_gross or change_found_net or change_found_repat

        print('change_found_gross',change_found_gross)
        print('change_found_net',change_found_net)
        print('change_found_repat',change_found_repat)

        print('any change',any_change)

        append_data = {
            'income_source':newEntryOptionData(data['income_source'],'income_source_types',user_id),                        
            'user_id':ObjectId(user_id),
            'net_income':net_income,
            'gross_income':gross_income,                                                       
            "updated_at":datetime.now(),                                                                                   
        }

        merge_data = data | append_data

        #print('mergedata',merge_data)
        del merge_data['pay_date']

        

        #if we found any changes on gross_income, net_income or repeat values
        if any_change:        

            with client.start_session() as session:
                with session.start_transaction():
                    try:

                        del merge_data['total_gross_income']
                        del merge_data['total_net_income']
                        #del merge_data['next_pay_date']

                        #get latest commit
                        commit = datetime.now() 
                        #generate new trasnaction data and save them
                        income_transaction_generate = generate_new_transaction_data_for_income(
                        gross_income,
                        net_income,
                        pay_date,
                        repeat,
                        commit,
                        ObjectId(income_id)
                        )                        
                        
                    
                        income_transaction_list = income_transaction_generate['income_transaction']
                        total_gross_income = income_transaction_generate['total_gross_for_period']
                        total_net_income = income_transaction_generate['total_net_for_period']
                        next_pay_date = income_transaction_generate['next_pay_date']
                        income_transaction_data = None
                        if len(income_transaction_list)> 0:                    
                            income_transaction_data = income_transaction.insert_many(income_transaction_list,session=session)
                                                
                        

                        #update latest commit and transaction summary
                        new_data_value = {
                            'commit':commit,
                            "total_gross_income":total_gross_income, 
                            "total_net_income":total_net_income, 
                            "next_pay_date":next_pay_date,                                                                                                
                            "updated_at":datetime.now()
                        }
                        new_merge_value = new_data_value | merge_data
                        #print(new_merge_value)
                        newvalues = { "$set": new_merge_value }                       
                        income_data = collection.update_one(myquery, newvalues, session=session)


                        #delete previous commits data
                        income_data_delete = income_transaction.update_many({
                            'income_id':ObjectId(income_id),
                            'commit':previous_commit
                        },{
                            "$set":{
                                'deleted_at':datetime.now()
                            }
                        },session=session)
                        

                        result = income_id!=None and  income_transaction_data!=None and income_transaction_data.inserted_ids and income_data.modified_count and income_data_delete.modified_count                                   
                        
                                                
                        if result:
                            message = 'Income account updated Succefull'
                            session.commit_transaction()
                        else:
                            message = 'Income account update Failed'
                            session.abort_transaction()
                    except Exception as ex:
                        income_id = None
                        print('Income Update Exception: ',ex)
                        result = 0
                        message = 'Income account update Failed'
                        session.abort_transaction()
        else:
            newvalues = { "$set": merge_data }
            try:
                income_data = collection.update_one(myquery, newvalues)
                result = 1 if income_data.modified_count else 0
                message = 'Income account updated Succefull'
            except Exception as ex:
                income_id = None
                print('Income Update Exception: ',ex)
                result = 0
                message = 'Income account update Failed'


        return jsonify({
            "income_id":income_id,
            "message":message,
            "result":result
        })
    





@app.route('/api/save-income-account', methods=['POST'])
async def save_income():

    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']

        income_id = None
        message = ''
        result = 0
        total_monthly_gross_income = 0
        total_monthly_net_income = 0
        with client.start_session() as session:
            with session.start_transaction():
        
                try:

                    net_income = float(data.get("net_income", 0))
                    gross_income = float(data.get("gross_income", 0))
                    
                    repeat = data['repeat']['value'] if data['repeat']['value'] > 0 else None
                    

                    pay_date = convertStringTodate(data['pay_date'])


                    #close = int(data['close']) if 'close' in data else 0

                    total_gross_income = 0
                    total_net_income = 0

                    commit = datetime.now()
                    
                    append_data = {
                        'income_source':newEntryOptionData(data['income_source'],'income_source_types',user_id),
                        
                        'user_id':ObjectId(user_id),

                        'net_income':net_income,
                        'gross_income':gross_income,
                        'total_net_income':total_net_income,
                        'total_gross_income':total_gross_income,
                        
                        
                        "created_at":datetime.now(),
                        "updated_at":datetime.now(),
                        "deleted_at":None,
                        #"close":0,
                        "closed_at":None,

                        'pay_date':pay_date,
                        'next_pay_date':None,
                        'commit':commit,
                        "deleted_at":None,
                        "closed_at":None       
                        

                        
                    }
                    #print('data',data)
                    #print('appendata',append_data)            

                    merge_data = data | append_data

                    #print('mergedata',merge_data)

                    income_data = collection.insert_one(merge_data,session=session)
                    income_id = str(income_data.inserted_id)

                    income_transaction_generate = generate_new_transaction_data_for_income(
                        gross_income,
                        net_income,
                        pay_date,
                        repeat,
                        commit,
                        ObjectId(income_id)
                        )
                    
                    income_transaction_list = income_transaction_generate['income_transaction']
                    total_gross_income = income_transaction_generate['total_gross_for_period']
                    total_net_income = income_transaction_generate['total_net_for_period']
                    next_pay_date = income_transaction_generate['next_pay_date']
                    income_transaction_data = None
                    if len(income_transaction_list)> 0:                    
                        income_transaction_data = income_transaction.insert_many(income_transaction_list,session=session)
                        total_monthly_gross_income, total_monthly_net_income = calculate_total_income_for_sepecific_month(income_transaction_list,commit.strftime('%Y-%m'))


                    usersettings_data = usersettings.update_one(
                            {'user_id':ObjectId(user_id)},
                            { "$set": {
                                'total_monthly_gross_income':total_monthly_gross_income,
                                'total_monthly_net_income':total_monthly_net_income,
                            } }
                            ,session=session 
                        )


                    income_query = {
                        "_id" :ObjectId(income_id)
                    }

                    newvalues = { "$set": {
                        "total_gross_income":total_gross_income, 
                        "total_net_income":total_net_income, 
                        "next_pay_date":next_pay_date,                                                                                                
                        "updated_at":datetime.now()
                    } }
                    
                    income_data = collection.update_one(income_query,newvalues,session=session)

                    

                    

                    result = 1 if income_id!=None and income_transaction_data!=None and income_transaction_data.acknowledged and income_data.modified_count and usersettings_data.modified_count else 0
                    
                    if result:
                        message = 'Income account added Succefull'
                        session.commit_transaction()
                    else:
                        message = 'Income account addition Failed'
                        session.abort_transaction()
                    
                except Exception as ex:
                    income_id = None
                    print('Income Save Exception: ',ex)
                    result = 0
                    message = 'Income account addition Failed'
                    session.abort_transaction()
                    

        return jsonify({
            "income_id":income_id,
            "message":message,
            "result":result
        })
    


@app.route('/api/income-typewise-info', methods=['GET'])
def get_typewise_income_info():

    # Fetch the income type cursor
    income_type_cursor = my_col('income_source_types').find(
        {"deleted_at": None},
        {'_id': 1, 'name': 1}
    )

    # Create a list of _id values
    incometype_id_list = [item['_id'] for item in income_type_cursor]


    pipeline = [
        # Step 1: Match documents with income_source.value in billtype_id_list
        {
            "$match": {
                "income_source.value": {"$in": incometype_id_list},
                "deleted_at": None,
                "closed_at":None
            }
        },

        # Step 2: Lookup to join income_source collection to get the name (label)
        {
            "$lookup": {
                "from": "income_source_types",                # The collection to join
                "localField": "income_source.value",    # Field from the current collection
                "foreignField": "_id",              # Field from the income_source collection
                "as": "income_source_info"                   # Resulting array field for joined data
            }
        },

        # Step 3: Unwind the income_source_info array to flatten it
        {"$unwind": "$income_source_info"},

        # Step 4: Group by income_source.value and count occurrences, include income_source name
        {
            "$group": {
                "_id": "$income_source.value",          # Group by income_source.value
                "count": {"$sum": 1},               # Count occurrences per bill type
                "balance": {"$sum": "$gross_income"},  # Sum balance and monthly_interest
                "name": {"$first": "$income_source_info.name"}  # Get the first name (label)
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
    income_source_type_all = list(collection.aggregate(pipeline))

    income_source_type_counts = income_source_type_all[0]['grouped_results'] if income_source_type_all else []
    total_income_source_type = income_source_type_all[0]['total_count'] if income_source_type_all else 0
    total_balance = income_source_type_all[0]['total_balance'] if income_source_type_all else 0
    if len(income_source_type_counts) > 0:
        data_json = MongoJSONEncoder().encode(income_source_type_counts)
        income_source_type_counts = json.loads(data_json)

     # Fetch bill type names
    income_source_types = my_col('income_source_types').find({'_id': {'$in': incometype_id_list}})    
    income_source_type_names = {str(d['_id']): d['name'] for d in income_source_types}
    

    

    return jsonify({
        "payLoads":{            
            "income_source_type_counts":income_source_type_counts,
            "total_income_source_type":total_income_source_type,
            "total_balance":total_balance,
            "income_source_type_names":income_source_type_names


        }        
    })