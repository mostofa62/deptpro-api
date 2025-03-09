import os
from flask import request,jsonify, json
from sqlalchemy import asc, desc
from app import app
from util import *
from datetime import datetime
from models import User
from dbpg import db

TOKEN_EXPIRATION = os.environ["TOKEN_EXPIRATION"]


@app.route('/api/userspg/<int:role>', methods=['POST'])
def list_user_pg(role: int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])

    # Base query: only active users with the given role
    query = db.session.query(
        User.id, User.name, User.email, User.phone, User.created_at, User.role
    ).filter(
        User.role == role,
        User.deleted_at.is_(None),
        User.suspended_at.is_(None)
    )

    # Apply global filtering
    if global_filter:
        query = query.filter(
            db.or_(
                User.name.ilike(f"%{global_filter}%"),
                User.email.ilike(f"%{global_filter}%")
            )
        )

    # Apply sorting
    for sort in sort_by:
        sort_field = sort['id']
        sort_direction = desc(getattr(User, sort_field)) if sort['desc'] else asc(getattr(User, sort_field))
        query = query.order_by(sort_direction)

    # Get total count before pagination
    total_count = query.count()

    # Apply pagination
    users = query.offset(page_index * page_size).limit(page_size).all()

    # Convert users to JSON
    user_list = [{
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "created_at": convertDateTostring(user.created_at),
        "role": user.role
    } for user in users]

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size

    return jsonify({
        'rows': user_list,
        'pageCount': total_pages,
        'totalRows': total_count
    })


@app.route("/api/userspg/<int:id>", methods=['GET'])
def view_user_pg(id: int):
    user = db.session.query(User).filter_by(id=id).first()

    if not user:
        return jsonify({"message": "User not found"}), 404

    user_data = {
        "name": user.name,
        "email": user.email,
        "memberid": user.memberid,
        "phone": user.phone,
        "role": user.role,
        "token": user.token,
        "token_expired_at": user.token_expired_at,
        "notified_by_email": user.notified_by_email,
        "notified_by_sms": user.notified_by_sms,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "suspended_at": user.suspended_at,
        "deleted_at": user.deleted_at
    }

    return jsonify({"user": user_data}), 200

#new registration from member registration part
@app.route("/api/member-registrationpg", methods=['POST'])
def member_registration_pg():
    if request.method == 'POST':
        data = request.get_json()
        
        # Initialize variables
        member_id = None
        message = ''
        error = 0
        role = data.get('role', 13)  # Default role is 13 if 'role' is not provided
        
        try:
            # Count members and admins based on role
            total_members = User.query.filter(User.role >= 10).count()
            total_admins = User.query.filter(User.role == 2).count()

            # Generate member ID and admin ID based on the role
            memberid = f"{datetime.now().strftime('%Y%m%d')}{total_members + 1}" if role > 9 else None
            adminid = f"{datetime.now().strftime('%Y%m%d')}{total_admins + 1}" if role < 9 else None
            
            # Create the new user object
            new_member = User(
                name=data['name'],
                email=data['email'],
                memberid=memberid,
                adminid=adminid,
                phone=data['phone'],
                password=data['password'],  # This should be hashed in production
                role=role,
                token=None,
                token_expired_at=None,
                notified_by_email=0,
                notified_by_sms=0,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                suspended_at=None,
                deleted_at=None,            
                refer_id=None
            )
            
            # Add the new user to the database
            db.session.add(new_member)
            db.session.commit()

            # Get the new member ID
            member_id = new_member.id
            message = 'Registration Successful'
            error = 0

        except Exception as ex:
            db.session.rollback()  # Rollback if there is an error
            print('Member registration failed:', ex)
            member_id = None
            message = 'Registration Failed'
            error = 1

        # Return response with member ID, message, and error code
        return jsonify({
            "member_id": member_id,
            "message": message,
            "error": error
        })
    
