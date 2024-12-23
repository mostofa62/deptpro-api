from collections import defaultdict
import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from incomeutil import calculate_breakdown_future,generate_new_transaction_data_for_future_income_boost, generate_new_transaction_data_for_future_income_v1, generate_new_transaction_data_for_income, generate_unique_id
from app import app
from db import my_col,myclient
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal


client = myclient
collection = my_col('income_transactions')
income = my_col('income')
income_boost = my_col('income_boost')
income_boost_transaction = my_col('income_boost_transactions')
income_monthly_log = my_col('income_monthly_log')
income_boost_monthly_log = my_col('income_boost_monthly_log')
app_data = my_col('app_data')


def income_transactions_next_function(todo):

        
        pipeline_boost = [
        {
            '$match': {
                'income.value': todo['_id'],
                'deleted_at':None,
                'closed_at':None,
                'repeat_boost.value': {'$gt': 0}
            }
            },
            {
                '$group': {
                    '_id': None,
                    'total_repeat_boost': {'$sum': '$repeat_boost.value'},
                    'total_income_boost': {
                        '$sum': '$income_boost'
                    }
                }
            }
        ]

        # Execute the aggregation
        result_boost = list(income_boost.aggregate(pipeline_boost))

        # Get the sums if any results found
        total_repeat_boost = result_boost[0]['total_repeat_boost'] if result_boost else 0
        total_income_boost = result_boost[0]['total_income_boost'] if result_boost else 0

        print('total_repeat_boost, total_income_boost',total_repeat_boost, total_income_boost)

        total_gross_income = todo['total_gross_income']
        total_net_income = todo['total_net_income']

        gross_income = todo['gross_income']
        net_income = todo['net_income']


        pipeline_boost_onetime = [
            {
                '$match': {
                    'income.value': todo['_id'],
                    'deleted_at': None,
                    'closed_at':None,
                    'repeat_boost.value': {'$lt': 1}
                }
            },
            {
                '$group': {
                    '_id': None,
                    'total_income_boost': {
                        '$sum': '$income_boost'
                    }
                }
            }
        ]


        # Execute the aggregation
        result_boost_onetime = list(income_boost.aggregate(pipeline_boost_onetime))

        total_income_boost_onetime = result_boost_onetime[0]['total_income_boost'] if result_boost_onetime else None

        print('total_income_boost_onetime',total_income_boost_onetime)
        #print(total_balance, contribution)

        #total_balance = todo['total_balance']
        #contribution = todo['contribution']
        income_boost_date = todo['next_pay_date'].strftime('%Y-%m') if total_income_boost_onetime !=None else None

        income_contribution_data = calculate_breakdown_future(

            initial_gross_input=total_gross_income,
            initial_net_input=total_net_income,
            gross_input=gross_income,
            net_input=net_income,            
            pay_date = todo['next_pay_date'],            
            frequency=todo['repeat']['value'],
            income_boost=total_income_boost_onetime,
            income_boost_date=income_boost_date,                        
            repeat_income_boost = total_income_boost,
            earner=todo.get('earner'),
            earner_id=str(todo['_id'])
        )

        income_contribution = income_contribution_data['breakdown']

        
               

    
        


        return income_contribution


