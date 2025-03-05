from flask import jsonify
from sqlalchemy import or_
#from flask_cors import CORS, cross_origin
from app import app
from util import *
from models import DebtType
from dbpg import db

@app.route("/api/debttype-dropdownpg/<int:user_id>", methods=['GET'])
async def debt_type_dropdown_pg(user_id:int, value_return:int=0):

    # Query BillType with filtering for deleted records, user_id, and sorting by ordering
    query = db.session.query(DebtType.id, DebtType.name, DebtType.parent_id, DebtType.ordering).filter(
        DebtType.deleted_at.is_(None),        
        or_(
            DebtType.user_id.in_([user_id]),  # Check for the specific user_id
            DebtType.user_id.is_(None)         # Check for NULL (None) user_id
        )
    ).all()

    # Organize categories into parent-child hierarchical structure
    grouped_categories = {}
    standalone_options = set()
    parents_with_children = set()

    # Step 1: Build the structure
    for category_id, category_name, parent_id, category_order in query:
        if parent_id is None:
            # This is a potential standalone option
            standalone_options.add(category_id)
            # Initialize as a parent in case it has children
            if category_id not in grouped_categories:
                grouped_categories[category_id] = {
                    "label": category_name,
                    "options": [],
                    "order": category_order or 0
                }
        else:
            # This is a child category
            if parent_id not in grouped_categories:
                # Initialize the parent if not already present
                grouped_categories[parent_id] = {
                    "label": None,  # Placeholder
                    "options": [],
                    "order": 0  # Placeholder
                }
            # Append the child to the parent
            grouped_categories[parent_id]["options"].append({
                "label": category_name,
                "value": category_id,
                "order": category_order or 0
            })
            # Mark this parent as having children
            parents_with_children.add(parent_id)

    # Step 2: Finalize parent categories
    for category_id, category_name, parent_id, category_order in query:
        if category_id in grouped_categories:
            # Update parent label and order
            grouped_categories[category_id]["label"] = category_name
            grouped_categories[category_id]["order"] = category_order or 0

    # Step 3: Remove parents with children from standalone options
    standalone_options = [
        {
            "label": grouped_categories[category_id]["label"],
            "value": category_id,
            "order": grouped_categories[category_id]["order"]
        }
        for category_id in standalone_options if category_id not in parents_with_children
    ]

    # Step 4: Prepare grouped categories and standalone options for the final result
    grouped_result = [group for group in grouped_categories.values() if group["options"]]

    # Step 5: Combine grouped categories and standalone options without sorting yet
    result = grouped_result + standalone_options

    # Step 6: Sort the final result by 'order'
    result = sorted(result, key=lambda x: x["order"])

    # Step 7: Sort child categories within each parent by 'order'
    for group in result:
        if "options" in group:
            group["options"] = sorted(group["options"], key=lambda x: x["order"])



    # Return result
    if value_return > 0:
        return result
    else:
       return jsonify({
        "list":result
    })
   