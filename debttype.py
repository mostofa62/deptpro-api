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


@app.route("/api/debttype-dropdown/<string:user_id>", methods=['GET'])
def debt_type_dropdown(user_id:str):
    cursor = my_col('debt_type').find(
        {
            "deleted_at":None,
            "user_id": {"$in": [None, ObjectId(user_id)]}
        },
        {'_id':1,'name':1,'parent':1}
        )
    # list_cur = []
    # for todo in cursor:               
    #     list_cur.append({'value':str(todo['_id']),'label':todo['name']})
    #list_cur = list(cursor)
    #data_json = MongoJSONEncoder().encode(list_cur)
    #data_obj = json.loads(data_json)
    categories = list(cursor)
    # Dictionary to store the grouped data
    grouped_categories = {}
    standalone_options = []

    # Iterate over the categories and group them by parent
    for category in categories:
        parent_id = category.get("parent")
        category_id = str(category["_id"])
        category_name = category["name"]

        if parent_id is None:
            # It's a parent category
            grouped_categories[category_id] = {
                "label": category_name,
                "options": []
            }
        else:
            # It's a child category, find its parent
            parent_id_str = str(parent_id)
            if parent_id_str in grouped_categories:
                grouped_categories[parent_id_str]["options"].append({
                    "label": category_name,
                    "value": category_id
                })

    # Separate out standalone categories (those with no children)
    for parent_id, group in grouped_categories.items():
        if not group["options"]:
            # If no children, treat this as a standalone option
            standalone_options.append({
                "label": group["label"],
                "value": parent_id
            })

    # Remove empty groups from the grouped categories
    grouped_categories = {k: v for k, v in grouped_categories.items() if v["options"]}

    # Combine the optgroups and standalone options
    result = list(grouped_categories.values()) + standalone_options
    return jsonify({
        "list":result
    })