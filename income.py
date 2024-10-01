import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from incomeutil import generate_new_transaction_data_for_income
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



@app.route('/api/delete-income', methods=['POST'])
def delete_income():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']

        income_account_id = None
        message = None
        error = 0
        deleted_done = 0

        try:
            myquery = { "_id" :ObjectId(id)}

            newvalues = { "$set": {                                     
                "deleted_at":datetime.now()                
            } }
            income_account_data =  collection.update_one(myquery, newvalues)
            income_account_id = id if income_account_data.modified_count else None
            error = 0 if income_account_data.modified_count else 1
            deleted_done = 1 if income_account_data.modified_count else 0
            message = 'Income account Deleted Successfully'if income_account_data.modified_count else 'Income account Deletion Failed'

        except Exception as ex:
            income_account_id = None
            print('Income account Save Exception: ',ex)
            message = 'Income account Deletion Failed'
            error  = 1
            deleted_done = 0
        
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
        {"_id":0}
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
        "deleted_at":None
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

        income_id = None
        message = ''
        result = 0
        try:

            net_income = float(data.get("net_income", 0))
            gross_income = float(data.get("gross_income", 0))
            
            repeat = data['repeat']

            pay_date = convertStringTodate(data['pay_date'])

            total_gross_income = 0
            total_net_income = 0
            

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

                'pay_date':pay_date,
                                
                

                
            }
            #print('data',data)
            #print('appendata',append_data)            

            merge_data = data | append_data

            print('mergedata',merge_data)

            myquery = { "_id" :ObjectId(id)}

            newvalues = { "$set": merge_data }

            income_data = my_col('income').update_one(myquery, newvalues)
            income_id = id if income_data.modified_count else None
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
        with client.start_session() as session:
            with session.start_transaction():
        
                try:

                    net_income = float(data.get("net_income", 0))
                    gross_income = float(data.get("gross_income", 0))
                    
                    repeat = data['repeat']['value'] if data['repeat']['value'] > 0 else None
                    

                    pay_date = convertStringTodate(data['pay_date'])

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

                        'pay_date':pay_date,
                        'next_pay_date':None,
                        'commit':commit       
                        

                        
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
                    if len(income_transaction_list)> 0:                    
                        income_transaction_data = income_transaction.insert_many(income_transaction_list,session=session)


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

                    result = 1 if income_id!=None and income_data.modified_count else 0
                    message = 'Income account added Succefull'
                    session.commit_transaction()
                    
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
                "deleted_at": None
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

    twelve_months_ago = datetime.now() - timedelta(days=365)

    print(twelve_months_ago)

    

    
    

    pipeline = [
    # Step 1: Match documents with pay_date in the last 12 months and not deleted
    {
        "$match": {
            "pay_date": {"$gte": twelve_months_ago},
            "deleted_at": None
        }
    },
    
    # Step 2: Project to extract year and month from pay_date
    {
        "$project": {
            "net_income": 1,
            "gross_income": 1,
            "year_month": {
                "$dateToString": {
                    "format": "%Y-%m",  # Format as "YYYY-MM"
                    "date": "$pay_date"
                }
            },
            "month": {
                "$dateToString": {
                    "format": "%m",  # Extract the month number (01-12)
                    "date": "$pay_date"
                }
            },
            "year": {
                "$dateToString": {
                    "format": "%Y",  # Extract the year
                    "date": "$pay_date"
                }
            }
        }
    },

    # Step 3: Group by year_month and sum the balance
    {
        "$group": {
            "_id": "$year_month",  # Group by the formatted month-year
            "total_balance": {"$sum": "$net_income"},
            "total_balance_gross": {"$sum": "$gross_income"},
            "year": {"$first": "$year"},  # Include the year
            "month": {"$first": "$month"}   # Include the month
        }
    },

    # Step 4: Create the formatted year_month_word
    {
        "$project": {
            "_id": 1,
            "total_balance": 1,
            "total_balance_gross":1,
            "year_month_word": {
                "$concat": [
                    {"$substr": [
                        {"$arrayElemAt": [
                            ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                            { "$subtract": [{ "$toInt": "$month" }, 1] }  # Convert month string to integer, { "$subtract": [{ "$toInt": "$month" }, 1] }  // Adjust for zero-based index
                        ]}, 0, 3  # Get the first 3 letters of the month
                    ]},
                    ", ",
                    "$year"  # Append the year
                ]
            }
        }
    },

    # Step 5: Optionally, sort by year_month
    {
        "$sort": {
            "_id": 1  # Sort in ascending order of year_month
        }
    },

    # Step 6: Limit to 12 rows
    {
        "$limit": 12  # Limit the output to the most recent 12 months
    },

    # Step 7: Calculate the total count and total balance
    {
        "$group": {
            "_id": None,  # No specific grouping field, aggregate the entire collection
            "total_count": {"$sum": 1},  # Count the number of months (or documents)
            "total_balance": {"$sum": "$total_balance"},  # Sum all the 'total_balance' values from the grouped results
            "total_balance_gross": {"$sum": "$total_balance_gross"},
            "grouped_results": {"$push": {  # Preserve all grouped results in an array
                "year_month": "$_id",
                "year_month_word": "$year_month_word",
                "total_balance": "$total_balance",
                "total_balance_gross":"$total_balance_gross"
            }}
        }
    },

    # Step 8: Use $project to format the output
    {
        "$project": {
            "_id": 0,                           # Remove the _id field
            #"total_count": 1,                   # Include the total count
            "total_balance": 1,
            "total_balance_gross":1,                 # Include the total balance
            "grouped_results": 1                # Include the grouped results
        }
    }
    
]
    
    
    
    year_month_wise_all = list(collection.aggregate(pipeline))

    year_month_wise_counts = year_month_wise_all[0]['grouped_results'] if year_month_wise_all else []
    #year_month_wise_type_t_count= year_month_wise_all[0]['total_count'] if year_month_wise_all else 0
    year_month_wise_balance = year_month_wise_all[0]['total_balance'] if year_month_wise_all else 0
    if len(year_month_wise_counts) > 0:
        data_json = MongoJSONEncoder().encode(year_month_wise_counts)
        year_month_wise_counts = json.loads(data_json)

    return jsonify({
        "payLoads":{            
            "income_source_type_counts":income_source_type_counts,
            "total_income_source_type":total_income_source_type,
            "total_balance":total_balance,
            "income_source_type_names":income_source_type_names,
            "year_month_wise_counts":year_month_wise_counts,
            "year_month_wise_balance":year_month_wise_balance


        }        
    })