@app.route('/api/income-transactions-next/<income_id>', methods=['GET'])
@app.route('/api/income-transactions-next', methods=['GET'])
def income_transactions_next(income_id=None):
    
    cursor = None
    
    if income_id!=None:

        cursor = income.find_one({
            'closed_at':None,
            'deleted_at':None,
            '_id':ObjectId(income_id)
        },{
            'earner':1,
            'gross_income':1,
            'net_income':1,
            'total_gross_income':1,
            'total_net_income':1,
            'pay_date':1,
            'next_pay_date':1,
            'repeat':1
            })


    else:

        cursor = income.find({
            'closed_at':None,
            'deleted_at':None
        },{
            'earner':1,
            'gross_income':1,
            'net_income':1,
            'total_gross_income':1,
            'total_net_income':1,
            'pay_date':1,
            'next_pay_date':1,
            'repeat':1
            })
    
    projection_list = []

    if income_id!=None:
        
        todo = cursor
        income_contribution = income_transactions_next_function(todo)
        projection_list.append(income_contribution)
    else:
        
        for todo in cursor:
            income_contribution = income_transactions_next_function(todo)
            projection_list.append(income_contribution)

    
    #print('projection_list',projection_list)

    

    # Optimized dictionary to store merged results
    merged_data = defaultdict(lambda: {
        "base_gross_income": 0,
        "base_net_income": 0,
        "month_word": "",
        "earners": []
    })

    # Merging logic with optimization
    for sublist in projection_list:
        for entry in sublist:
            month = entry['month']
            merged_entry = merged_data[month]

            # Accumulate income values directly
            merged_entry['base_gross_income'] += entry['base_gross_income']
            merged_entry['base_net_income'] += entry['base_net_income']
            # Append earner-specific data
            merged_entry['earners'].append({
                'earner': entry['earner'],
                'earner_id': entry['earner_id'],
                'gross_income': entry['base_gross_income'],
                'net_income': entry['base_net_income']
            })

            # Store the month word (assumes it's consistent for the same month)
            if not merged_entry['month_word']:
                merged_entry['month_word'] = entry['month_word']

    # Round values during final conversion to avoid redundant operations
    result = sorted(
        [
            {
                "month": month,
                "base_gross_income": round(data['base_gross_income'], 2),
                "base_net_income": round(data['base_net_income'], 2),
                "month_word": data['month_word'],
                "earners": data['earners']
            }
            for month, data in merged_data.items()
        ],
        key=lambda x: datetime.strptime(x['month'], "%Y-%m")
    )


        


    
    
    
    return jsonify({
        "payLoads":{            
            
               #'projection_list':result,
               #'projection_list_boost':result_boost,
               'projection_list':result
                     


        }        
    })
