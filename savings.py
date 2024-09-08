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
collection = my_col('saving')
category_types = my_col('category_types')

# Helper function to calculate interest and progress
def calculate_savings(savings):
    # Calculate total savings: starting amount + total contributions + any savings boosts
    total_contributions = savings['contribution'] * savings['months_contributed']
    savings_boost = savings.get('savings_boost', 0)
    total_savings = savings['starting_amount'] + total_contributions + savings_boost
    
    # Calculate interest (assuming monthly compounding for simplicity)
    interest_rate = savings['interest_rate'] / 100
    months = savings['months_contributed']
    interest_earned = total_savings * ((1 + interest_rate / 12) ** months - 1)
    
    # Update progress toward goal
    progress = (total_savings + interest_earned) / savings['goal_amount'] * 100
    
    return total_savings, interest_earned, progress


@app.route('/api/delete-saving', methods=['POST'])
def delete_saving():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']

        saving_account_id = None
        message = None
        error = 0
        deleted_done = 0

        try:
            myquery = { "_id" :ObjectId(id)}

            newvalues = { "$set": {                                     
                "deleted_at":datetime.now()                
            } }
            saving_account_data =  collection.update_one(myquery, newvalues)
            saving_account_id = id if saving_account_data.modified_count else None
            error = 0 if saving_account_data.modified_count else 1
            deleted_done = 1 if saving_account_data.modified_count else 0
            message = 'Saving account Deleted Successfully'if saving_account_data.modified_count else 'Saving account Deletion Failed'

        except Exception as ex:
            saving_account_id = None
            print('Saving account Save Exception: ',ex)
            message = 'Saving account Deletion Failed'
            error  = 1
            deleted_done = 0
        
        return jsonify({
            "saving_account_id":saving_account_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })

@app.route("/api/saving/<string:id>", methods=['GET'])
def view_saving(id:str):
    saving = collection.find_one(
        {"_id":ObjectId(id)},
        {"_id":0}
        )
    
    
    saving['starting_date'] = convertDateTostring(saving['starting_date'],"%Y-%m-%d")    
    saving['user_id'] = str(saving['user_id'])

    
    category_type = my_col('category_types').find_one(
        {"_id":saving['category']['value']},
        {"_id":0,"name":1}
        )
    
    saving['category']['value'] = str(saving['category']['value'])
    saving['category']['label'] = category_type['name']   
    

    return jsonify({
        "saving":saving
    })

@app.route('/api/saving/<string:user_id>', methods=['POST'])
def list_saving(user_id:str):
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

        #saving type filter
        category_types = my_col('category_types').find(
                {'name':{"$regex":global_filter,"$options":"i"}},
                {'_id':1}
            )
        category_types_list = list(category_types)
        category_types_id_list = [d.pop('_id') for d in category_types_list]

        pattern_str = r'^\d{4}-\d{2}-\d{2}$'
        starting_date = None        
        #try:
        if re.match(pattern_str, global_filter):
            starting_date = datetime.strptime(global_filter,"%Y-%m-%d")            
        #except ValueError:
        else:
            starting_date = None            

        query["$or"] = [
            
            {"earner": {"$regex": global_filter, "$options": "i"}},            
            {"starting_date":starting_date},            
            {"category.value": {"$in":category_types_id_list}},                 
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
        if todo['category']!=None:
            category_id = todo['category']['value']
            category_type = my_col('category_types').find_one(
            {"_id":category_id},
            {"_id":0,"name":1}
            )
            todo['category'] =  category_type['name']
        

        todo['starting_date'] = convertDateTostring(todo['starting_date'])       
        


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
                    "total_goal_amount": {"$sum": "$goal_amount"},
                    "total_starting_amount":{"$sum": "$starting_amount"},
                    "total_contribution" :{"$sum": "$contribution"}                                      
                    }}  # Sum the balance
    ]

    # Execute the aggregation pipeline
    result = list(collection.aggregate(pipeline))

     # Extract the total balance from the result
    total_goal_amount = result[0]['total_goal_amount'] if result else 0
    total_starting_amount = result[0]['total_starting_amount'] if result else 0
    total_contribution = result[0]['total_contribution'] if result else 0
        
    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count,
        'extra_payload':{
            'total_goal_amount':total_goal_amount,
            'total_starting_amount':total_starting_amount,
            'total_contribution':total_contribution                       
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



@app.route('/api/save-saving-account/<string:id>', methods=['POST'])
async def update_saving(id:str):
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']

        saving_id = None
        message = ''
        result = 0
        try:

            starting_date = convertStringTodate(data['starting_date'])
        
            append_data = {
                'category':newEntryOptionData(data['category'],'category_types',user_id),                

                'user_id':ObjectId(user_id),

                'goal_amount':float(data.get("goal_amount", 0)),
                'interest':float(data.get("interest", 0)),
                'starting_amount':float(data.get("starting_amount", 0)),
                'contribution':float(data.get("contribution", 0)),
                
                "created_at":datetime.now(),
                "updated_at":datetime.now(),
                "deleted_at":None,

                'starting_date':starting_date,                                
  
            }
            #print('data',data)
            #print('appendata',append_data)            

            merge_data = data | append_data

            print('mergedata',merge_data)

            myquery = { "_id" :ObjectId(id)}

            newvalues = { "$set": merge_data }

            saving_data = my_col('saving').update_one(myquery, newvalues)
            saving_id = id if saving_data.modified_count else None
            result = 1 if saving_data.modified_count else 0
            message = 'Saving account updated Succefull'
        except Exception as ex:
            saving_id = None
            print('Saving Update Exception: ',ex)
            result = 0
            message = 'Saving account update Failed'

        return jsonify({
            "saving_id":saving_id,
            "message":message,
            "result":result
        })
    





@app.route('/api/save-saving-account', methods=['POST'])
async def save_saving():
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']

        saving_id = None
        message = ''
        result = 0
        try:

            
            starting_date = convertStringTodate(data['starting_date'])
        
            append_data = {
                'category':newEntryOptionData(data['category'],'category_types',user_id),                

                'user_id':ObjectId(user_id),

                'goal_amount':float(data.get("goal_amount", 0)),
                'interest':float(data.get("interest", 0)),
                'starting_amount':float(data.get("starting_amount", 0)),
                'contribution':float(data.get("contribution", 0)),
                
                "created_at":datetime.now(),
                "updated_at":datetime.now(),
                "deleted_at":None,

                'starting_date':starting_date,

                'months_contributed': 0                                
  
            }
            #print('data',data)
            #print('appendata',append_data)            

            merge_data = data | append_data

            #print('mergedata',merge_data)

            saving_data = my_col('saving').insert_one(merge_data)
            saving_id = str(saving_data.inserted_id)
            result = 1 if saving_id!=None else 0
            message = 'Saving account added Succefull'
        except Exception as ex:
            saving_id = None
            print('Saving Save Exception: ',ex)
            result = 0
            message = 'Saving account addition Failed'

        return jsonify({
            "saving_id":saving_id,
            "message":message,
            "result":result
        })