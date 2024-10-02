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
collection = my_col('income_boost')
income_boost_types = my_col('income_boost_types')




@app.route('/api/delete-income-boost', methods=['POST'])
def delete_income_boost():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']

        income_boost_id = None
        message = None
        error = 0
        deleted_done = 0

        try:
            myquery = { "_id" :ObjectId(id)}

            newvalues = { "$set": {                                     
                "deleted_at":datetime.now()                
            } }
            income_boost_data =  collection.update_one(myquery, newvalues)
            income_boost_id = id if income_boost_data.modified_count else None
            error = 0 if income_boost_data.modified_count else 1
            deleted_done = 1 if income_boost_data.modified_count else 0
            message = 'Income boost Deleted Successfully'if income_boost_data.modified_count else 'Income boost Deletion Failed'

        except Exception as ex:
            income_boost_id = None
            print('Income boost Save Exception: ',ex)
            message = 'Income boost Deletion Failed'
            error  = 1
            deleted_done = 0
        
        return jsonify({
            "income_boost_id":income_boost_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })


@app.route("/api/income-boost-all/<string:id>", methods=['GET'])
def get_income_boost_all(id:str):
    income = collection.find_one(
        {"_id":ObjectId(id)},
        {"_id":0}
        )
    
    income['pay_date_boost_word'] = income['pay_date_boost'].strftime('%d %b, %Y')
    income['pay_date_boost'] = convertDateTostring(income['pay_date_boost'],"%Y-%m-%d")
    income['user_id'] = str(income['user_id'])

    
    

    
    income['repeat_boost'] = income['repeat_boost']['label']

    
    income_boost_type = income_boost_types.find_one(
        {"_id":income['income_boost_source']['value']},
        {"_id":0,"name":1}
        )
    
    
    income['income_boost_source'] = income_boost_type['name']
    

    return jsonify({
        "payLoads":{
            "income":income
        }
    })

@app.route("/api/income-boost/<string:id>", methods=['GET'])
def view_income_boost(id:str):
    income = collection.find_one(
        {"_id":ObjectId(id)},
        {"_id":0}
        )
    
    
    
    income['pay_date_boost'] = convertDateTostring(income['pay_date_boost'],"%Y-%m-%d")
    income['user_id'] = str(income['user_id'])

    
    income_boost_type = income_boost_types.find_one(
        {"_id":income['income_boost_source']['value']},
        {"_id":0,"name":1}
        )
    
    income['income_boost_source']['value'] = str(income['income_boost_source']['value'])
    income['income_boost_source']['label'] = income_boost_type['name']
    

    return jsonify({
        "income":income
    })