@app.route('/api/income-transactions-previous/<income_id>', methods=['GET'])
@app.route('/api/income-transactions-previous', methods=['GET'])
def income_transactions_previous(income_id=None):



    twelve_months_ago = datetime.now() - timedelta(days=365)

    match_query = {
        "pay_date": {"$gte": twelve_months_ago},
        "deleted_at": None,
        "closed_at":None,
    }
    if income_id!=None:
        match_query["income_id"] = ObjectId(income_id)

    pipeline = [
    # Step 1: Match documents with pay_date in the last 12 months and not deleted
    {
        "$match": match_query
    },
    
    # Step 2: Project to extract year and month from pay_date
    # {
    #     "$project": {
    #         "total_net_for_period": 1,
    #         "total_gross_for_period": 1,
    #         "month_word":1,
    #         "month":1            
    #     }
    # },

    # Step 3: Group by year_month and sum the balance
    # {
    #     "$group": {
    #         "_id": "$month",  # Group by the formatted month-year
    #         "total_balance_net": {"$max": "$total_net_for_period"},
    #         "total_balance_gross": {"$max": "$total_gross_for_period"},
    #         "month_word": {"$first": "$month_word"},  # Include the year
    #         "month": {"$first": "$month"}   # Include the month
    #     }
    # },

    {
        "$group": {
            "_id": { "month": "$month", "income_id": "$income_id" },
            "total_balance_net": { "$max": "$total_net_for_period" },
            #"total_balance_gross": { "$max": "$total_gross_for_period" },  # Max balance for each income_id in the month
            "month_word": { "$first": "$month_word" },                   # Include month_word for formatting
            "month": { "$first": "$month" }                              # Include month for further grouping
        }
    },

    # Step 4: Create the formatted year_month_word
    # {
    #     "$project": {
    #         "_id": 1,
    #         "total_balance_net": 1,
    #         "total_balance_gross":1,
    #         "month_word":1            
    #     }
    # },

    {
        "$group": {
            "_id": "$_id.month",  # Group by month
            "total_balance_net": { "$sum": "$total_balance_net" },  # Sum the max balances per income_id in the month
            "month_word": { "$first": "$month_word" },          # Keep month_word
            "month": { "$first": "$month" }                     # Keep month for sorting later
        }
    },

     {
        "$project": {
            "_id": 1,
            "total_balance_net": 1,
            "month_word": 1
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
            ##"total_count": {"$sum": 1},  # Count the number of months (or documents)
            #"total_balance_net": {"$sum": "$total_balance_net"},  # Sum all the 'total_balance' values from the grouped results
            #"total_balance_gross": {"$sum": "$total_balance_gross"},
            "grouped_results": {"$push": {  # Preserve all grouped results in an array
                #"year_month": "$_id",
                "year_month_word": "$month_word",
                "total_balance_net": "$total_balance_net",
                "total_balance_gross":"$total_balance_gross"
            }}
        }
    },

    # Step 8: Use $project to format the output
    {
        "$project": {
            "_id": 0,                           # Remove the _id field
            #"total_count": 1,                   # Include the total count
            #"total_balance_net": 1,
            #"total_balance_gross":1,                 # Include the total balance
            "grouped_results": 1                # Include the grouped results
        }
    }
        
    ]
    
    year_month_wise_all = list(collection.aggregate(pipeline))

    year_month_wise_counts = year_month_wise_all[0]['grouped_results'] if year_month_wise_all else []

    if len(year_month_wise_counts) > 0:
        data_json = MongoJSONEncoder().encode(year_month_wise_counts)
        year_month_wise_counts = json.loads(data_json)

    total_monthly_balance = 0    
    if income_id!=None:
        income_monthly_log_data = income_monthly_log.find_one({'income_id':ObjectId(income_id)})
        if income_monthly_log_data!=None:
            total_monthly_balance = income_monthly_log_data['total_monthly_net_income']

    return jsonify({
        "payLoads":{            
            
            "year_month_wise_counts":year_month_wise_counts,            
            "total_monthly_balance":total_monthly_balance

        }        
    })


@app.route('/api/income-boost-transactions-previous/<income_id>', methods=['GET'])
def income_boost_transactions_previous(income_id):



    twelve_months_ago = datetime.now() - timedelta(days=365)

    match_query = {
        "pay_date": {"$gte": twelve_months_ago},
        "deleted_at": None,
        "closed_at":None,
        "income_id":ObjectId(income_id)
    }    

    pipeline = [
    # Step 1: Match documents with pay_date in the last 12 months and not deleted
    {
        "$match": match_query
    },
    
    # Step 2: Project to extract year and month from pay_date
    {
        "$project": {
            "base_input_boost": 1,            
            "month_word":1,
            "month":1            
        }
    },

    # Step 3: Group by year_month and sum the balance
    {
        "$group": {
            "_id": "$month",  # Group by the formatted month-year
            "total_balance_net": {"$sum": "$base_input_boost"},            
            "month_word": {"$first": "$month_word"},  # Include the year
            "month": {"$first": "$month"}   # Include the month
        }
    },

    # Step 4: Create the formatted year_month_word
    {
        "$project": {
            "_id": 1,
            "total_balance_net": 1,           
            "month_word":1            
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
            ##"total_count": {"$sum": 1},  # Count the number of months (or documents)
            #"total_balance_net": {"$sum": "$total_balance_net"},  # Sum all the 'total_balance' values from the grouped results
            #"total_balance_gross": {"$sum": "$total_balance_gross"},
            "grouped_results": {"$push": {  # Preserve all grouped results in an array
                #"year_month": "$_id",
                "year_month_word": "$month_word",
                "total_balance_net": "$total_balance_net"                
            }}
        }
    },

    # Step 8: Use $project to format the output
    {
        "$project": {
            "_id": 0,                           # Remove the _id field
            #"total_count": 1,                   # Include the total count
            #"total_balance_net": 1,
            #"total_balance_gross":1,                 # Include the total balance
            "grouped_results": 1                # Include the grouped results
        }
    }
        
    ]
    
    year_month_wise_all = list(income_boost_transaction.aggregate(pipeline))

    year_month_wise_counts = year_month_wise_all[0]['grouped_results'] if year_month_wise_all else []

    if len(year_month_wise_counts) > 0:
        data_json = MongoJSONEncoder().encode(year_month_wise_counts)
        year_month_wise_counts = json.loads(data_json)

    total_monthly_balance = 0        
    income_boost_monthly_log_data = income_boost_monthly_log.find_one({'income_id':ObjectId(income_id)})
    if income_boost_monthly_log_data!=None:
        total_monthly_balance = income_boost_monthly_log_data['total_monthly_boost_income']

    return jsonify({
        "payLoads":{            
            
            "year_month_wise_counts":year_month_wise_counts,            
            "total_monthly_balance":total_monthly_balance

        }        
    })



