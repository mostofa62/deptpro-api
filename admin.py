import os
from flask import request,jsonify, json
from sqlalchemy import asc, desc, func
from app import app
from util import convertDateTostring
from datetime import datetime
from models import User
from dbpg import db


@app.route("/api/adminpg/<int:id>", methods=['GET'])
def admin_dashboard_pg(id: int):


    role_counts = db.session.query(
    func.count(User.id).label('user_count'),
        User.role
    ).filter(User.role.in_([2, 13, 10])).group_by(User.role).all()

    role_counts_dict = [{'role':role,'count': count} for count, role in role_counts]
    online_count = db.session.query(
    func.count(User.id).label('user_count')        
    ).filter(User.is_online == True).scalar()



    return jsonify({
        "payLoads":{
            "role_counts": role_counts_dict,
            "online_count":online_count
        }
        
        })