@app.route('/api/income-boost/<string:user_id>', methods=['POST'])
def list_income_boost(user_id:str):
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
        income_boost_type = income_boost_types.find(
                {'name':{"$regex":global_filter,"$options":"i"}},
                {'_id':1}
            )
        income_boost_types_list = list(income_boost_type)
        income_boost_types_id_list = [d.pop('_id') for d in income_boost_types_list]

        pattern_str = r'^\d{4}-\d{2}-\d{2}$'
        
        pay_date_boost = None
        #try:
        if re.match(pattern_str, global_filter):
            
            pay_date_boost = datetime.strptime(global_filter,"%Y-%m-%d")
        #except ValueError:
        else:
            
            pay_date_boost = None

        query["$or"] = [
            
            {"earner": {"$regex": global_filter, "$options": "i"}},            
            
            {"pay_date_boost":pay_date_boost},
            {"income_boost_source.value": {"$in":income_boost_types_id_list}},                 
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
        

        if todo['income_boost_source']!=None:
            income_boost_id = todo['income_boost_source']['value']
            income_boost_type = income_boost_types.find_one(
            {"_id":income_boost_id},
            {"_id":0,"name":1}
            )
            todo['income_boost_source'] =  income_boost_type['name']

        

        

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
        # {
        #     '$addFields': {
        #         'total_monthly_income': {'$add': ['$monthly_gross_income', '$income_boost']}
        #     }
        # },
        {"$group": {"_id": None, 
                    
                    "total_income_boost" :{"$sum": "$income_boost"},
                                      
                    }}  # Sum the balance
    ]

    # Execute the aggregation pipeline
    result = list(collection.aggregate(pipeline))

     # Extract the total balance from the result
    
    
    total_income_boost = result[0]['total_income_boost'] if result else 0
    

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count,
        'extra_payload':{
           
            'total_income_boost':total_income_boost,
                     
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



@app.route('/api/save-income-boost/<string:id>', methods=['POST'])
async def update_income_boost(id:str):
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']

        income_id = None
        message = ''
        result = 0
        try:

            
            income_boost = float(data.get("income_boost", 0))
            
            #repeat_boost = data['repeat_boost']['value'] if data['repeat_boost']['value'] > 0 else None

            
            

            
            pay_date_boost = convertStringTodate(data['pay_date_boost'])                        
           

            append_data = {
                
                'income_boost_source':newEntryOptionData(data['income_boost_source'],'income_boost_types',user_id),                

                'user_id':ObjectId(user_id),

                
                'income_boost':income_boost,

                
                "created_at":datetime.now(),
                "updated_at":datetime.now(),
                "deleted_at":None,

                
                'pay_date_boost':pay_date_boost,                             
                                
                

                
            }
            #print('data',data)
            #print('appendata',append_data)            

            merge_data = data | append_data

            print('mergedata',merge_data)

            myquery = { "_id" :ObjectId(id)}

            newvalues = { "$set": merge_data }

            income_data = collection.update_one(myquery, newvalues)
            income_id = id if income_data.modified_count else None
            result = 1 if income_data.modified_count else 0
            message = 'Income boost updated Succefull'
        except Exception as ex:
            income_id = None
            print('Income Update Exception: ',ex)
            result = 0
            message = 'Income boost update Failed'

        return jsonify({
            "income_id":income_id,
            "message":message,
            "result":result
        })
    



@app.route('/api/save-income-boost', methods=['POST'])
async def save_income_boost():
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']

        income_id = None
        message = ''
        result = 0
        
        try:

            
            income_boost = float(data.get("income_boost", 0))                    
            #repeat_boost = data['repeat_boost']['value'] if data['repeat_boost']['value'] > 0 else None


            

            
            pay_date_boost = convertStringTodate(data['pay_date_boost'])                        
            

            append_data = {                        
                'income_boost_source':newEntryOptionData(data['income_boost_source'],'income_boost_types',user_id),                

                'user_id':ObjectId(user_id),

                
                'income_boost':income_boost,

                
                
                "created_at":datetime.now(),
                "updated_at":datetime.now(),
                "deleted_at":None,

                
                'pay_date_boost':pay_date_boost,                
                                
                

                
            }
            #print('data',data)
            #print('appendata',append_data)            

            merge_data = data | append_data

            #print('mergedata',merge_data)

            income_data = collection.insert_one(merge_data)
            income_id = str(income_data.inserted_id)

            


            result = 1 if income_id!=None else 0
            message = 'Income boost added Succefull'
            
        except Exception as ex:
            income_id = None
            print('Income Save Exception: ',ex)
            result = 0
            message = 'Income boost addition Failed'
                   

        return jsonify({
            "income_id":income_id,
            "message":message,
            "result":result
        })
    


@app.route('/api/income-boost-typewise-info', methods=['GET'])
def get_typewise_income_boost_info():

    # Fetch the income type cursor
    income_type_cursor = income_boost_types.find(
        {"deleted_at": None},
        {'_id': 1, 'name': 1}
    )

    # Create a list of _id values
    incometype_id_list = [item['_id'] for item in income_type_cursor]


    pipeline = [
        # Step 1: Match documents with income_boost.value in billtype_id_list
        {
            "$match": {
                "income_boost_source.value": {"$in": incometype_id_list},
                "deleted_at": None
            }
        },

        # Step 2: Lookup to join income_boost collection to get the name (label)
        {
            "$lookup": {
                "from": "income_boost_types",                # The collection to join
                "localField": "income_boost_source.value",    # Field from the current collection
                "foreignField": "_id",              # Field from the income_boost collection
                "as": "income_boost_info"                   # Resulting array field for joined data
            }
        },

        # Step 3: Unwind the income_boost_info array to flatten it
        {"$unwind": "$income_boost_info"},

        # Step 4: Group by income_boost.value and count occurrences, include income_boost name
        {
            "$group": {
                "_id": "$income_boost_source.value",          # Group by income_boost.value
                "count": {"$sum": 1},               # Count occurrences per bill type
                "balance": {"$sum": "$income_boost"},  # Sum balance and monthly_interest
                "name": {"$first": "$income_boost_info.name"}  # Get the first name (label)
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
    income_boost_type_all = list(collection.aggregate(pipeline))

    income_boost_type_counts = income_boost_type_all[0]['grouped_results'] if income_boost_type_all else []
    total_income_boost_type = income_boost_type_all[0]['total_count'] if income_boost_type_all else 0
    total_balance = income_boost_type_all[0]['total_balance'] if income_boost_type_all else 0
    if len(income_boost_type_counts) > 0:
        data_json = MongoJSONEncoder().encode(income_boost_type_counts)
        income_boost_type_counts = json.loads(data_json)

     # Fetch bill type names
    income_boost_types = income_boost_types.find({'_id': {'$in': incometype_id_list}})    
    income_boost_type_names = {str(d['_id']): d['name'] for d in income_boost_types}

    

    return jsonify({
        "payLoads":{            
            "income_boost_type_counts":income_boost_type_counts,
            "total_income_boost_type":total_income_boost_type,
            "total_balance":total_balance,
            "income_boost_type_names":income_boost_type_names,
           


        }        
    })