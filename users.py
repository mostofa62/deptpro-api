import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from app import app
from db import my_col
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta

TOKEN_EXPIRATION = os.environ["TOKEN_EXPIRATION"]
#CORS(app)
collection = my_col('users')

@app.route('/api/users/<int:role>', methods=['POST'])
def list_user(role:int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])

    # Construct MongoDB filter query
    query = {
        'role':role
    }
    if global_filter:
        query["$or"] = [
            {"name": {"$regex": global_filter, "$options": "i"}},
            {"email": {"$regex": global_filter, "$options": "i"}},
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
    data_list = list(cursor)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size
    

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count
    })

'''
@app.route("/api/users", methods=['GET'])
def list_user():
    page = int(request.args.get('page'))
    per_page = int(request.args.get('per_page'))
    total=my_col('users').count_documents({"role":2})
    cursor = my_col('users').find({"role":2}).skip(per_page*(page-1)).limit(per_page)
    total_pages = int(total / per_page) * per_page
    #list_cur = list(cursor)
    #json_data = dumps(list_cur, indent = 2) 
    data_json = MongoJSONEncoder().encode(list(cursor))
    data_obj = json.loads(data_json)


    return jsonify({
        "page":page,
        "per_page":per_page,
        "total":total,
        "total_pages":total_pages,
        "data":data_obj
    })
'''
@app.route("/api/users/<string:id>", methods=['GET'])
def view_user(id:str):
    user = my_col('users').find_one(
        {"_id":ObjectId(id)},
        {"_id":0,"password":0,'id':0}
        )


    return jsonify({
        "user":user
    })

#new registration from member registration part
@app.route("/api/member-registration", methods=['POST'])
def member_registration():
    if request.method == 'POST':
        data = json.loads(request.data)
        member_id = None
        message = ''
        error = 0

        total_members=my_col('users').count_documents({"role":{'$gte':10}})
        memberid = datetime.now().strftime('%Y%m%d%H%M%S')+str(total_members+1)
        try:      
            members = my_col('users').insert_one({
                "name":data['name'],            
                "email":data['email'],
                "memberid":memberid,
                "phone":data['phone'],
                "password":data['password'],
                "role":13, #1-9 for admin, staff , 10-client, 12-affiliated,13-prospect users
                "token":None,
                "token_expired_at":None,                
                "notified_by_email":0,
                "notified_by_sms":0,
                "created_at":datetime.now(),
                "updated_at":datetime.now(),
                "suspended_at":None,
                "deleted_at":None,
                'id':(total_members+1)
                })
            member_id = str(members.inserted_id)
            error = 0
            message = 'Registration Succefull'
        except Exception as ex:
            print('Member insertion Failed',ex)
            member_id = None
            error = 1
            message = 'Registration Failed'


        return jsonify({
            "member_id":member_id,
            "message":message,
            "error":error
        })
    
#member login endpoint
@app.route("/api/member-login", methods=['POST'])
def member_login():
   if request.method == 'POST':
        data = json.loads(request.data)

        email = data['email']
        password = data['password']

        myquery = { "$or":[
            {"email" :email},
            {"memberid":email}
        ]}
        

        user = my_col('users').find_one(myquery)
        print('found user: ',user)

        login_status = 0
        message = "Member not found!"

        if(user!=None and user["suspended_at"] != None):
            message = "Your account is suspended!"
            login_status = 2
            return({
                "user":None,
                "message":message,
                "login_status":login_status
            })
        
        if(user!=None and user["deleted_at"] != None):
            message = "Your account is removed!"
            login_status = 3
            return({
                "user":None,
                "message":message,
                "login_status":login_status
            })
        
        if(user!=None and user["role"] < 10):
            message = "You are not allowed here!"
            login_status = 5
            return({
                "user":None,
                "message":message,
                "login_status":login_status
            })    


        if(user !=None and user['password'] == password):            
            
            
            id = str(user["_id"])

            token = JWT_ENCODE({"userid":id,"email":email})
                        
            token_expired_at = datetime.now()+timedelta(minutes=datetime.now().minute+int(TOKEN_EXPIRATION))
            print('TOKEN: ',token, 'TOKEN_EXPIRED_At',token_expired_at)
            newvalues = { "$set": { "token": token,"token_expired_at":token_expired_at } }
            myquery = { "_id" :ObjectId(user["_id"])}
            

            my_col('users').update_one(myquery, newvalues)
            login_status = 1
            message = None
            return jsonify({             
                 "localId":id,
                 "displayName":user["name"],
                 "idToken":token,
                 "role":user["role"],
                 "expiresIn":TOKEN_EXPIRATION,
                 "message":message,
                 "login_status":login_status
             
           })
        
        if(user !=None and user['password'] != password):
            message = "May be you forgot your password!"
            login_status = 4
            return({
                "user":None,
                "password":None,
                "login_status":login_status,
                "message":message

            })

        
        
        return({
        "user":None,
        "login_status":login_status,
        "message":message,
        })
