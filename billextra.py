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
collection = my_col('bill_extra')


extra_type = [
    {'value':1, 'label':'Paydown Boost'},
    {'value':2, 'label':'Debt Purchase'},
    {'value':3, 'label':'WithDrawl'},
    {'value':4, 'label':'Bill Purchase'},

]

@app.route('/api/bill-extra-dropdown', methods=['GET'])
def bill_extra_dropdown():

    return jsonify({
        'extra_type': extra_type        
        
    })

@app.route('/api/bill-extras/<string:user_id>', methods=['POST'])
def list_extras(user_id:str):
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

        pattern_str = r'^\d{4}-\d{2}-\d{2}$'
        pay_date_extra = None        
        #try:
        if re.match(pattern_str, global_filter):
            pay_date_extra = datetime.strptime(global_filter,"%Y-%m-%d")            
        #except ValueError:
        else:
            pay_date_extra = None

        

        query["$or"] = [
            
            {"pay_date_extra":pay_date_extra},
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
        #todo['billing_month_year'] = f"{todo['month']['label']}, {todo['year']['value']}"
        todo['pay_date_extra_word'] = todo['pay_date_extra'].strftime('%d %b, %Y') 
        todo['pay_date_extra'] = convertDateTostring(todo['pay_date_extra'],'%Y-%m-%d') 
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


@app.route('/api/save-bill-extra', methods=['POST'])
async def save_extra():
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']
        

        extra_id = None
        message = ''
        result = 0
        try:

            

           
            pay_date_extra = convertStringTodate(data['pay_date_extra'])
            month = convertDateTostring(pay_date_extra,"%b %Y") 
            append_data = {
                

                'user_id':ObjectId(user_id),
                'pay_date_extra':pay_date_extra,
                'month':month,
                "created_at":datetime.now(),
                "updated_at":datetime.now(),
                "deleted_at":None,

                               
                

                
            }
            #print('data',data)
            #print('appendata',append_data)            

            merge_data = data | append_data

            del merge_data['id']

            #print('mergedata',merge_data)

            extra_data = collection.insert_one(merge_data)
            extra_id = str(extra_data.inserted_id)
            result = 1 if extra_id!=None else 0
            message = 'Bill Extra account added Succefull'
        except Exception as ex:
            extra_id = None
            print('Bill Extra Save Exception: ',ex)
            result = 0
            message = 'Bill Extra account addition Failed'

        return jsonify({
            "extra_id":extra_id,
            "message":message,
            "result":result
        })



@app.route('/api/update-bill-extra', methods=['POST'])
async def update_extra():
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']
        

        extra_id = data['id']
        message = ''
        result = 0
        try:
            pay_date_extra = convertStringTodate(data['pay_date_extra']) 
     
            append_data = {
                'user_id':ObjectId(user_id),
                'pay_date_extra':pay_date_extra,                
                "updated_at":datetime.now(),                               
            }                     

            merge_data = data | append_data

            del merge_data['id']

            query = {
                '_id':ObjectId(extra_id)
            }

            newvalues = { "$set": merge_data }

            

            #print('mergedata',merge_data)

            extra_data = collection.update_one(query,newvalues)            
            result = 1 if extra_data.modified_count!=None else 0
            message = 'Bill Extra account updated Succefull'
        except Exception as ex:
            extra_id = None
            print('Bill Extra updated Exception: ',ex)
            result = 0
            message = 'Bill Extra account update Failed'

        return jsonify({
            "extra_id":extra_id,
            "message":message,
            "result":result
        })



@app.route('/api/delete-extra', methods=['POST'])
def delete_extra():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']

        extra_account_id = None
        message = None
        error = 0
        deleted_done = 0

        try:
            myquery = { "_id" :ObjectId(id)}

            newvalues = { "$set": {                                     
                "deleted_at":datetime.now()                
            } }
            extra_account_data =  collection.update_one(myquery, newvalues)
            extra_account_id = id if extra_account_data.modified_count else None
            error = 0 if extra_account_data.modified_count else 1
            deleted_done = 1 if extra_account_data.modified_count else 0
            message = 'Bill Extra account Deleted Successfully'if extra_account_data.modified_count else 'Bill Extra account Deletion Failed'

        except Exception as ex:
            extra_account_id = None
            print('Bill Extra account Save Exception: ',ex)
            message = 'Bill Extra account Deletion Failed'
            error  = 1
            deleted_done = 0
        
        return jsonify({
            "extra_account_id":extra_account_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })
