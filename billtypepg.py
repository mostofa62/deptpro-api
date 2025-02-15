import os
from flask import Flask,request,jsonify, json
from app import app
from util import *
from datetime import datetime,timedelta
from dbpg import db
from models import BillType
from pgutils import RepeatFrequency, ReminderDays

@app.route("/api/billtype-dropdownpg/<int:user_id>", methods=['GET'])
def bill_type_dropdown_pg(user_id: int, value_return: int = 0):
    # Query BillType with filtering for deleted records, user_id, and sorting by ordering
    query = db.session.query(BillType.id, BillType.name, BillType.parent_id, BillType.ordering).filter(
        BillType.deleted_at.is_(None),
        (BillType.user_id == user_id)
    ).order_by(BillType.ordering).all()

    # Organize categories into parent-child hierarchical structure
    grouped_categories = {}
    standalone_options = []

    # Loop through all BillTypes to group by parent-child hierarchy
    for category_id, category_name, parent_id, category_order in query:
        if parent_id is None:
            # Parent category: create a new entry for it in grouped_categories
            grouped_categories[category_id] = {
                "label": category_name,
                "options": [],
                "order": category_order or 0
            }
        else:
            # Child category: append it to the appropriate parent group
            if parent_id in grouped_categories:
                grouped_categories[parent_id]["options"].append({
                    "label": category_name,
                    "value": category_id,
                    "order": category_order or 0
                })

    # Sort child categories and standalone options by their 'order' field
    sorted_grouped_categories = [
        {**group, "options": sorted(group["options"], key=lambda x: x["order"])}
        for group in grouped_categories.values()
    ]
    
    # Extract and sort standalone categories (those with no children)
    standalone_options = sorted(
        (group for group in grouped_categories.values() if not group["options"]),
        key=lambda x: x["order"]
    )

    # Final result: Combine sorted grouped categories and standalone options
    result = sorted(sorted_grouped_categories, key=lambda x: x["order"]) + standalone_options

    # Return result
    if value_return > 0:
        return result
    else:
        return jsonify({
            "payLoads":{
            "bill_types": result,
            "repeat_frequency":RepeatFrequency,
            "reminder_days":ReminderDays
            }
        })