#member login endpoint
@app.route("/api/member-loginpg", methods=['POST'])
def member_login_pg():
    if request.method != 'POST':
        return jsonify({"message": "Invalid request method"}), 405

    data = request.get_json()
    email_or_memberid = data.get("email")
    password = data.get("password")

    if not email_or_memberid or not password:
        return jsonify({"message": "Email and password are required", "login_status": 0}), 400

    # Find user by email or member ID
    user = db.session.query(User).filter(
        (User.email == email_or_memberid) | (User.memberid == email_or_memberid)
    ).first()

    if not user:
        return jsonify({"user":None,"message": "Member not found!", "login_status": 0}), 200

    # Check if account is suspended or deleted
    if user.suspended_at:
        return jsonify({"user":None,"message": "Your account is suspended!", "login_status": 2}), 200

    if user.deleted_at:
        return jsonify({"user":None,"message": "Your account is removed!", "login_status": 3}), 200

    # Role-based access restriction
    if user.role < 10:
        return jsonify({"user":None,"message": "You are not allowed here!", "login_status": 5}), 200

    # Verify plain-text password
    if user.password != password:
        return jsonify({"user":None,"password":None,"message": "Maybe you forgot your password!", "login_status": 4}), 200

    # Generate JWT Token
    token_and_expiration = get_token_and_expiration({"user_id": user.id, "email": user.email})
    token = token_and_expiration[0]
    token_expired_at = token_and_expiration[1]
   
    # Update user with new token and expiration time
    user.token = token
    user.token_expired_at = token_expired_at
    user.is_online = True
    db.session.commit()

    return jsonify({
        "localId": user.id,
        "displayName": user.name,
        "idToken": token,
        "role": user.role,
        "expiresIn": TOKEN_EXPIRATION,
        "message": None,
        "login_status": 1
    }), 200


#member logout
@app.route("/api/member-logoutpg", methods=['POST'])
def member_logout_pg():
    data = request.get_json()
    token = data.get("token")

    if not token:
        return jsonify({"logout": 0, "message": "Token is required"}), 400

    try:
        decoded = decode_token(token)        
       

        if 'user_id' not in decoded:
            return jsonify({"logout": 0, "message": "Invalid token"}), 401
        
        user_id = decoded["user_id"]

        # Update user record in the database
        user = db.session.query(User).filter_by(id=user_id).first()

        if user:
            user.token = None
            user.token_expired_at = None
            user.is_online = False
            db.session.commit()
            return jsonify({"logout": 1, "message": "Successfully logged out"}), 200

    except Exception as e:
        print("Error decoding token:", e)
        return jsonify({"logout": 0, "message": "Invalid or expired token"}), 401

    return jsonify({"logout": 0, "message": "Logout failed"}), 400

   


#admin login endpoint
@app.route("/api/admin-loginpg", methods=['POST'])
def admin_login_pg():
    if request.method != 'POST':
        return jsonify({"message": "Invalid request method"}), 405

    data = request.get_json()
    email_or_memberid = data.get("email")
    password = data.get("password")

    if not email_or_memberid or not password:
        return jsonify({"message": "Email and password are required", "login_status": 0}), 400

    # Find user by email or member ID
    user = db.session.query(User).filter(
        (User.email == email_or_memberid) | (User.memberid == email_or_memberid)
    ).first()

    if not user:
        return jsonify({"user":None,"message": "Member not found!", "login_status": 0}), 200

    # Check if account is suspended or deleted
    if user.suspended_at:
        return jsonify({"user":None,"message": "Your account is suspended!", "login_status": 2}), 200

    if user.deleted_at:
        return jsonify({"user":None,"message": "Your account is removed!", "login_status": 3}), 200

    # Role-based access restriction
    if user.role >= 10:
        return jsonify({"user":None,"message": "You are not allowed here!", "login_status": 5}), 200

    # Verify plain-text password
    if user.password != password:
        return jsonify({"user":None,"password":None,"message": "Maybe you forgot your password!", "login_status": 4}), 200

    # Generate JWT Token
    token_and_expiration = get_token_and_expiration({"user_id": user.id, "email": user.email})
    token = token_and_expiration[0]
    token_expired_at = token_and_expiration[1]
   
    # Update user with new token and expiration time
    user.token = token
    user.token_expired_at = token_expired_at
    user.is_online = True
    db.session.commit()

    return jsonify({
        "localId": user.id,
        "displayName": user.name,
        "idToken": token,
        "role": user.role,
        "expiresIn": TOKEN_EXPIRATION,
        "message": None,
        "login_status": 1
    }), 200
   
