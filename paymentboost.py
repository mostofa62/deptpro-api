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
collection = my_col('payment_boost')

@app.route('/api/boosts/<string:user_id>', methods=['POST'])
def list_boosts(user_id:str):
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

        

        query["$or"] = [
            
            {"month.label": {"$regex": global_filter, "$options": "i"}},
            {"year.value": {"$regex": global_filter, "$options": "i"}},
            {"amount": {"$regex": global_filter, "$options": "i"}},            
                           
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
        todo['billing_month_year'] = f"{todo['month']['label']}, {todo['year']['value']}"
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


@app.route('/api/save-boost', methods=['POST'])
async def save_boost():
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']
        

        boost_id = None
        message = ''
        result = 0
        try:

            

           

            append_data = {
                

                'user_id':ObjectId(user_id),

                
                "created_at":datetime.now(),
                "updated_at":datetime.now(),
                "deleted_at":None,

                               
                

                
            }
            #print('data',data)
            #print('appendata',append_data)            

            merge_data = data | append_data

            del merge_data['id']

            #print('mergedata',merge_data)

            boost_data = collection.insert_one(merge_data)
            boost_id = str(boost_data.inserted_id)
            result = 1 if boost_id!=None else 0
            message = 'Payment Boost account added Succefull'
        except Exception as ex:
            boost_id = None
            print('Payment Boost Save Exception: ',ex)
            result = 0
            message = 'Payment Boost account addition Failed'

        return jsonify({
            "boost_id":boost_id,
            "message":message,
            "result":result
        })



@app.route('/api/update-boost', methods=['POST'])
async def update_boost():
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']
        

        boost_id = data['id']
        message = ''
        result = 0
        try:

     
            append_data = {
                'user_id':ObjectId(user_id),                
                "updated_at":datetime.now(),                               
            }                     

            merge_data = data | append_data

            del merge_data['id']

            query = {
                '_id':ObjectId(boost_id)
            }

            newvalues = { "$set": merge_data }

            

            #print('mergedata',merge_data)

            boost_data = collection.update_one(query,newvalues)            
            result = 1 if boost_data.modified_count!=None else 0
            message = 'Payment Boost account updated Succefull'
        except Exception as ex:
            boost_id = None
            print('Payment Boost updated Exception: ',ex)
            result = 0
            message = 'Payment Boost account update Failed'

        return jsonify({
            "boost_id":boost_id,
            "message":message,
            "result":result
        })



@app.route('/api/delete-boost', methods=['POST'])
def delete_boost():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']

        boost_account_id = None
        message = None
        error = 0
        deleted_done = 0

        try:
            myquery = { "_id" :ObjectId(id)}

            newvalues = { "$set": {                                     
                "deleted_at":datetime.now()                
            } }
            boost_account_data =  collection.update_one(myquery, newvalues)
            boost_account_id = id if boost_account_data.modified_count else None
            error = 0 if boost_account_data.modified_count else 1
            deleted_done = 1 if boost_account_data.modified_count else 0
            message = 'Payment Boost account Deleted Successfully'if boost_account_data.modified_count else 'Payment Boost account Deletion Failed'

        except Exception as ex:
            boost_account_id = None
            print('Payment Boost account Save Exception: ',ex)
            message = 'Payment Boost account Deletion Failed'
            error  = 1
            deleted_done = 0
        
        return jsonify({
            "boost_account_id":boost_account_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })
