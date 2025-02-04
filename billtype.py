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


@app.route("/api/billtype-dropdown/<string:user_id>", methods=['GET'])
def bill_type_dropdown(user_id:str,value_return:int=0):
    sort_params = [('order', 1)]  # Sort by the 'order' field in ascending order
    cursor = my_col('bill_type').find(
        {
            "deleted_at": None,
            "user_id": {"$in": [None, ObjectId(user_id)]}
        },
        {'_id': 1, 'name': 1, 'parent': 1, 'order': 1}  # Include 'order' in the projection
    ).sort(sort_params)

    categories = list(cursor)
    grouped_categories = {}
    standalone_options = []

    # Iterate over the categories and group them by parent
    for category in categories:
        parent_id = category.get("parent")
        category_id = str(category["_id"])
        category_name = category["name"]
        category_order = category.get("order", 0)  # Get the order, default to 0

        if parent_id is None:
            # It's a parent category
            grouped_categories[category_id] = {
                "label": category_name,
                "options": [],
                "order": category_order  # Store the order for parent categories
            }
        else:
            # It's a child category, find its parent
            parent_id_str = str(parent_id)
            if parent_id_str in grouped_categories:
                grouped_categories[parent_id_str]["options"].append({
                    "label": category_name,
                    "value": category_id,
                    "order": category_order  # Store the order for child categories
                })

    # Sort the children within each parent group by the 'order' field
    for parent_id, group in grouped_categories.items():
        group["options"] = sorted(group["options"], key=lambda x: x["order"])

    # Separate out standalone categories (those with no children) and those with no children but ordered
    for parent_id, group in grouped_categories.items():
        if not group["options"]:
            standalone_options.append({
                "label": group["label"],
                "value": parent_id,
                "order": group["order"]  # Include the order for standalone options
            })

    # Remove empty groups from the grouped categories
    grouped_categories = {k: v for k, v in grouped_categories.items() if v["options"]}

    # Sort the parent categories by their 'order' field
    sorted_grouped_categories = sorted(grouped_categories.values(), key=lambda x: x["order"])

    # Sort standalone categories by their 'order' field
    sorted_standalone_options = sorted(standalone_options, key=lambda x: x["order"])

    # Combine the sorted optgroups and sorted standalone options
    result = sorted_grouped_categories + sorted_standalone_options

    if value_return > 0:
        return result
    else:
        return jsonify({
            "list":result
        })


