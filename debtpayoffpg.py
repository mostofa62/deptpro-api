from flask import request,jsonify
#from flask_cors import CORS, cross_origin
from app import app
from util import *
from models import  DebtAccounts, DebtType, UserSettings
from dbpg import db


@app.route('/api/debtpayoffpg/<int:user_id>', methods=['POST'])
def debtpayoff_pg(user_id: int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)

    # Query DebtAccounts and join DebtType
    query = db.session.query(DebtAccounts, DebtType.name).join(
        DebtType, DebtAccounts.debt_type_id == DebtType.id
    ).filter(
        DebtAccounts.user_id == user_id,
        DebtAccounts.deleted_at == None,
        DebtAccounts.closed_at == None
    ).order_by(DebtAccounts.custom_payoff_order)

    # Get total count of matching records
    total_count = query.count()

    # Paginate results
    debts = query.offset(page_index * page_size).limit(page_size).all()

    

    # Create a list of debt entries
    debt_entries = []
    for debt, debt_type_name in debts:
        debt_entry = {
            "id": debt.id,
            "name": debt.name,
            "debt_type": debt_type_name,  # Directly from the join
            "payor": debt.payor,
            "balance": round(debt.balance, 2),
            "interest_rate": debt.interest_rate,
            "monthly_payment": round(debt.monthly_payment, 2),
            "monthly_interest": round(debt.monthly_interest, 2),
            "due_date": convertDateTostring(debt.due_date),
            "custom_payoff_order": debt.custom_payoff_order
        }
        debt_entries.append(debt_entry)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size

    return jsonify({
        'rows': debt_entries,
        'pageCount': total_pages,
        'totalRows': total_count
    })



from sqlalchemy import case

@app.route('/api/update-payoff-orderpg', methods=['POST'])
def update_payoff_order_pg():
    data = request.get_json()

    if not data:
        return jsonify({'message': 'No data provided'}), 400

    try:
        # Prepare the case expressions for each `id` and `custom_payoff_order`
        update_cases = [
            (DebtAccounts.id == item["id"], item["custom_payoff_order"]) for item in data
        ]

        # Create the case statement, using the unpacking operator (*) to pass conditions as positional arguments
        custom_payoff_case = case(*update_cases, else_=DebtAccounts.custom_payoff_order)

        # Perform the update using a single query
        db.session.query(DebtAccounts).update({
            DebtAccounts.custom_payoff_order: custom_payoff_case
        })

        db.session.commit()  # Commit the changes to the database

        return jsonify({'message': 'Custom payoff order updated successfully'}), 200

    except Exception as e:
        db.session.rollback()  # Rollback in case of error
        return jsonify({'message': f'An error occurred: {str(e)}'}), 200