@app.route('/api/income-transactions/<string:income_id>', methods=['POST'])
def list_income_transactions(income_id:str):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    #global_filter = data.get('filter', '')
    #sort_by = data.get('sortBy', [])

    # Construct MongoDB filter query
    query = {
        #'role':{'$gte':10}
        "income_id":ObjectId(income_id),
        "income_boost_id":{'$eq':None},
        "deleted_at":None,
        "closed_at":None,
    }
    # if global_filter:
        

    #     pattern_str = r'^\d{4}-\d{2}-\d{2}$'
    #     pay_date = None
        
    #     #try:
    #     if re.match(pattern_str, global_filter):
    #         pay_date = datetime.strptime(global_filter,"%Y-%m-%d")
            
    #     #except ValueError:
    #     else:
    #         pay_date = None
            

    #     query["$or"] = [
            
    #         #{"earner": {"$regex": global_filter, "$options": "i"}},            
    #         {"pay_date":pay_date},                                        
    #         # Add other fields here if needed
    #     ]

    # Construct MongoDB sort parameters
    sort_params = [
        ('pay_date',-1)
    ]
    cursor = collection.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
    # for sort in sort_by:
    #     sort_field = sort['id']
    #     sort_direction = -1 if sort['desc'] else 1
    #     sort_params.append((sort_field, sort_direction))

    # Fetch data from MongoDB
    # if sort_params:
    #     cursor = collection.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
    # else:
    #     # Apply default sorting or skip sorting
    #     cursor = collection.find(query).skip(page_index * page_size).limit(page_size)



    total_count = collection.count_documents(query)
    #data_list = list(cursor)
    data_list = []

    for todo in cursor:


        todo['pay_date_word'] = todo['pay_date'].strftime('%d %b, %Y')
        todo['pay_date'] = convertDateTostring(todo['pay_date'],"%Y-%m-%d")

        todo['next_pay_date_word'] = todo['next_pay_date'].strftime('%d %b, %Y')
        todo['next_pay_date'] = convertDateTostring(todo['next_pay_date'],"%Y-%m-%d")                

        


        data_list.append(todo)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size


    #total balance , interest, monthly intereset paid off
    # Aggregate query to sum the balance field
    # pipeline = [
    #     {"$match": query},  # Filter by user_id
    #     # {
    #     #     '$addFields': {
    #     #         'total_monthly_income': {'$add': ['$gross_income', '$income_boost']}
    #     #     }
    #     # },
    #     {"$group": {"_id": None, 
    #                 "total_net_income": {"$sum": "$base_net_income"},
    #                 "total_gross_income":{"$sum": "$base_gross_income"},                                                        
    #                 }}  # Sum the balance
    # ]

    # # Execute the aggregation pipeline
    # result = list(collection.aggregate(pipeline))

    #  # Extract the total balance from the result
    # total_net_income = result[0]['total_net_income'] if result else 0
    # total_gross_income = result[0]['total_gross_income'] if result else 0
    
    

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count,
        # 'extra_payload':{
        #     'total_net_income':total_net_income,
        #     'total_gross_income':total_gross_income,             
        # }
    })





