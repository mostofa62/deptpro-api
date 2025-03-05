from flask import jsonify
from sqlalchemy import and_, asc, func
#from flask_cors import CORS, cross_origin
from models import BillAccounts, BillPayments, BillType
from dbpg import db
from billfunctions import calculate_future_bill
from app import app
from util import *
from datetime import datetime
from sqlalchemy.orm import joinedload
import calendar

def get_month_key(month_year):
    month, year = month_year.split(', ')
    month_number = list(calendar.month_abbr).index(month)
    return (int(year), month_number)

# Sort all months by date
def parse_month(month_str):
    try:
        return datetime.strptime(month_str, '%b %Y')
    except ValueError:
        return datetime.min  # Default to a minimal date if parsing fails


@app.route("/api/bill-projectionpg/<int:userid>", methods=['GET'])
def bill_projection_pg(userid: int):
    # Initializing response structure
    response = {
        "payLoads": {
            "bill_type_bill_counts": [],
            "total_bill_type": 0,
            "total_balance": 0,
            "bill_type_names": {},
            "bill_type_ammortization": [],
            "data": {},
            "error": None  # Default to None for errors, to return a consistent 200 OK
        }
    }

    try:
        # Query BillAccounts with related BillTypes for the given user_id    
        bill_accounts_data = db.session.query(BillAccounts).options(
            joinedload(BillAccounts.bill_type)
        ).filter(
            and_(
                BillAccounts.deleted_at.is_(None),
                BillAccounts.user_id == userid
            )
        ).order_by(asc(BillAccounts.next_due_date)).all()

        if not bill_accounts_data:
            response["payLoads"]["error"] = "No bill accounts found for the user."
            return jsonify(response)

        bill_type_ids = list({str(account.bill_type.id) for account in bill_accounts_data if account.bill_type})

        bill_type_balances = {}    
        data = {}

        for account in bill_accounts_data:
            account_id = str(account.id)  # Convert ObjectId to string
            bill_type_id = str(account.bill_type_id)  # Get the bill type ID 
            frequency = account.repeat_frequency      
            account_balance = float(account.default_amount)

            # Accumulate balance for the same bill type
            bill_type_balances[bill_type_id] = bill_type_balances.get(bill_type_id, 0) + account_balance

            # Calculate future bill projection
            projection_data = calculate_future_bill(initial_amount=account_balance, start_date=account.next_due_date, frequency=frequency)
            monthly_data = projection_data.get('breakdown', [])

            for record in monthly_data:
                month = record.get('month_word')
                amount = record.get('balance', 0)

                # Initialize the month entry if not already present
                if month not in data:
                    data[month] = {'month': month}

                # Sum amounts for the same month and bill type
                data[month][bill_type_id] = data[month].get(bill_type_id, 0) + amount

        # Ensure all bill types are present in each month
        for month, month_data in data.items():
            for bill_type_id in bill_type_ids:
                month_data.setdefault(bill_type_id, 0)  # Fill missing bill type with 0

        # Sort months in calendar order
        merged_data = dict(sorted(data.items(), key=lambda item: get_month_key(item[0])))

        # Convert to list of dicts for the frontend
        chart_data = list(merged_data.values()) if merged_data else []

        # Allocation query for current month's bill payments
        current_month_str = datetime.now().strftime("%Y-%m")

        query = db.session.query(
            BillAccounts.bill_type_id.label('id'),
            BillType.name.label("name"),
            func.sum(BillPayments.amount).label("balance"),
            func.count(BillAccounts.bill_type_id).label('count'),
        ).join(BillAccounts, BillPayments.bill_account_id == BillAccounts.id) \
         .join(BillType, BillAccounts.bill_type_id == BillType.id) \
         .filter(
             func.to_char(BillPayments.pay_date, 'YYYY-MM') == current_month_str,
             BillAccounts.user_id == userid  # Filter by user_id
         ) \
         .group_by(
             BillAccounts.bill_type_id,
             BillType.name
         )
        
        results = query.all()

        total_balance = 0
        total_bill_type = 0
        bill_type_bill_counts = []

        for row in results:
            total_balance += row.balance
            total_bill_type += 1
            bill_type_bill_counts.append({"id": row.id, "name": row.name, "balance": row.balance, "count": row.count})

        bill_types = db.session.query(BillType.id, BillType.name).all()
        bill_type_names = {str(d.id): d.name for d in bill_types}

        # Update response with data
        response["payLoads"].update({
            "bill_type_bill_counts": bill_type_bill_counts,
            "total_bill_type": total_bill_type,
            "total_balance": total_balance,
            "bill_type_names": bill_type_names,
            "bill_type_ammortization": chart_data,
            "data": data
        })

    except Exception as e:
        # Log error or print to console
        print(f"Error occurred: {e}")
        # Add error message to response
        response["payLoads"]["error"] = str(e)

    return jsonify(response)
