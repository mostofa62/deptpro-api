from collections import defaultdict
import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from incomeutil import generate_new_transaction_data_for_future_income, generate_new_transaction_data_for_future_income_boost, generate_new_transaction_data_for_income, generate_unique_id
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
app_data = my_col('app_data')
@app.route('/api/income-transactions-next/<income_id>', methods=['GET'])
def income_transactions_next_one(income_id):


    current_month = datetime.now().strftime('%Y-%m')
    income_monthly_log_data = income_monthly_log.find_one({
        'income_id':ObjectId(income_id)
    })
    total_monthly_net_income = income_monthly_log_data['total_monthly_net_income'] if  income_monthly_log_data!=None and 'total_monthly_net_income' in income_monthly_log_data else 0
    total_monthly_gross_income = income_monthly_log_data['total_monthly_gross_income'] if  income_monthly_log_data!=None and 'total_monthly_gross_income' in income_monthly_log_data else 0    

    projection_list = []
    todo = income.find_one({
        'closed_at':None,
        'deleted_at':None,
        '_id':ObjectId(income_id)
    },{
        'gross_income':1,
        'net_income':1,
        'pay_date':1,
        'next_pay_date':1,
        'repeat':1
        })
    
    if todo !=None:
        income_transaction_data = generate_new_transaction_data_for_future_income(

            gross_input=todo['gross_income'],
            net_input=todo['net_income'],
            pay_date=todo['next_pay_date'],
            frequency=todo['repeat']['value']
        )
        income_transaction = income_transaction_data['income_transaction']

        projection_list.append(income_transaction)

    # Dictionary to store merged results
    merged_data = defaultdict(lambda: {
        "base_gross_income": 0,
        "base_net_income": 0,
        #"total_gross_for_period": 0,
        #"total_net_for_period": 0,
        "month_word": ""
    })

    # Merging logic
    if len(projection_list) > 0:
        for sublist in projection_list:
            for entry in sublist:
                
                month = entry['month']                
                if month == current_month:
                    merged_data[month]['base_gross_income'] = round(total_monthly_gross_income,2)
                    merged_data[month]['base_net_income'] = round(total_monthly_net_income,2)
                #merged_data[month]['id'] = ObjectId()
                merged_data[month]['base_gross_income'] += round(entry['base_gross_income'],2)
                merged_data[month]['base_net_income'] += round(entry['base_net_income'],2)
                #merged_data[month]['total_gross_for_period'] += entry['total_gross_for_period']
                #merged_data[month]['total_net_for_period'] += entry['total_net_for_period']
                merged_data[month]['month_word'] = entry['month_word']

                merged_data[month]['base_gross_income'] = round(merged_data[month]['base_gross_income'],2)
                merged_data[month]['base_net_income']  = round(merged_data[month]['base_net_income'] ,2)

            #merged_data[month]['id'] = generate_unique_id(month)


    # Convert the merged data back into a list if needed
    result = [{"month": month, **data} for month, data in merged_data.items()]

    return jsonify({
        "payLoads":{            
            
               #'projection_list':result,
               #'projection_list_boost':result_boost,
               'projection_list':result
                     


        }        
    })