@app.route('/api/income-boost-transactions/<string:income_id>', methods=['POST'])
def list_income_boost_transactions(income_id:str):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    #global_filter = data.get('filter', '')
    #sort_by = data.get('sortBy', [])

    # Construct MongoDB filter query
    query = {
        #'role':{'$gte':10}
        "income_id":ObjectId(income_id),
        "income_boost_id":{'$ne':None},
        "deleted_at":None,
        "closed_at":None,
    }
    # if global_filter:
        

    #     pattern_str = r'^\d{4}-\d{2}-\d{2}$'
    #     pay_date = None
        
    #     #try:
    #     if re.match(pattern_str, global_filter):
    #         pay_date = datetime.strptime(global_filter,"%Y-%m-%d")
            
    #     #except ValueError:
    #     else:
    #         pay_date = None
            

    #     query["$or"] = [
            
    #         #{"earner": {"$regex": global_filter, "$options": "i"}},            
    #         {"pay_date":pay_date},                                        
    #         # Add other fields here if needed
    #     ]

    # Construct MongoDB sort parameters
    sort_params = [
        ('pay_date',-1)
    ]
    cursor = collection.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
    # for sort in sort_by:
    #     sort_field = sort['id']
    #     sort_direction = -1 if sort['desc'] else 1
    #     sort_params.append((sort_field, sort_direction))

    # Fetch data from MongoDB
    # if sort_params:
    #     cursor = collection.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
    # else:
    #     # Apply default sorting or skip sorting
    #     cursor = collection.find(query).skip(page_index * page_size).limit(page_size)



    total_count = collection.count_documents(query)
    #data_list = list(cursor)
    data_list = []

    for todo in cursor:

        income_boost_ac = income_boost.find_one({'_id':todo['income_boost_id']})

        todo['income_boost'] = income_boost_ac['earner'] if income_boost_ac!=None else None

        todo['contribution'] = todo['gross_income']
        todo['total_balance'] = todo['total_gross_for_period']
        todo['contribution_date_word'] = convertDateTostring(todo['pay_date'])
        todo['contribution_date'] = convertDateTostring(todo['pay_date'],"%Y-%m-%d")

        todo['next_pay_date_word'] = convertDateTostring(todo['next_pay_date'])
        todo['next_pay_date_boost'] = convertDateTostring(todo['next_pay_date'],"%Y-%m-%d")                

        


        data_list.append(todo)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size


    #total balance , interest, monthly intereset paid off
    # Aggregate query to sum the balance field
    # pipeline = [
    #     {"$match": query},  # Filter by user_id
    #     # {
    #     #     '$addFields': {
    #     #         'total_monthly_income': {'$add': ['$gross_income', '$income_boost']}
    #     #     }
    #     # },
    #     {"$group": {"_id": None, 
    #                 "total_net_income": {"$sum": "$base_net_income"},
    #                 "total_gross_income":{"$sum": "$base_gross_income"},                                                        
    #                 }}  # Sum the balance
    # ]

    # # Execute the aggregation pipeline
    # result = list(collection.aggregate(pipeline))

    #  # Extract the total balance from the result
    # total_net_income = result[0]['total_net_income'] if result else 0
    # total_gross_income = result[0]['total_gross_income'] if result else 0
    
    

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count,
        # 'extra_payload':{
        #     'total_net_income':total_net_income,
        #     'total_gross_income':total_gross_income,             
        # }
    })