#admin logout
@app.route("/api/admin-logoutpg", methods=['POST'])
def admin_logout_pg():
    data = request.get_json()
    token = data.get("token")

    if not token:
        return jsonify({"logout": 0, "message": "Token is required"}), 400

    try:
        decoded = decode_token(token)        
       
        if 'user_id' not in decoded:
            return jsonify({"logout": 0, "message": "Invalid token"}), 401
        
        user_id = decoded["user_id"]

        # Update user record in the database
        user = db.session.query(User).filter_by(id=user_id).first()

        if user:
            user.token = None
            user.token_expired_at = None
            user.is_online = False
            db.session.commit()
            return jsonify({"logout": 1, "message": "Successfully logged out"}), 200

    except Exception as e:
        print("Error decoding token:", e)
        return jsonify({"logout": 0, "message": "Invalid or expired token"}), 401

    return jsonify({"logout": 0, "message": "Logout failed"}), 400


@app.route("/api/user-createpg/<int:id>", methods=['POST'])
def update_user_pg(id: int):
    if request.method == 'POST':
        # Get user data from the form
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        password = request.form.get('password')

        message = ''
        error = 0

        try:
            # Fetch user record
            user = User.query.filter_by(id=id).first()

            if not user:
                message = "User not found!"
                error = 1
                return jsonify({"message": message, "error": error})

            # Update user details
            user.name = name
            user.phone = phone
            user.email = email
            user.updated_at = datetime.now()

            # Update password if provided
            if password:
                user.password = password

            # Commit the changes to the database
            db.session.commit()

            message = 'Update Saved!'
            error = 0

        except Exception as ex:
            # Rollback in case of error
            db.session.rollback()
            print('Error:', ex)
            message = 'Update Failed!'
            error = 1

        # Return updated user details without the password
        updated_user = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "created_at": convertDateTostring(user.created_at),
            "role": user.role
        }

        return jsonify({
            "user": updated_user,
            "message": message,
            "error": error
        })



@app.route("/api/userbypg/<string:tag>/<int:userid>/<string:token>", methods=['GET'])
def userby_pg(tag:str,userid:int,token:str):
    decoded = jwt.decode(token, key, algorithms="HS256")
    user = userid if decoded["user"] == userid else None
    return({
        "user":user
    })


@app.route("/api/userbyemailpg/<int:userid>", methods=['POST'])
@app.route("/api/userbyemailpg", methods=['POST'])
def userbyEmail_pg(userid: int=None):
    if request.method == 'POST':
        data = json.loads(request.data)
        email = data.get('email')

        # Initialize a variable to indicate if the email exists for this user
        found = True
        user_self = None
        
        # Find the user by user ID
        if userid:
            user_self = User.query.filter_by(id=userid).first()

        user = User.query.filter_by(email=email).first()
        
        if(user_self and email == user_self.email):
            found = True
        elif((user and user_self) and email != user_self.email):
            found = False
        elif(user and user_self == None):
            found = False        
        elif(user== None and user_self == None):
            found=True
        
        return jsonify({"success": found})

@app.route("/api/userbyusernamepg/<int:userid>", methods=['POST'])
def userbyUsername_pg(userid:int):
    if request.method == 'POST':
        data = json.loads(request.data)
        username = data['username']
              # Initialize a variable to indicate if the email exists for this user
        found = True
        user_self = None
        
        # Find the user by user ID
        if userid:
            user_self = User.query.filter_by(id=userid).first()

        user = User.query.filter_by(username=username).first()
        
        if(user_self and username == user_self.username):
            found = True
        elif((user and user_self) and username != user_self.username):
            found = False
        elif(user and user_self == None):
            found = False        
        elif(user== None and user_self == None):
            found=True
        
        
    return({
        "success":found
    })