#member logout
@app.route("/api/member-logout", methods=['POST'])
def member_logout():
   if request.method == 'POST':
        data = json.loads(request.data)

        token = data['token']
        
        
        decoded = JWT_DECODE(token)
        print('decode data:',decoded)
        if(decoded):
            myquery = { "_id" :ObjectId(decoded['userid'])}
            newvalues = { "$set": { "token": None,'token_expired_at':None } }
            my_col('users').update_one(myquery, newvalues)
            return({"logout":1})
        
        return({"logout":0})
   


#admin login endpoint
@app.route("/api/admin-login", methods=['POST'])
def admin_login():
   if request.method == 'POST':
        data = json.loads(request.data)

        email = data['email']
        password = data['password']

        myquery = { "$or":[
            {"email" :email},
            {"memberid":email}
        ]}
        

        user = my_col('users').find_one(myquery)
        print('found user: ',user)

        login_status = 0
        message = "User not found!"

        if(user!=None and user["suspended_at"] != None):
            message = "Your account is suspended!"
            login_status = 2
            return({
                "user":None,
                "message":message,
                "login_status":login_status
            })
        
        if(user!=None and user["deleted_at"] != None):
            message = "Your account is removed!"
            login_status = 3
            return({
                "user":None,
                "message":message,
                "login_status":login_status
            })
        

        if(user!=None and user["role"] >= 10):
            message = "You are not allowed here!"
            login_status = 5
            return({
                "user":None,
                "message":message,
                "login_status":login_status
            })


        if(user !=None and user['password'] == password):            
            
            
            id = str(user["_id"])

            token = JWT_ENCODE({"userid":id,"email":email})
                        
            token_expired_at = datetime.now()+timedelta(minutes=datetime.now().minute+int(TOKEN_EXPIRATION))
            print('TOKEN: ',token, 'TOKEN_EXPIRED_At',token_expired_at)
            newvalues = { "$set": { "token": token,"token_expired_at":token_expired_at } }
            myquery = { "_id" :ObjectId(user["_id"])}
            

            my_col('users').update_one(myquery, newvalues)
            login_status = 1
            message = None
            return jsonify({             
                 "localId":id,
                 "displayName":user["name"],
                 "idToken":token,
                 "role":user["role"],
                 "expiresIn":TOKEN_EXPIRATION,
                 "message":message,
                 "login_status":login_status
             
           })
        
        if(user !=None and user['password'] != password):
            message = "May be you forgot your password!"
            login_status = 4
            return({
                "user":None,
                "password":None,
                "login_status":login_status,
                "message":message

            })

            
        
        return({
        "user":None,
        "login_status":login_status,
        "message":message,
        })
#admin logout
@app.route("/api/admin-logout", methods=['POST'])
def admin_logout():
   if request.method == 'POST':
        data = json.loads(request.data)

        token = data['token']
        
        
        decoded = JWT_DECODE(token)
        print('decode data:',decoded)
        if(decoded):
            myquery = { "_id" :ObjectId(decoded['userid'])}
            newvalues = { "$set": { "token": None,'token_expired_at':None } }
            my_col('users').update_one(myquery, newvalues)
            return({"logout":1})
        
        return({"logout":0})   


