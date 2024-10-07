from collections import defaultdict
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

collection = my_col('saving_contributions')


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