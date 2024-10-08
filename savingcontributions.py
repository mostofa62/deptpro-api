from collections import defaultdict
import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin

from savingutil import calculate_breakdown, calculate_breakdown_future
from app import app
from db import my_col,myclient
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal

collection = my_col('saving_contributions')
saving = my_col('saving')

@app.route('/api/saving-contributions-next', methods=['GET'])
def saving_contributions_next():



    #twelve_months_next = datetime.now() + timedelta(days=365)

    

    # query = {
    #     "pay_date": {"$eq": pay_date},
    # }

    cursor = saving.find({
        'closed_at':None,
        'deleted_at':None,
        'goal_reached':None,
        'next_contribution_date':{'$ne':None}
    },{
        'total_balance':1,
        'starting_amount':1,
        'interest':1,
        'contribution':1,
        'goal_amount':1,
        'goal_reached':1,
        'next_contribution_date':1,
        'repeat':1
        })
    
    projection_list = []

    for todo in cursor:        

        saving_contribution_data = calculate_breakdown_future(

            initial_amount=todo['total_balance'],
            contribution=todo['contribution'],
            annual_interest_rate=todo['interest'],
            start_date = todo['next_contribution_date'],
            goal_amount = todo['goal_amount'],
            frequency=todo['repeat']['value']
        )
        saving_contribution = saving_contribution_data['breakdown']

        projection_list.append(saving_contribution)

    
    # Dictionary to store merged results
    merged_data = defaultdict(lambda: {
        "total_balance": 0,
        "contribution": 0,
        #"total_gross_for_period": 0,
        #"total_net_for_period": 0,
        "month_word": ""
    })

    # Merging logic
    for sublist in projection_list:
        for entry in sublist:
            
            month = entry['month']
            #merged_data[month]['id'] = ObjectId()
            merged_data[month]['total_balance'] += round(entry['total_balance'],2)
            merged_data[month]['contribution'] += round(entry['contribution'],2)
            #merged_data[month]['total_gross_for_period'] += entry['total_gross_for_period']
            #merged_data[month]['total_net_for_period'] += entry['total_net_for_period']
            merged_data[month]['month_word'] = entry['month_word']

            merged_data[month]['total_balance'] = round(merged_data[month]['total_balance'],2)
            merged_data[month]['contribution']  = round(merged_data[month]['contribution'] ,2)

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



@app.route('/api/saving-contributions-previous', methods=['GET'])
def saving_contributions_previous():



    twelve_months_ago = datetime.now() - timedelta(days=365)

    pipeline = [
    # Step 1: Match documents with contribution_date in the last 12 months and not deleted
    {
        "$match": {
            "contribution_date": {"$gte": twelve_months_ago},
            "deleted_at": None,
            "closed_at":None
        }
    },
    
    # Step 2: Project to extract year and month from contribution_date
    {
        "$project": {
            "total_balance": 1,
            "contribution": 1,
            "month_word":1,
            "month":1            
        }
    },

    # Step 3: Group by year_month and sum the balance
    {
        "$group": {
            "_id": "$month",  # Group by the formatted month-year
            "total_balance": {"$sum": "$total_balance"},
            "total_contribution": {"$sum": "$contribution"},
            "month_word": {"$first": "$month_word"},  # Include the year
            "month": {"$first": "$month"}   # Include the month
        }
    },

    # Step 4: Create the formatted year_month_word
    {
        "$project": {
            "_id": 1,
            "total_balance": 1,
            "total_contribution":1,
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
                "total_balance": "$total_balance",
                "total_contribution":"$total_contribution"
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

    return jsonify({
        "payLoads":{            
            
            "year_month_wise_counts":year_month_wise_counts,            


        }        
    })




@app.route('/api/saving-contributions/<string:saving_id>', methods=['POST'])
def list_saving_contributions(saving_id:str):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    #global_filter = data.get('filter', '')
    #sort_by = data.get('sortBy', [])

    # Construct MongoDB filter query
    query = {
        #'role':{'$gte':10}
        "saving_id":ObjectId(saving_id),
        "deleted_at":None,
        "closed_at":None,        
    }
    # if global_filter:
        

    #     pattern_str = r'^\d{4}-\d{2}-\d{2}$'
    #     contribution_date = None
        
    #     #try:
    #     if re.match(pattern_str, global_filter):
    #         contribution_date = datetime.strptime(global_filter,"%Y-%m-%d")
            
    #     #except ValueError:
    #     else:
    #         contribution_date = None
            

    #     query["$or"] = [
            
    #         #{"earner": {"$regex": global_filter, "$options": "i"}},            
    #         {"contribution_date":contribution_date},                                        
    #         # Add other fields here if needed
    #     ]

    # Construct MongoDB sort parameters
    sort_params = [
        ('contribution_date',1)
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


        todo['contribution_date_word'] = todo['contribution_date'].strftime('%d %b, %Y')
        todo['contribution_date'] = convertDateTostring(todo['contribution_date'],"%Y-%m-%d")

        todo['next_contribution_date_word'] = todo['next_contribution_date'].strftime('%d %b, %Y')
        todo['next_contribution_date'] = convertDateTostring(todo['next_contribution_date'],"%Y-%m-%d")                

        


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
    #     #         'total_monthly_saving': {'$add': ['$gross_saving', '$saving_boost']}
    #     #     }
    #     # },
    #     {"$group": {"_id": None, 
    #                 "total_net_saving": {"$sum": "$base_net_saving"},
    #                 "total_gross_saving":{"$sum": "$base_gross_saving"},                                                        
    #                 }}  # Sum the balance
    # ]

    # # Execute the aggregation pipeline
    # result = list(collection.aggregate(pipeline))

    #  # Extract the total balance from the result
    # total_net_saving = result[0]['total_net_saving'] if result else 0
    # total_gross_saving = result[0]['total_gross_saving'] if result else 0
    
    

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count,
        # 'extra_payload':{
        #     'total_net_saving':total_net_saving,
        #     'total_gross_saving':total_gross_saving,             
        # }
    })