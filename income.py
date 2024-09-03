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

        #debt type filter
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
        income_source_id = todo['income_source']['value']
        income_source_type = my_col('income_source_types').find_one(
        {"_id":income_source_id},
        {"_id":0,"name":1}
        )
        todo['income_source'] =  income_source_type['name']


        income_boost_id = todo['income_boost_source']['value']
        income_boost_type = my_col('income_boost_types').find_one(
        {"_id":income_boost_id},
        {"_id":0,"name":1}
        )
        todo['income_boost_source'] =  income_boost_type['name']

        todo['pay_date'] = convertDateTostring(todo['pay_date'])

        todo['pay_date_boost'] = convertDateTostring(todo['pay_date_boost'])
        


        data_list.append(todo)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size


    #total balance , interest, monthly intereset paid off
    # Aggregate query to sum the balance field
    pipeline = [
        {"$match": query},  # Filter by user_id
        {"$group": {"_id": None, 
                    "total_monthly_net_income": {"$sum": "$monthly_net_income"},
                    "total_monthly_gross_income":{"$sum": "$monthly_gross_income"}                   
                    }}  # Sum the balance
    ]

    # Execute the aggregation pipeline
    result = list(collection.aggregate(pipeline))

     # Extract the total balance from the result
    total_monthly_net_income = result[0]['total_monthly_net_income'] if result else 0
    total_monthly_gross_income = result[0]['total_monthly_gross_income'] if result else 0
    

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count,
        'extra_payload':{
            'total_monthly_net_income':total_monthly_net_income,
            'total_monthly_gross_income':total_monthly_gross_income            
        }
    })


def newEntryOptionData(data_obj:any, collectionName:str, user_id:str):
    if '__isNew__' in data_obj:
        collecObj =  my_col(collectionName).insert_one({
            'name':data_obj['label'],
            'user_id':ObjectId(user_id)
        })

        if collecObj.inserted_id != None:
            return {'value': collecObj.inserted_id}
    else:
        return {'value': ObjectId(data_obj['value'])}



@app.route('/api/save-income-account', methods=['POST'])
async def save_income():
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']

        income_id = None
        message = ''
        result = 0
        try:

            

            pay_date = convertStringTodate(data['pay_date'])
            pay_date_boost = convertStringTodate(data['pay_date_boost'])            

            append_data = {
                'income_source':newEntryOptionData(data['income_source'],'income_source_types',user_id),
                'income_boost_source':newEntryOptionData(data['income_boost_source'],'income_boost_types',user_id),                

                'user_id':ObjectId(user_id),

                'monthly_net_income':float(data.get("monthly_net_income", 0)),
                'monthly_gross_income':float(data.get("monthly_gross_income", 0)),
                
                "created_at":datetime.now(),
                "updated_at":datetime.now(),
                "deleted_at":None,

                'pay_date':pay_date,
                'pay_date_boost':pay_date_boost,                
                

                
            }
            #print('data',data)
            #print('appendata',append_data)            

            merge_data = data | append_data

            #print('mergedata',merge_data)

            income_data = my_col('income').insert_one(merge_data)
            income_id = str(income_data.inserted_id)
            result = 1 if income_id!=None else 0
            message = 'Income account added Succefull'
        except Exception as ex:
            income_id = None
            print('Income Save Exception: ',ex)
            result = 0
            message = 'Income account addition Failed'

        return jsonify({
            "income_id":income_id,
            "message":message,
            "result":result
        })