@app.route('/api/income-transactions-next-all/<user_id>', methods=['GET'])
def income_transactions_next(user_id:str):



    #twelve_months_next = datetime.now() + timedelta(days=365)

    

    # query = {
    #     "pay_date": {"$eq": pay_date},
    # }

    #income and incomeboost
    current_month = datetime.now().strftime('%Y-%m')
    app_datas = app_data.find_one({'user_id':ObjectId(user_id)})    

    total_monthly_net_income = app_datas['total_current_net_income'] if  app_datas!=None and 'total_current_net_income' in app_datas else 0
    total_monthly_gross_income = app_datas['total_current_gross_income'] if  app_datas!=None and 'total_current_gross_income' in app_datas else 0

    cursor = income.find({
        'closed_at':None,
        'deleted_at':None
    },{
        'gross_income':1,
        'net_income':1,
        'pay_date':1,
        'next_pay_date':1,
        'repeat':1
        })
    
    projection_list = []

    for todo in cursor:
        
        income_transaction_data = generate_new_transaction_data_for_future_income(

            gross_input=todo['gross_income'],
            net_input=todo['net_income'],
            pay_date=todo['next_pay_date'],
            frequency=todo['repeat']['value']
        )
        income_transaction = income_transaction_data['income_transaction']

        projection_list.append(income_transaction)

    
    # Dictionary to store merged results
    merged_data = defaultdict(lambda: {
        "base_gross_income": 0,
        "base_net_income": 0,
        #"total_gross_for_period": 0,
        #"total_net_for_period": 0,
        "month_word": ""
    })

    # Merging logic
    for sublist in projection_list:
        for entry in sublist:
            
            month = entry['month']
            if month == current_month:
                merged_data[month]['base_gross_income'] = round(total_monthly_gross_income+entry['base_gross_income'],2)
                merged_data[month]['base_net_income'] = round(total_monthly_net_income+entry['base_net_income'],2)
                
            #merged_data[month]['id'] = ObjectId()
            merged_data[month]['base_gross_income'] += round(entry['base_gross_income'],2)
            merged_data[month]['base_net_income'] += round(entry['base_net_income'],2)
            #merged_data[month]['total_gross_for_period'] += entry['total_gross_for_period']
            #merged_data[month]['total_net_for_period'] += entry['total_net_for_period']
            merged_data[month]['month_word'] = entry['month_word']

            merged_data[month]['base_gross_income'] = round(merged_data[month]['base_gross_income'],2)
            merged_data[month]['base_net_income']  = round(merged_data[month]['base_net_income'] ,2)

            #merged_data[month]['id'] = generate_unique_id(month)


    # Convert the merged data back into a list if needed
    result = [{"month": month, **data} for month, data in merged_data.items()]


    cursor = income_boost.find({
        'closed_at':None,
        'deleted_at':None
    },{
        'income_boost':1,
        'pay_date_boost':1,
        'next_pay_date_boost':1,
        'repeat_boost':1
        })
    
    projection_list_boost = []

    for todo in cursor:

        income_transaction_data = generate_new_transaction_data_for_future_income_boost(

            input_boost=todo['income_boost'],        
            pay_date=todo['next_pay_date_boost'],
            frequency=todo['repeat_boost']['value']
        )
        income_transaction = income_transaction_data['income_transaction']

        projection_list_boost.append(income_transaction)


    # Dictionary to store merged results
    merged_data_boost = defaultdict(lambda: {
        "base_input_boost": 0,
       
        #"total_gross_for_period": 0,
        #"total_net_for_period": 0,
        "month_word": ""
    })

    # Merging logic
    for sublist in projection_list_boost:
        for entry in sublist:
            
            month = entry['month']
            #merged_data[month]['id'] = ObjectId()
            merged_data_boost[month]['base_input_boost'] += round(entry['base_input_boost'],2)
            
            merged_data_boost[month]['month_word'] = entry['month_word']

            merged_data_boost[month]['base_input_boost'] = round(merged_data_boost[month]['base_input_boost'],2)
            

            #merged_data[month]['id'] = generate_unique_id(month)


    # Convert the merged data back into a list if needed
    result_boost = [{"month": month, **data} for month, data in merged_data_boost.items()]

    # Default fields with values 0
    default_fields = {
        "base_gross_income": 0.0,
        "base_net_income": 0.0,
        "base_input_boost": 0.0,
    }

    combined_dict = {item["month"]: {**default_fields, **item} for item in result}

    for boost_item in result_boost:
        month = boost_item["month"]
        if month in combined_dict:
            combined_dict[month].update(boost_item)  # Merge data if 'month' exists
        else:
            combined_dict[month] = {**default_fields, **boost_item}

    # Convert back to list format
    merged_list = list(combined_dict.values())
    
    
    return jsonify({
        "payLoads":{            
            
               #'projection_list':result,
               #'projection_list_boost':result_boost,
               'projection_list':merged_list
                     


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
    {
        "$project": {
            "base_net_income": 1,
            "base_gross_income": 1,
            "month_word":1,
            "month":1            
        }
    },

    # Step 3: Group by year_month and sum the balance
    {
        "$group": {
            "_id": "$month",  # Group by the formatted month-year
            "total_balance_net": {"$sum": "$base_net_income"},
            "total_balance_gross": {"$sum": "$base_gross_income"},
            "month_word": {"$first": "$month_word"},  # Include the year
            "month": {"$first": "$month"}   # Include the month
        }
    },

    # Step 4: Create the formatted year_month_word
    {
        "$project": {
            "_id": 1,
            "total_balance_net": 1,
            "total_balance_gross":1,
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
    cursor = income_boost_transaction.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
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



    total_count = income_boost_transaction.count_documents(query)
    #data_list = list(cursor)
    data_list = []

    for todo in cursor:


        todo['pay_date_word'] = todo['pay_date'].strftime('%d %b, %Y')
        todo['pay_date'] = convertDateTostring(todo['pay_date'],"%Y-%m-%d")

        todo['next_pay_date_word'] = todo['next_pay_date_boost'].strftime('%d %b, %Y')
        todo['next_pay_date_boost'] = convertDateTostring(todo['next_pay_date_boost'],"%Y-%m-%d")                

        


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




