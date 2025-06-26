from flask import request,jsonify
from pymongo import UpdateOne
#from flask_cors import CORS, cross_origin
from app import app
from util import *
from models import  DebtAccounts, DebtType, UserSettings
from dbpg import db
from sqlalchemy.dialects import postgresql
from db import my_col
debt_accounts_log = my_col('debt_accounts_log')

@app.route('/api/debtpayoffpg/<int:user_id>', methods=['POST'])
def debtpayoff_pg(user_id: int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)

    # Query DebtAccounts and join DebtType
    query = db.session.query(
        DebtAccounts.id,
        DebtAccounts.name,
        DebtAccounts.payor,
        DebtAccounts.balance,
        DebtAccounts.interest_rate,
        DebtAccounts.monthly_payment,
        DebtAccounts.monthly_interest,
        DebtAccounts.due_date,
        DebtAccounts.custom_payoff_order,
        DebtType.name
        ).join(
        DebtType, DebtAccounts.debt_type_id == DebtType.id
    ).filter(
        DebtAccounts.user_id == user_id,
        DebtAccounts.deleted_at == None,
        DebtAccounts.closed_at == None
    ).order_by(DebtAccounts.custom_payoff_order)

    compiled = query.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    print(str(compiled))

    # Get total count of matching records
    total_count = query.count()

    # Paginate results
    #debts = query.offset(page_index * page_size).limit(page_size).all()
    debts = query.all()
    

    # Create a list of debt entries
    debt_entries = []
    for (
        id,
        name,
        payor,
        balance,
        interest_rate,
        monthly_payment,
        monthly_interest,
        due_date,
        custom_payoff_order,
        debt_type_name
    ) in debts:
        debt_entry = {
            "id": id,
            "name": name,
            "debt_type": debt_type_name,  # Directly from the join
            "payor": payor,
            "balance": round(balance, 2),
            "interest_rate": interest_rate,
            "monthly_payment": round(monthly_payment, 2),
            "monthly_interest": round(monthly_interest, 2),
            "due_date": convertDateTostring(due_date),
            "custom_payoff_order": custom_payoff_order
        }
        debt_entries.append(debt_entry)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size

    return jsonify({
        'rows': debt_entries,
        'pageCount': total_pages,
        'totalRows': total_count
    })



from sqlalchemy import case, update

@app.route('/api/update-payoff-orderpg', methods=['POST'])
def update_payoff_order_pg():
    data = request.get_json()

    if not data:
        return jsonify({'message': 'No data provided'}), 400

    try:
        
        # Prepare the case expressions for each `id` and `custom_payoff_order`
        '''
        update_cases = [
            (DebtAccounts.id == item["id"], item["custom_payoff_order"]) for item in data
        ]

    
        # Create the case statement, using the unpacking operator (*) to pass conditions as positional arguments
        custom_payoff_case = case(*update_cases, else_=DebtAccounts.custom_payoff_order)
        '''

       

        conditions = [
            (DebtAccounts.id == item["id"], item["custom_payoff_order"]) for item in data
        ]
        custom_payoff_case = case(*conditions)

        ids_to_update = [item["id"] for item in data]

        # Build the UPDATE statement
        stmt = (
            update(DebtAccounts)
            .where(DebtAccounts.id.in_(ids_to_update))
            .values(custom_payoff_order=custom_payoff_case)
        )
        # Print the raw SQL
        compiled = stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        print(str(compiled))


        db.session.execute(stmt)

        # Perform the update using a single query
        # db.session.query(DebtAccounts).update({
        #     DebtAccounts.custom_payoff_order: custom_payoff_case
        # })        


        operations = [
            UpdateOne(
                {"debt_id": item["id"]},  # Match
                {"$set": {"custom_payoff_order": item["custom_payoff_order"]}}
            )
            for item in data
        ]

        message = 'Custom payoff order updated successfully'

        if operations:  # Make sure it's not empty
            debt_accounts_log.bulk_write(operations)
            db.session.commit()  # Commit the changes to the database
        else:
            message = 'Custom payoff order update failed'
        
        
        return jsonify({'message': message}), 200

    except Exception as e:
        print('exceptio',e)
        db.session.rollback()  # Rollback in case of error
        return jsonify({'message': f'An error occurred: {str(e)}'}), 200