@app.route("/api/user-create/<string:id>", methods=['POST'])
def update_user(id:str):
    if request.method == 'POST':
      name  =  request.form.get('name')
      phone = request.form.get('phone')
      email  =  request.form.get('email')
      password  =  request.form.get('password')

      message = ''
      error = 0


      try:

        myquery = { "_id" :ObjectId(id)}
        newvalues = { "$set": { 
            "name": name,
            "phone":phone,
            "email":email,
            "updated_at":datetime.now() 
            } 
        }
        if(password != ""):
            newvalues = { "$set": { 
                "name": name,
                "phone":phone,
                "email":email,
                "password":password, 
                "updated_at":datetime.now() } }

        
        my_col('users').update_one(myquery, newvalues)
        message = 'Update Saved!'
        error = 0
      except Exception as ex:          
          print('',ex)
          message = 'Update Failed!'
          error = 1
      


    return jsonify({
        "user":my_col('users').find_one(myquery,{"_id":0,"password":0,'id':0}),
        "message":message,
        "error":error
    })



@app.route("/api/userby/<string:tag>/<string:userid>/<string:token>", methods=['GET'])
def userby(tag:str,userid:str,token:str):
    decoded = jwt.decode(token, key, algorithms="HS256")
    user = userid if decoded["user"] == userid else None
    return({
        "user":user
    })



@app.route("/api/userbyemail/<string:userid>", methods=['POST'])
def userbyEmail(userid:str):
    if request.method == 'POST':
        data = json.loads(request.data)
        email = data['email']
        #print(token)
        #exit()
        
        unexpected_token_value = ["undefined", "null"]
        user_self = None
        if(userid not in unexpected_token_value):
            myquery = { "_id" :ObjectId(userid)}
            user_self = my_col('users').find_one(myquery)
            
        myquery = { "email" :email}
        user = my_col('users').find_one(myquery)

        found = True

        if(user_self and email == user_self['email']):
            found = True
        elif((user and user_self) and email != user_self['email']):
            found = False
        elif(user and user_self == None):
            found = False        
        elif(user== None and user_self == None):
            found=True
        
    return({
        "success":found
    })

@app.route("/api/userbyusername/<string:userid>", methods=['POST'])
def userbyUsername(userid:str):
    if request.method == 'POST':
        data = json.loads(request.data)
        username = data['username']
        #print(token)
        #exit()
        
        unexpected_token_value = ["undefined", "null"]
        user_self = None
        if(userid not in unexpected_token_value):
            myquery = { "_id" :ObjectId(userid)}
            user_self = my_col('users').find_one(myquery)
            
        myquery = { "username" :username}
        user = my_col('users').find_one(myquery)

        found = True

        if(user_self and username == user_self['username']):
            found = True
        elif((user and user_self) and username != user_self['username']):
            found = False
        elif(user and user_self == None):
            found = False        
        elif(user== None and user_self == None):
            found=True
        
    return({
        "success":found
    })





@app.route('/api/suspend_user/<string:id>/<string:action>', methods=['GET'])
async def suspend_user(id:str,action:str):
    myquery = { "_id" :ObjectId(id)}
    user = my_col('users').find_one(myquery)
    message = user["name"]+" suspended succssfully"
    newvalues = { "$set": { 
        "suspended_at":datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "updated_at":datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  
        } }
    
    if(action == '1'):
        newvalues = { "$set": { 
        "suspended_at":None,
        "updated_at":datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  
        } }
    
    my_col('users').update_one(myquery, newvalues)
    count_done=1

    return jsonify({
        "message":message,
        "done_delete":count_done

    })




@app.route('/api/action-user', methods=['POST'])
def action_user():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']
        key = data['key']
        value = data['value']
        userid = data['userid']
    

        record_id = None
        message = None
        error = 0
        record_done = 0

        value_params = {                                     
                key:value,                
                'updated_by':ObjectId(userid),       
                                               
        }

        try:
            myquery = { "_id" :ObjectId(id)}

            newvalues = { "$set": value_params }
            user_data =  my_col('users').update_one(myquery, newvalues)
            record_id = id if user_data.modified_count else None

            error = 0 if user_data.modified_count else 1
            record_done = 1 if user_data.modified_count  else 0
            if record_done:
                message = f'User {key} Successfully'
                
            else:
                message = f'User {key} Failed'
       

        except Exception as ex:
            record_id = None
            print('User Save Exception: ',ex)
            message = f'User {key} Failed'
            error  = 1
            record_done = 0
    
    
        return jsonify({
            "record_id":record_id,
            "message":message,
            "error":error,
            "deleted_done":record_done
        }) 