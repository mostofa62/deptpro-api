from flask import request,jsonify
#from flask_cors import CORS, cross_origin
from app import app
import re
from util import *
from datetime import datetime
from models import AppData, CashFlow, PaymentBoost
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
        admin_id = data.get('admin_id')
        boost_id = None
        message = ''
        result = 0
        current_datetime = datetime.now()
        current_boost_month = int(convertDateTostring(current_datetime,'%Y%m'))

        try:
            # Convert string to date (assuming the helper functions are present)
            pay_date_boost = convertStringTodate(data['pay_date_boost'])
            pay_date_boost_month = int(convertDateTostring(pay_date_boost,'%Y%m'))
            month = convertDateTostring(pay_date_boost, "%b %Y")
            amount = float(data['amount'])
            comment = data['comment'] if data['comment']!="" else None

            # Create new PaymentBoost instance
            new_boost = PaymentBoost(
                user_id=user_id,
                admin_id=admin_id,
                amount=amount,
                pay_date_boost=pay_date_boost,
                month=month,
                comment=comment,
                created_at=current_datetime,
                updated_at=current_datetime,
                deleted_at=None
            )

            # Add the new record to the session and commit to the database
            db.session.add(new_boost)

            if pay_date_boost_month == current_boost_month:
                app_data = db.session.query(AppData).filter(AppData.user_id == user_id).first()
                if app_data:                
                    if app_data.current_debt_boost_month != None and app_data.current_debt_boost_month == current_boost_month:
                        app_data.total_monthly_debt_boost += amount
                    else:
                        app_data.total_monthly_debt_boost =  amount
                        app_data.current_debt_boost_month = current_boost_month
                else:
                    app_data = AppData(
                            user_id=user_id,
                            current_debt_boost_month = current_boost_month,
                            total_monthly_debt_boost=amount                        
                        )
                db.session.add(app_data)

                cashflow_data = db.session.query(CashFlow).filter(
                            CashFlow.user_id == user_id,
                            CashFlow.month == current_boost_month
                        ).first()
                if not cashflow_data:
                    cashflow_data = CashFlow(
                        user_id = user_id,
                        amount = 0,
                        month = current_boost_month,
                        updated_at = None
                    )
                else:
                    cashflow_data.updated_at = None                    
                db.session.add(cashflow_data)
            
            
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
        admin_id = data.get('admin_id')
        boost_id = data.get('id')
        message = ''
        result = 0
        current_datetime = datetime.now()
        current_boost_month = int(convertDateTostring(current_datetime,'%Y%m'))
        
        try:
            # Convert string to date (assuming the helper functions are present)
            pay_date_boost = convertStringTodate(data['pay_date_boost'])
            pay_date_boost_month = int(convertDateTostring(pay_date_boost,'%Y%m'))
            month = convertDateTostring(pay_date_boost,"%b %Y")

            # Fetch the existing PaymentBoost record
            boost = db.session.query(PaymentBoost).filter(PaymentBoost.id==boost_id).first()
            # print('boost',boost)

            amount = float(data['amount'])
            comment = data['comment'] if data['comment']!="" else None
            if boost:
                previous_amount = boost.amount
                previous_pay_date_boost = boost.pay_date_boost
                change_found_amount = False if are_floats_equal(previous_amount, amount) else True
                change_found_pay_date_boost = False if previous_pay_date_boost == pay_date_boost else True
                any_change = change_found_amount or change_found_pay_date_boost
                
                # Update the fields
                boost.user_id = user_id                
                boost.admin_id = admin_id                
                boost.updated_at = current_datetime
                if change_found_pay_date_boost:
                    boost.pay_date_boost = pay_date_boost
                    boost.month = month
                if change_found_amount:
                    boost.amount = amount
                boost.comment = comment

                db.session.add(boost)
                # Commit the changes to the database
                if any_change and pay_date_boost_month == current_boost_month:                    

                    app_data = db.session.query(AppData).filter(AppData.user_id == user_id).first() 
                    if app_data:                        
                        if app_data.current_debt_boost_month == current_boost_month:
                            app_data.total_monthly_debt_boost -= previous_amount
                            app_data.total_monthly_debt_boost += amount
                        else:
                            app_data.total_monthly_debt_boost =  amount
                            app_data.current_debt_boost_month = current_boost_month                        
                        db.session.add(app_data)
                    
                    cashflow_data = db.session.query(CashFlow).filter(
                        CashFlow.user_id == user_id,
                        CashFlow.month == current_boost_month
                    ).first()
                    if cashflow_data:
                        cashflow_data.updated_at = None                
                        db.session.add(cashflow_data)

                
                db.session.commit()

                boost_id = boost.id
                result = 1
                message = 'Payment Boost account updated successfully'
            else:
                result = 0
                message = 'Payment Boost account not found'

        except Exception as ex:
            print('Payment Boost Update Exception: ', ex)
            db.session.rollback()
            boost_id = None
            result = 0
            message = 'Payment Boost account update failed'
        finally:
            db.session.close()

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
        admin_id = data.get('admin_id')
        current_datetime = datetime.now()
        current_boost_month = int(convertDateTostring(current_datetime,'%Y%m'))

        try:
            # Extract the boost ID from the request data
            boost_id = data.get('id')

            # Fetch the existing PaymentBoost record
            boost = PaymentBoost.query.filter_by(id=boost_id).first()

            if boost:
                user_id = boost.user_id
                previous_amount = boost.amount
                previous_pay_date_boost = boost.pay_date_boost
                pay_date_boost_month = int(convertDateTostring(previous_pay_date_boost,'%Y%m'))
                # Mark the record as deleted by setting 'deleted_at' field
                boost.deleted_at = current_datetime
                boost.admin_id = admin_id
                if pay_date_boost_month == current_boost_month:
                    app_data = db.session.query(AppData).filter(AppData.user_id == user_id).first() 
                    if app_data:                        
                        if app_data.current_debt_boost_month == current_boost_month:
                            app_data.total_monthly_debt_boost -= previous_amount                                                      
                        db.session.add(app_data)
                    
                    cashflow_data = db.session.query(CashFlow).filter(
                        CashFlow.user_id == user_id,
                        CashFlow.month == current_boost_month
                    ).first()
                    if cashflow_data:
                        cashflow_data.updated_at = None                
                        db.session.add(cashflow_data)

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
