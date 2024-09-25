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


client = myclient
collection = my_col('income')
income_source_types = my_col('income_source_types')

def calculate_next_payment(pay_date, repeat_value):
    if repeat_value == 1:  # Daily
        next_payment = pay_date + timedelta(days=1)
    elif repeat_value == 2:  # Weekly
        next_payment = pay_date + timedelta(weeks=1)
    elif repeat_value == 3:  # Bi-weekly
        next_payment = pay_date + timedelta(weeks=2)
    elif repeat_value == 4:  # Monthly
        next_payment = pay_date.replace(month=pay_date.month % 12 + 1) if pay_date.month != 12 else pay_date.replace(year=pay_date.year + 1, month=1)
    elif repeat_value == 5:  # Quarterly
        next_payment = pay_date.replace(month=pay_date.month + 3 if pay_date.month <= 9 else pay_date.month - 9, year=pay_date.year if pay_date.month <= 9 else pay_date.year + 1)
    elif repeat_value == 6:  # Annually
        next_payment = pay_date.replace(year=pay_date.year + 1)
    else:
        next_payment = None  # For unsupported repeat values
    return next_payment


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
    income['pay_date_boost_word'] = income['pay_date_boost'].strftime('%d %b, %Y')
    income['pay_date_boost'] = convertDateTostring(income['pay_date_boost'],"%Y-%m-%d")
    income['user_id'] = str(income['user_id'])

    
    income_source_type = my_col('income_source_types').find_one(
        {"_id":income['income_source']['value']},
        {"_id":0,"name":1}
        )
    
    
    income['income_source'] = income_source_type['name']

    income['repeat'] = income['repeat']['label']
    income['repeat_boost'] = income['repeat_boost']['label']

    if income['income_boost_source']!=None:
        income_boost_type = my_col('income_boost_types').find_one(
            {"_id":income['income_boost_source']['value']},
            {"_id":0,"name":1}
            )
        
        
        income['income_boost_source'] = income_boost_type['name']
    

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
    income['pay_date_boost'] = convertDateTostring(income['pay_date_boost'],"%Y-%m-%d")
    income['user_id'] = str(income['user_id'])

    
    income_source_type = my_col('income_source_types').find_one(
        {"_id":income['income_source']['value']},
        {"_id":0,"name":1}
        )
    
    income['income_source']['value'] = str(income['income_source']['value'])
    income['income_source']['label'] = income_source_type['name']

    if income['income_boost_source']!=None:
        income_boost_type = my_col('income_boost_types').find_one(
            {"_id":income['income_boost_source']['value']},
            {"_id":0,"name":1}
            )
        
        income['income_boost_source']['value'] = str(income['income_boost_source']['value'])
        income['income_boost_source']['label'] = income_boost_type['name']
    

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
        pay_date_boost = None
        #try:
        if re.match(pattern_str, global_filter):
            pay_date = datetime.strptime(global_filter,"%Y-%m-%d")
            pay_date_boost = datetime.strptime(global_filter,"%Y-%m-%d")
        #except ValueError:
        else:
            pay_date = None
            pay_date_boost = None

        query["$or"] = [
            
            {"earner": {"$regex": global_filter, "$options": "i"}},            
            {"pay_date":pay_date},
            {"pay_date_boost":pay_date_boost},
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

        if todo['income_boost_source']!=None:
            income_boost_id = todo['income_boost_source']['value']
            income_boost_type = my_col('income_boost_types').find_one(
            {"_id":income_boost_id},
            {"_id":0,"name":1}
            )
            todo['income_boost_source'] =  income_boost_type['name']

        todo['pay_date'] = convertDateTostring(todo['pay_date'])

        todo['next_pay_date'] = convertDateTostring(todo['next_pay_date'])

        todo['pay_date_boost'] = convertDateTostring(todo['pay_date_boost'])

        todo['next_boost_date'] = convertDateTostring(todo['next_boost_date'])

        todo['monthly_income_total'] = float(todo['monthly_gross_income']+todo['income_boost'])
        


        data_list.append(todo)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size


    #total balance , interest, monthly intereset paid off
    # Aggregate query to sum the balance field
    pipeline = [
        {"$match": query},  # Filter by user_id
        {
            '$addFields': {
                'total_monthly_income': {'$add': ['$monthly_gross_income', '$income_boost']}
            }
        },
        {"$group": {"_id": None, 
                    "total_monthly_net_income": {"$sum": "$monthly_net_income"},
                    "total_monthly_gross_income":{"$sum": "$monthly_gross_income"},
                    "total_income_boost" :{"$sum": "$income_boost"},
                    "total_monthly_income" :{"$sum": "$total_monthly_income"},                  
                    }}  # Sum the balance
    ]

    # Execute the aggregation pipeline
    result = list(collection.aggregate(pipeline))

     # Extract the total balance from the result
    total_monthly_net_income = result[0]['total_monthly_net_income'] if result else 0
    total_monthly_gross_income = result[0]['total_monthly_gross_income'] if result else 0
    
    total_income_boost = result[0]['total_income_boost'] if result else 0
    total_monthly_income = result[0]['total_monthly_income'] if result else 0

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count,
        'extra_payload':{
            'total_monthly_net_income':total_monthly_net_income,
            'total_monthly_gross_income':total_monthly_gross_income,
            'total_income_boost':total_income_boost,
            'total_monthly_income':total_monthly_income              
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

            monthly_net_income = float(data.get("monthly_net_income", 0))
            monthly_gross_income = float(data.get("monthly_gross_income", 0))
            income_boost = float(data.get("income_boost", 0))
            repeat = data['repeat']
            repeat_boost = data['repeat_boost']

            # Get the number of months to calculate over (default to 12 months for a year)
            months = int(request.args.get('months', 12))

            # Calculate the total income immediately
            """ total_gross_income = calculate_total_income_with_repeat(
                monthly_gross_income,
                income_boost,
                repeat,
                repeat_boost,
                days=months * 30  # Convert months to days for calculation
            ) """

            total_gross_income = calculate_total_monthly_gross_income(
                monthly_gross_income,
                income_boost,
                repeat['label'],
                repeat_boost['label']                
            )



            # deductions = data.get('deductions', 0)

            # # Calculate the net income including the income boost
            # total_net_income = total_gross_income - (deductions * (months // repeat['value']))

            total_net_income = calculate_total_monthly_net_income(
                monthly_net_income,
                income_boost,
                repeat['label'],
                repeat_boost['label']                
            )


            

            pay_date = convertStringTodate(data['pay_date'])
            pay_date_boost = convertStringTodate(data['pay_date_boost'])                        
            next_pay_date = calculate_next_payment(pay_date, data['repeat']['value']) 
            next_boost_date = calculate_next_payment(pay_date_boost, data['repeat_boost']['value'])            
            #print(next_boost_date)

            append_data = {
                'income_source':newEntryOptionData(data['income_source'],'income_source_types',user_id),
                'income_boost_source':newEntryOptionData(data['income_boost_source'],'income_boost_types',user_id),                

                'user_id':ObjectId(user_id),

                'monthly_net_income':monthly_net_income,
                'monthly_gross_income':monthly_gross_income,
                'income_boost':income_boost,

                'total_gross_income':round(total_gross_income,2),
                'total_net_income':round(total_net_income,2),
                "created_at":datetime.now(),
                "updated_at":datetime.now(),
                "deleted_at":None,

                'pay_date':pay_date,
                'pay_date_boost':pay_date_boost,                             
                'next_pay_date':next_pay_date,
                'next_boost_date':next_boost_date                  
                

                
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
    


def newIncomeAccountsTransactions(income_data):
    today = datetime.today()    
    monthly_gross_income = income_data['monthly_gross_income']
    monthly_net_income = income_data['monthly_net_income']
    first_pay_date = income_data['pay_date']
    base_income_frequency = income_data['repeat']  # Can be monthly, quarterly, annually
    boost_amount = income_data['income_boost']
    boost_frequency = income_data['repeat_boost']
    pay_date_boost = income_data['pay_date_boost']
    income_id = income_data['income_id']

    


    total_gross_income = 0
    total_net_income = 0
    income_details = []
    current_date = first_pay_date

    #print(base_income_frequency, boost_frequency)
    #month_count =  calculate_income_month_count(first_pay_date)
    #print('month counted',month_count)
    while current_date <= today:
    # for month in range(month_count):
        #current_month = first_pay_date + timedelta(days=30 * month)

        #print('current month',current_month, 'month',month)

    #while current_date <= today:
        base_gross_income = monthly_gross_income
        base_net_income = monthly_net_income
        
        boost = 0
        if boost_frequency:
            boost = calculate_boost(current_date, first_pay_date, boost_frequency, boost_amount)

        total_gross_for_period = base_gross_income + boost
        total_net_for_period = base_net_income + boost
        total_gross_income += total_gross_for_period
        total_net_income += total_net_for_period

        # Append details for the current period
        income_details.append({
            "period_start_word": current_date.strftime("%b, %Y"),
            "period_start": current_date.strftime("%Y-%m"),
            "creation_date":current_date,
            "base_gross_income": base_gross_income,
            "base_net_income": base_net_income,
            "boost": boost,
            "boost_amount":boost_amount,
            "total_gross_for_period": total_gross_for_period,
            'total_net_for_period':total_net_for_period,            
            "income_id":ObjectId(income_id),
            "created_at":datetime.now()
        })
        

        # Move to the next period based on base income frequency
        current_date = add_time(current_date, base_income_frequency)

    return {
        'income_details':income_details,
        'total_net_income':total_net_income,
        'total_gross_income':total_gross_income
    }



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

                    monthly_net_income = float(data.get("monthly_net_income", 0))
                    monthly_gross_income = float(data.get("monthly_gross_income", 0))
                    income_boost = float(data.get("income_boost", 0))
                    repeat = data['repeat']['value'] if data['repeat']['value'] > 0 else None
                    repeat_boost = data['repeat_boost']['value'] if data['repeat_boost']['value'] > 0 else None


                    total_gross_income = 0
                    total_net_income = 0

                    pay_date = convertStringTodate(data['pay_date'])
                    pay_date_boost = convertStringTodate(data['pay_date_boost'])                        
                    next_pay_date = calculate_next_payment(pay_date, data['repeat']['value']) 
                    next_boost_date = calculate_next_payment(pay_date_boost, data['repeat_boost']['value'])            

                    append_data = {
                        'income_source':newEntryOptionData(data['income_source'],'income_source_types',user_id),
                        'income_boost_source':newEntryOptionData(data['income_boost_source'],'income_boost_types',user_id),                

                        'user_id':ObjectId(user_id),

                        'monthly_net_income':monthly_net_income,
                        'monthly_gross_income':monthly_gross_income,
                        'income_boost':income_boost,

                        'total_gross_income':round(total_gross_income,2),
                        'total_net_income':round(total_net_income,2),
                        
                        "created_at":datetime.now(),
                        "updated_at":datetime.now(),
                        "deleted_at":None,

                        'pay_date':pay_date,
                        'pay_date_boost':pay_date_boost,                
                        'next_pay_date':next_pay_date,
                        'next_boost_date':next_boost_date                   
                        

                        
                    }
                    #print('data',data)
                    #print('appendata',append_data)            

                    merge_data = data | append_data

                    #print('mergedata',merge_data)

                    income_data = my_col('income').insert_one(merge_data,session=session)
                    income_id = str(income_data.inserted_id)

                    if repeat:

                        income_transaction = newIncomeAccountsTransactions({
                            'monthly_gross_income':monthly_gross_income,
                            'monthly_net_income':monthly_net_income,
                            'pay_date':pay_date,
                            'repeat':repeat,
                            'income_boost':income_boost,
                            'repeat_boost':repeat_boost,
                            'pay_date_boost':pay_date_boost,
                            'income_id':income_id

                        })
                        income_details = income_transaction['income_details']
                        total_net_income = income_transaction['total_net_income']
                        total_gross_income = income_transaction['total_gross_income']
                        

                        my_col(f"income_transactions").insert_many(income_details,session=session)

                        newvalues = { "$set": {
                            "total_gross_income":total_gross_income,
                            "total_net_income":total_net_income,                                                                                                
                            "updated_at":datetime.now()
                        } }

                        query = {
                            "_id" :ObjectId(income_id)
                        }

                        my_col('income').update_one(query,newvalues,session=session)


                    result = 1 if income_id!=None else 0
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
                "balance": {"$sum": "$monthly_gross_income"},  # Sum balance and monthly_interest
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

    

    # Define the aggregation pipeline
    """ pipeline = [
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
            "monthly_net_income": 1,
            "year_month": {
                "$dateToString": {
                    "format": "%Y-%m",
                    "date": "$pay_date"
                }
            },
            "year_month_word":{
                "$dateToString": {
                    "format": "%b, %Y",
                    "date": "$pay_date"
                }
            }
        }
    },

    # Step 3: Group by year_month and sum the balance
    {
        "$group": {
            "_id": "$year_month",  # Group by the formatted month-year
            "total_balance": {"$sum": "$monthly_net_income"},
            "total_balance_gross": {"$sum": "$monthly_gross_income"},
            "year_month_word": {"$first": "$year_month_word"}  # Include the readable format
        }
    },

    
    
    # Step 4: Optionally, sort by year_month
    {
        "$sort": {
            "_id": 1  # Sort in ascending order of year_month
        }
    },


    # Step 5: Calculate the total count and total balance
    {
        "$group": {
            "_id": None,                        # No specific grouping field, aggregate the entire collection
            #"total_count": {"$sum": 1},        # Count the number of months (or documents)
            "total_balance": {"$sum": "$total_balance"},  # Sum all the 'total_balance' values from the grouped results
            "total_balance_gross": {"$sum": "$total_balance_gross"},
            "grouped_results": {"$push": {  # Preserve all grouped results in an array
                "year_month": "$_id",
                "year_month_word": "$year_month_word",
                "total_balance": "$total_balance"
            }}
        }
    },

    # Step 6: Use $project to format the output
    {
        "$project": {
            "_id": 0,                           # Remove the _id field
            #"total_count": 1,                   # Include the total count
            "total_balance": 1,                 # Include the total balance
            "grouped_results": 1                # Include the grouped results
        }
    }
] """
    

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
            "monthly_net_income": 1,
            "monthly_gross_income": 1,
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
            "total_balance": {"$sum": "$monthly_net_income"},
            "total_balance_gross": {"$sum": "$monthly_gross_income"},
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