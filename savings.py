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
saving_source_types = my_col('saving_source_types')

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


@app.route("/api/saving-all/<string:id>", methods=['GET'])
def get_saving_all(id:str):
    saving = collection.find_one(
        {"_id":ObjectId(id)},
        {"_id":0}
        )
    
    saving['starting_date_word'] = saving['starting_date'].strftime('%d %b, %Y')
    saving['starting_date'] = convertDateTostring(saving['starting_date'],"%Y-%m-%d")
      
    saving['user_id'] = str(saving['user_id'])

    
    category_type = my_col('category_types').find_one(
        {"_id":saving['category']['value']},
        {"_id":0,"name":1}
        )
    
    
    saving['category'] = category_type['name']

    saving['repeat'] = saving['repeat']['label']

    saving['interest_type'] = saving['interest_type']['label']
    saving['savings_strategy'] = saving['savings_strategy']['label']
    


   
    

    return jsonify({
        "payLoads":{
            "saving":saving
        }
    })

@app.route('/api/saving-typewise-info', methods=['GET'])
def get_typewise_saving_info():

    # Fetch the saving type cursor
    saving_type_cursor = my_col('category_types').find(
        {"deleted_at": None},
        {'_id': 1, 'name': 1}
    )

    # Create a list of _id values
    savingtype_id_list = [item['_id'] for item in saving_type_cursor]


    pipeline = [
        # Step 1: Match documents with category.value in billtype_id_list
        {
            "$match": {
                "category.value": {"$in": savingtype_id_list},
                "deleted_at": None
            }
        },

        # Step 2: Lookup to join category collection to get the name (label)
        {
            "$lookup": {
                "from": "category_types",                # The collection to join
                "localField": "category.value",    # Field from the current collection
                "foreignField": "_id",              # Field from the category collection
                "as": "category_info"                   # Resulting array field for joined data
            }
        },

        # Step 3: Unwind the category_info array to flatten it
        {"$unwind": "$category_info"},

        # Step 4: Group by category.value and count occurrences, include category name
        {
            "$group": {
                "_id": "$category.value",          # Group by category.value
                "count": {"$sum": 1},               # Count occurrences per bill type
                "balance": {"$sum": "$goal_amount"},  # Sum balance and monthly_interest
                "name": {"$first": "$category_info.name"}  # Get the first name (label)
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
    category_type_all = list(collection.aggregate(pipeline))

    category_type_counts = category_type_all[0]['grouped_results'] if category_type_all else []
    total_category_type = category_type_all[0]['total_count'] if category_type_all else 0
    total_balance = category_type_all[0]['total_balance'] if category_type_all else 0
    if len(category_type_counts) > 0:
        data_json = MongoJSONEncoder().encode(category_type_counts)
        category_type_counts = json.loads(data_json)

     # Fetch bill type names
    category_types = my_col('category_types').find({'_id': {'$in': savingtype_id_list}})    
    category_type_names = {str(d['_id']): d['name'] for d in category_types}

    twelve_months_ago = datetime.now() - timedelta(days=365)

    print(twelve_months_ago)

    

    
    

    pipeline = [
    # Step 1: Match documents with starting_date in the last 12 months and not deleted
    {
        "$match": {
            "starting_date": {"$gte": twelve_months_ago},
            "deleted_at": None
        }
    },
    
    # Step 2: Project to extract year and month from starting_date
    {
        "$project": {
            "starting_amount": 1,
            "goal_amount": 1,
            "year_month": {
                "$dateToString": {
                    "format": "%Y-%m",  # Format as "YYYY-MM"
                    "date": "$starting_date"
                }
            },
            "month": {
                "$dateToString": {
                    "format": "%m",  # Extract the month number (01-12)
                    "date": "$starting_date"
                }
            },
            "year": {
                "$dateToString": {
                    "format": "%Y",  # Extract the year
                    "date": "$starting_date"
                }
            }
        }
    },

    # Step 3: Group by year_month and sum the balance
    {
        "$group": {
            "_id": "$year_month",  # Group by the formatted month-year
            "total_balance": {"$sum": "$starting_amount"},
            "total_goal_amount": {"$sum": "$goal_amount"},
            "year": {"$first": "$year"},  # Include the year
            "month": {"$first": "$month"}   # Include the month
        }
    },

    # Step 4: Create the formatted year_month_word
    {
        "$project": {
            "_id": 1,
            "total_balance": 1,
            "total_goal_amount":1,
            "year_month_word": {
                "$concat": [
                    {"$substr": [
                        {"$arrayElemAt": [
                            ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                            { "$subtract": [{ "$toInt": "$month" }, 1] }  # Convert month string to integer, { "$subtract": [{ "$toInt": "$month" }, 1] }  // Adjust for zero-based index
                        ]}, 0, 3  # Get the first 3 letters of the month
                    ]},
                    ", ",
                    "$year"  # Append the year
                ]
            }
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
            "total_count": {"$sum": 1},  # Count the number of months (or documents)
            "total_balance": {"$sum": "$total_balance"},  # Sum all the 'total_balance' values from the grouped results
            "total_goal_amount": {"$sum": "$total_goal_amount"},
            "grouped_results": {"$push": {  # Preserve all grouped results in an array
                "year_month": "$_id",
                "year_month_word": "$year_month_word",
                "total_balance": "$total_balance",
                "total_goal_amount":"$total_goal_amount"
            }}
        }
    },

    # Step 8: Use $project to format the output
    {
        "$project": {
            "_id": 0,                           # Remove the _id field
            #"total_count": 1,                   # Include the total count
            "total_balance": 1,
            "total_goal_amount":1,                 # Include the total balance
            "grouped_results": 1                # Include the grouped results
        }
    }
    
]
    
    
    
    year_month_wise_all = list(collection.aggregate(pipeline))

    year_month_wise_counts = year_month_wise_all[0]['grouped_results'] if year_month_wise_all else []
    #year_month_wise_type_t_count= year_month_wise_all[0]['total_count'] if year_month_wise_all else 0
    year_month_wise_balance = year_month_wise_all[0]['total_balance'] if year_month_wise_all else 0
    if len(year_month_wise_counts) > 0:
        data_json = MongoJSONEncoder().encode(year_month_wise_counts)
        year_month_wise_counts = json.loads(data_json)

    return jsonify({
        "payLoads":{            
            "category_type_counts":category_type_counts,
            "total_category_type":total_category_type,
            "total_balance":total_balance,
            "category_type_names":category_type_names,
            "year_month_wise_counts":year_month_wise_counts,
            "year_month_wise_balance":year_month_wise_balance


        }        
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
            
            {"saver": {"$regex": global_filter, "$options": "i"}},            
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

            saving_data = collection.update_one(myquery, newvalues)
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
  
            }
            #print('data',data)
            #print('appendata',append_data)            

            merge_data = data | append_data

            #print('mergedata',merge_data)

            saving_data = collection.insert_one(merge_data)
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