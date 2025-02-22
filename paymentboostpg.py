from flask import request,jsonify
#from flask_cors import CORS, cross_origin
from app import app
import re
from util import *
from datetime import datetime
from models import PaymentBoost
from dbpg import db



@app.route('/api/boostspg/<int:user_id>', methods=['POST'])
def list_boosts_pg(user_id: int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])

    # Construct SQLAlchemy filter query
    query = PaymentBoost.query.filter(PaymentBoost.user_id == user_id, PaymentBoost.deleted_at == None)

    if global_filter:
        pattern_str = r'^\d{4}-\d{2}-\d{2}$'
        pay_date_boost = None
        # Match date filter if applicable
        if re.match(pattern_str, global_filter):
            pay_date_boost = convertStringTodate(global_filter)
        
        # Add filtering conditions
        if pay_date_boost:
            query = query.filter(PaymentBoost.pay_date_boost == pay_date_boost)
        else:
            query = query.filter(
                (PaymentBoost.amount.like(f"%{global_filter}%")) |
                (PaymentBoost.month.like(f"%{global_filter}%"))
            )

    # Apply sorting based on the sortBy parameter
    for sort in sort_by:
        sort_field = getattr(PaymentBoost, sort['id'])
        sort_direction = db.desc(sort_field) if sort['desc'] else sort_field
        query = query.order_by(sort_direction)

    # Apply pagination
    query = query.offset(page_index * page_size).limit(page_size)

    # Fetch data and total count
    data_list = query.all()
    total_count = PaymentBoost.query.filter(PaymentBoost.user_id == user_id, PaymentBoost.deleted_at == None).count()

    # Format the data for response
    data_json = []
    for boost in data_list:
        boost_data = {
            'id': boost.id,
            'user_id': boost.user_id,
            'amount': boost.amount,
            'pay_date_boost': convertDateTostring(boost.pay_date_boost,'%Y-%m-%d'),
            'pay_date_boost_word': convertDateTostring(boost.pay_date_boost),
            'comment': boost.comment,
            'month': boost.month            
        }
        data_json.append(boost_data)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size

    return jsonify({
        'rows': data_json,
        'pageCount': total_pages,
        'totalRows': total_count,
    })

@app.route('/api/save-boostpg', methods=['POST'])
def save_boost_pg():
    if request.method == 'POST':
        data = request.get_json()

        user_id = data.get('user_id')
        boost_id = None
        message = ''
        result = 0

        try:
            # Convert string to date (assuming the helper functions are present)
            pay_date_boost = convertStringTodate(data['pay_date_boost'])
            month = convertDateTostring(pay_date_boost, "%b %Y")
            amount = float(data['amount'])
            comment = data['comment'] if data['comment']!="" else None

            # Create new PaymentBoost instance
            new_boost = PaymentBoost(
                user_id=user_id,
                amount=amount,
                pay_date_boost=pay_date_boost,
                month=month,
                comment=comment,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                deleted_at=None
            )

            # Add the new record to the session and commit to the database
            db.session.add(new_boost)
            db.session.commit()

            # Get the ID of the inserted record
            boost_id = new_boost.id
            result = 1
            message = 'Payment Boost account added successfully'

        except Exception as ex:
            boost_id = None
            print('Payment Boost Save Exception: ', ex)
            result = 0
            message = 'Payment Boost account addition failed'

        return jsonify({
            "boost_id": boost_id,
            "message": message,
            "result": result
        })


@app.route('/api/update-boostpg', methods=['POST'])
def update_boost_pg():
    if request.method == 'POST':
        data = request.get_json()

        user_id = data.get('user_id')
        boost_id = data.get('id')
        message = ''
        result = 0

        try:
            # Convert string to date (assuming the helper functions are present)
            pay_date_boost = convertStringTodate(data['pay_date_boost'])

            # Fetch the existing PaymentBoost record
            boost = PaymentBoost.query.filter_by(id=boost_id).first()

            amount = float(data['amount'])
            comment = data['comment'] if data['comment']!="" else None

            if boost:
                # Update the fields
                boost.user_id = user_id
                boost.pay_date_boost = pay_date_boost
                boost.updated_at = datetime.now()
                boost.amount = amount
                boost.comment = comment
                # Commit the changes to the database
                db.session.commit()

                boost_id = boost.id
                result = 1
                message = 'Payment Boost account updated successfully'
            else:
                result = 0
                message = 'Payment Boost account not found'

        except Exception as ex:
            print('Payment Boost Update Exception: ', ex)
            boost_id = None
            result = 0
            message = 'Payment Boost account update failed'

        return jsonify({
            "boost_id": boost_id,
            "message": message,
            "result": result
        })



@app.route('/api/delete-boostpg', methods=['POST'])
def delete_boost_pg():
    if request.method == 'POST':
        data = request.get_json()

        boost_account_id = None
        message = None
        error = 0
        deleted_done = 0

        try:
            # Extract the boost ID from the request data
            boost_id = data.get('id')

            # Fetch the existing PaymentBoost record
            boost = PaymentBoost.query.filter_by(id=boost_id).first()

            if boost:
                # Mark the record as deleted by setting 'deleted_at' field
                boost.deleted_at = datetime.now()

                # Commit the changes to the database
                db.session.commit()

                boost_account_id = boost.id
                deleted_done = 1
                message = 'Payment Boost account deleted successfully'
            else:
                error = 1
                deleted_done = 0
                message = 'Payment Boost account not found'

        except Exception as ex:
            print('Payment Boost account Deletion Exception: ', ex)
            boost_account_id = None
            error = 1
            deleted_done = 0
            message = 'Payment Boost account deletion failed'

        return jsonify({
            "boost_account_id": boost_account_id,
            "message": message,
            "error": error,
            "deleted_done": deleted_done
        })