@app.route('/api/suspend_userpg', methods=['POST'])
def suspend_member_pg():
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = None
        action = None
        message = None
        error = 0
        deleted_done = 0

        # Extract data from the request
        id = data['id']
        key = data['key']

        # Determine action and field based on the key
        action = 'Deleted' if key < 2 else 'Suspended'       

        # Fetch the user by ID using SQLAlchemy
        user = User.query.get(id)

        if user:
            try:
                # Set the appropriate field to the current time
                if key < 2:
                    user.deleted_at = datetime.now()
                else:
                    user.suspended_at = datetime.now()

                # Update the 'updated_at' timestamp
                user.updated_at = datetime.now()

                # Commit the changes to the database
                db.session.commit()
                user_id = id
                deleted_done = 1
                message = f'Member account {action} Successfully'
            except Exception as ex:
                # Rollback in case of any error and log the issue
                db.session.rollback()
                print(f'Member account Save Exception: {ex}')
                message = f'Member account {action} Failed'
                error = 1
        else:
            message = "User not found"
            error = 1
            deleted_done = 0

        return jsonify({
            "user_id": user_id,
            "message": message,
            "error": error,
            "deleted_done": deleted_done
        })


@app.route('/api/suspend_userpg/<int:id>/<string:action>', methods=['GET'])
async def suspend_user_pg(id: int, action: str):
    # Fetch the user by ID using SQLAlchemy
    user = User.query.get(id)
    
    if user:
        # Set the message based on the user's name
        message = f'{user.name} suspended successfully'

        # Check if the action is to suspend or unsuspend
        if action == '1':
            # If action is '1', unsuspend the user
            user.suspended_at = None
        else:
            # Otherwise, suspend the user
            user.suspended_at = datetime.now()
        
        # Update the 'updated_at' timestamp
        user.updated_at = datetime.now()
        
        try:
            # Commit the changes to the database
            db.session.commit()
            count_done = 1  # Operation was successful

        except Exception as ex:
            # If an error occurs, rollback the transaction and log the error
            db.session.rollback()
            print(f"Error suspending user: {ex}")
            message = "Failed to suspend/unsuspend user"
            count_done = 0

    else:
        # If the user does not exist, set an error message
        message = "User not found"
        count_done = 0

    return jsonify({
        "message": message,
        "done_delete": count_done
    })




@app.route('/api/action-userpg', methods=['POST'])
def action_user_pg():
    if request.method == 'POST':
        data = request.get_json()  # Parse the incoming JSON data

        id = data['id']
        key = data['key']
        value = data['value']
        userid = data['userid']

        record_id = None
        message = None
        error = 0
        record_done = 0

        # Prepare the data to update in the database
        value_params = {
            key: value,
            'updated_by': userid,  # Assuming `updated_by` field exists or needs to be added to the model
        }

        try:
            # Query for the user by id
            user = User.query.get(id)

            if user:
                # If the user exists, update the appropriate field with new value
                setattr(user, key, value)
                user.updated_by = userid  # Assuming you have an `updated_by` field (you may need to add it)

                # Commit the changes to the database
                db.session.commit()

                record_id = user.id
                record_done = 1
                message = f'User {key} successfully updated'

            else:
                # User not found by id
                message = f'User with ID {id} not found'
                error = 1
                record_done = 0

        except Exception as ex:
            # If any SQLAlchemy error occurs, handle it
            db.session.rollback()
            print('User Save Exception: ', ex)
            message = f'User {key} failed to update'
            error = 1
            record_done = 0

        return jsonify({
            "record_id": record_id,
            "message": message,
            "error": error,
            "deleted_done": record_done
        })