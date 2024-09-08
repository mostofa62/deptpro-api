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

            

            pay_date = convertStringTodate(data['pay_date'])
            pay_date_boost = convertStringTodate(data['pay_date_boost'])                        
            next_pay_date = calculate_next_payment(pay_date, data['repeat']['value']) 
            next_boost_date = calculate_next_payment(pay_date_boost, data['repeat_boost']['value'])            
            #print(next_boost_date)

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
            next_pay_date = calculate_next_payment(pay_date, data['repeat']['value']) 
            next_boost_date = calculate_next_payment(pay_date_boost, data['repeat_boost']['value'])            

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
                'next_pay_date':next_pay_date,
                'next_boost_date':next_boost_date                   
                

                
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