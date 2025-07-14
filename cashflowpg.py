from flask import request,jsonify
#from flask_cors import CORS, cross_origin
from app import app

from util import *
from models import CashFlow
from dbpg import db

@app.route('/api/cashflowpg/<int:user_id>', methods=['POST'])
def list_cashflow_pg(user_id: int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)    
    cashflow_list = []
    session = db.session
    total_pages = 0
    total_count = 0
    try:

        filters = [
            CashFlow.user_id == user_id,        
        ]

        query = session.query(
            CashFlow.id,
            CashFlow.month,
            CashFlow.amount
        ).filter(*filters)

        
        

        
        query = query.order_by(CashFlow.month.desc(), CashFlow.id.desc())

        # Count before pagination
        total_count = query.count()

        # Pagination
        query = query.offset(page_index * page_size).limit(page_size)
        
        
        results = query.all()

       
        for result in results:
            cashflow_data={
                'id':result.id,
                'month_word':convertNumberToDate(result.month),
                'amount':result.amount
            }
            cashflow_list.append(cashflow_data)

        total_pages = (total_count + page_size - 1) // page_size

    except Exception as e:
        #return year_month_wise_counts
        cashflow_list = []

    finally:
        session.close()

    return jsonify({
        'rows': cashflow_list,
        'pageCount': total_pages,
        'totalRows': total_count,
    })