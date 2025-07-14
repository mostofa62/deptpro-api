from flask import request,jsonify, json
from sqlalchemy import func, or_
#from flask_cors import CORS, cross_origin
from pgutils import new_entry_option_data
from models import AppData, CashFlow, Income, IncomeBoost, IncomeBoostType, IncomeTransaction
from incomeutil import generate_new_transaction_data_for_income_boost, get_single_boost
from app import app
import re
from util import *
from dbpg import db

@app.route('/api/delete-income-boostpg', methods=['POST'])
def delete_income_boost_pg():
    if request.method == 'POST':
        data = json.loads(request.data)

        income_boost_id = data['id']
        admin_id = data.get('admin_id')
        key = data.get('key')
        action = 'Deleted' if key < 2 else 'Closed'
        #field = IncomeBoost.deleted_at if key < 2 else IncomeBoost.closed_at
        field = "deleted_at" if key < 2 else "closed_at"
        
        message = None
        error = 0
        deleted_done = 0

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        try:

            

            income_boost = db.session.query(IncomeBoost).filter(IncomeBoost.id == income_boost_id).first()

            if income_boost:
                if income_boost.pay_date_boost <= today:
                    
                    app_data = db.session.query(AppData).filter(AppData.user_id == income_boost.user_id).first()
                    income  = db.session.query(Income).filter(Income.id == income_boost.income_id).first()

                    if income:
                        income.total_gross_income -= income_boost.total_balance
                        income.total_net_income -= income_boost.total_balance
                        income.total_monthly_gross_income -= income_boost.total_monthly_gross_income
                        income.total_monthly_net_income -= income_boost.total_monthly_net_income
                        income.total_yearly_gross_income -= income_boost.total_yearly_gross_income
                        income.total_yearly_net_income -= income_boost.total_yearly_net_income

                        db.session.add(income)

                    if app_data:

                        app_data.total_yearly_gross_income -= income_boost.total_monthly_gross_income
                        app_data.total_yearly_net_income -= income_boost.total_monthly_net_income
                        app_data.total_monthly_gross_income -= income_boost.total_yearly_gross_income
                        app_data.total_monthly_net_income -= income_boost.total_yearly_net_income

                        db.session.add(app_data)

                    
                  
                    db.session.query(IncomeTransaction).filter(            
                        IncomeTransaction.income_boost_id == income_boost_id
                    ).delete(synchronize_session=False)

                setattr(income_boost, field, datetime.now())
                setattr(income_boost, 'admin_id', admin_id)

                message = f'Income boost {action} Successfully'
                deleted_done = 1
                db.session.commit()



            # Update the Income record
            '''
            income_boost_update = db.session.query(IncomeBoost).filter(IncomeBoost.id == income_boost_id).update(
                {field: datetime.now()}, synchronize_session=False
            )
            '''

            

            
            '''
            if income_boost_update:
                message = f'Income boost {action} Successfully'
                deleted_done = 1
                db.session.commit()
            else:
                message = f'Income boost {action} Failed'
                db.session.rollback()
                error = 1

            '''

        except Exception as ex:
            db.session.rollback()
            print('Income boost Delete Exception:', ex)
            message = f'Income boost {action} Failed'
            error = 1

        

                      
        
        return jsonify({
            "income_boost_id":income_boost_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })



@app.route('/api/income-boostpg/<int:income_id>', methods=['POST'])
def list_income_boost_pg(income_id: int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])

    # Base query
    query = db.session.query(
    IncomeBoost.id,
    IncomeBoost.earner,
    IncomeBoost.pay_date_boost,
    IncomeBoost.next_pay_date_boost,
    IncomeBoost.income_boost,    
    IncomeBoost.repeat_boost,
    IncomeBoost.total_balance,
    IncomeBoostType.name.label("income_boost_source")
    ).filter(
        IncomeBoost.income_id == income_id,
        IncomeBoost.deleted_at.is_(None),
        IncomeBoost.closed_at.is_(None)
    ).join(IncomeBoostType, IncomeBoost.income_boost_source_id == IncomeBoostType.id, isouter=True)

    if global_filter:
        pattern_str = r'^\d{4}-\d{2}-\d{2}$'
        pay_date_boost = None

        if re.match(pattern_str, global_filter):
            pay_date_boost = datetime.strptime(global_filter, "%Y-%m-%d")

        query = query.filter(or_(
            IncomeBoost.earner.ilike(f"%{global_filter}%"),
            IncomeBoost.pay_date_boost == pay_date_boost,
            IncomeBoostType.name.ilike(f"%{global_filter}%")
        ))

    # Sorting
    sort_params = [IncomeBoost.created_at.desc()]  # Default sorting
    for sort in sort_by:
        sort_field = getattr(IncomeBoost, sort['id'], None)
        if sort_field:
            sort_params.append(sort_field.desc() if sort['desc'] else sort_field.asc())

    query = query.order_by(*sort_params)

    # Pagination
    total_count = query.count()
    total_pages = (total_count + page_size - 1) // page_size
    results = query.offset(page_index * page_size).limit(page_size).all()

    # Formatting results
    data_list = []
    for entry in results:
        data_list.append({
            'id': entry.id,
            'earner': entry.earner,
            'pay_date_boost': convertDateTostring(entry.pay_date_boost),
            'next_pay_date_boost': convertDateTostring(entry.next_pay_date_boost),
            'income_boost_source': entry.income_boost_source if entry.income_boost_source else None,
            'income_boost': entry.income_boost,
            'repeat_boost':entry.repeat_boost,
            'total_balance':entry.total_balance
        })

    # Aggregate total income boost
    total_income_boost = db.session.query(func.sum(IncomeBoost.income_boost)).filter(
        IncomeBoost.income_id == income_id,
        IncomeBoost.deleted_at.is_(None)
    ).scalar() or 0

    return jsonify({
        'rows': data_list,
        'pageCount': total_pages,
        'totalRows': total_count,
        'extra_payload': {
            'total_income_boost': total_income_boost,
        }
    })



@app.route('/api/save-income-boostpg', methods=['POST'])
async def save_income_boost_pg():
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']
        admin_id = data['admin_id']
        income_id = data['income']['value']
        income_boost_id = None
        message = ''
        result = 0

        total_gross_income= \
        total_net_income=\
        total_monthly_gross_income=\
        total_monthly_net_income=\
        total_yearly_gross_income=\
        total_yearly_net_income = 0.0

        current_month = int(convertDateTostring(datetime.now(),'%Y%m'))
        

        # Retrieve the Income record using SQLAlchemy query
        income_entry = db.session.query(
            Income.total_gross_income, 
            Income.total_net_income, 
            Income.total_monthly_gross_income,
            Income.total_monthly_net_income,
            Income.total_yearly_gross_income,
            Income.total_yearly_net_income,          
            Income.commit, 
            Income.user_id
        ).filter_by(id=income_id).first()
       

        total_gross_income, total_net_income,total_monthly_gross_income,total_monthly_net_income,total_yearly_gross_income,total_yearly_net_income,commit,user_id= income_entry

        pay_date_boost = convertStringTodate(data['pay_date_boost'])
        repeat = data['repeat_boost']['value']
        repeat_boost = data['repeat_boost']['value'] if data['repeat_boost']['value'] > 0 else None
        income_boost = float(data.get("income_boost", 0))
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        merge_data = {    
            'income_id': income_id,            
            'income_boost_source_id': new_entry_option_data(data['income_boost_source'], IncomeBoostType, user_id),                
            'user_id': user_id,
            'admin_id':admin_id,
            'earner':data['earner'],
            'repeat_boost':data['repeat_boost'],    
            'income_boost': income_boost,         
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "deleted_at": None,
            "closed_at": None,  
            'pay_date_boost': pay_date_boost,                
            'next_pay_date_boost': None, 
            'total_balance': 0,                                      
        }

        session = db.session
        

        if pay_date_boost <= today:
            total_balance = 0
            
            income_boost_entry = IncomeBoost(**merge_data)
            session.add(income_boost_entry)
            session.flush()  # To get the ID of the inserted record
            income_boost_id = income_boost_entry.id
           

            if repeat > 0:
                # Handle the case for repeated income boosts
                contribution_data = generate_new_transaction_data_for_income_boost(
                    total_balance,
                    income_boost,
                    pay_date_boost,
                    repeat_boost,
                    commit,
                    data['income']['value'],
                    income_boost_id,
                    user_id,
                    total_gross_income,
                    total_net_income                 
                )
                income_transaction_list = contribution_data['income_transaction']
                total_balance_b = contribution_data['total_boost_for_period']
                total_gross_income = contribution_data['total_gross_for_period']
                total_net_income = contribution_data['total_net_for_period']
                next_contribution_date_b = contribution_data['next_pay_date']
                is_single = contribution_data['is_single']
                total_monthly_gross_income_b = contribution_data['total_monthly_gross_income']
                total_monthly_net_income_b = contribution_data['total_monthly_net_income']
                total_yearly_gross_income_b = contribution_data['total_yearly_gross_income']
                total_yearly_net_income_b = contribution_data['total_yearly_net_income']

                # Update the boost status
                boost_status = {
                    'id': income_boost_id,
                    'next_pay_date_boost': next_contribution_date_b,
                    'total_balance': total_balance_b,
                    'total_monthly_gross_income':total_monthly_gross_income_b,
                    'total_monthly_net_income':total_monthly_net_income_b,
                    'total_yearly_gross_income':total_yearly_gross_income_b,
                    'total_yearly_net_income':total_yearly_net_income_b,
                    'closed_at': None
                }

                total_monthly_gross_income = total_monthly_gross_income + total_monthly_gross_income_b
                total_monthly_net_income = total_monthly_net_income + total_monthly_net_income_b
                total_yearly_gross_income = total_yearly_gross_income + total_yearly_gross_income_b
                total_yearly_net_income = total_yearly_net_income + total_yearly_net_income_b

                # Update the income record
                update_data = {
                    "total_net_income": total_net_income,            
                    'total_gross_income': total_gross_income, 
                    'total_monthly_gross_income' :total_monthly_gross_income,
                    'total_monthly_net_income':total_monthly_net_income,
                    'total_yearly_gross_income':total_yearly_gross_income,
                    'total_yearly_net_income':total_yearly_net_income,
                    'updated_at': datetime.now()              
                }

                try:

                    if len(income_transaction_list)> 0:
                        if is_single:
                            session.add(IncomeTransaction(**income_transaction_list))
                        else:
                            session.add_all([IncomeTransaction(**entry) for entry in income_transaction_list])

                    # Update the status of income boost in the IncomeBoost model
                    session.query(IncomeBoost).filter_by(id=boost_status['id']).update({
                        'next_pay_date_boost': boost_status['next_pay_date_boost'],
                        'total_balance': boost_status['total_balance'],
                        'total_monthly_gross_income': boost_status['total_monthly_gross_income'],
                        'total_monthly_net_income': boost_status['total_monthly_net_income'],
                        'total_yearly_gross_income': boost_status['total_yearly_gross_income'],
                        'total_yearly_net_income': boost_status['total_yearly_net_income'],                        
                        'closed_at': boost_status['closed_at']
                    })

                    session.query(Income).filter_by(id=income_id).update(update_data)

                    app_data = session.query(AppData).filter(AppData.user_id == user_id).first()

                    app_data.total_yearly_gross_income += total_yearly_gross_income_b
                    app_data.total_yearly_net_income += total_yearly_net_income_b
                    app_data.total_monthly_gross_income += total_monthly_gross_income_b
                    app_data.total_monthly_net_income += total_monthly_net_income_b
                    app_data.income_updated_at = None                   
                    session.add(app_data)

                    cashflow_data = session.query(CashFlow).filter(
                        CashFlow.user_id == user_id,
                        CashFlow.month == current_month
                    ).first()
                    cashflow_data.updated_at = None

                    session.add(cashflow_data)
                    
                    session.commit()

                    result = 1
                    message = 'Income boost added Succefull'
                        

                except Exception as ex:

                    income_boost_id = None
                    print('Income Boost Save Exception: ',ex)
                    result = 0
                    message = 'Income boost addition Failed'
                    session.rollback()
            else:

                contribution_breakdown_b = get_single_boost(
                                total_balance,
                                income_boost,
                                pay_date_boost,
                                repeat_boost,
                                total_gross_income,
                                total_net_income                               
                                )
                breakdown_b = contribution_breakdown_b['income_transaction']
                total_balance_b = contribution_breakdown_b['total_boost_for_period']
                total_gross_income = contribution_breakdown_b['total_gross_for_period']
                total_net_income = contribution_breakdown_b['total_net_for_period']
                next_contribution_date_b = contribution_breakdown_b['next_pay_date']
                total_monthly_gross_income_b = contribution_breakdown_b['total_monthly_gross_income']
                total_monthly_net_income_b = contribution_breakdown_b['total_monthly_net_income']
                total_yearly_gross_income_b = contribution_breakdown_b['total_yearly_gross_income']
                total_yearly_net_income_b = contribution_breakdown_b['total_yearly_net_income']

                            

                income_transaction_list = {
                        'income_id':income_id,
                        'income_boost_id':income_boost_id,
                        'commit':commit,
                        'user_id':user_id,
                        **breakdown_b
                }

                # Update the boost status
                boost_status = {
                    'id': income_boost_id,
                    'next_pay_date_boost': next_contribution_date_b,
                    'total_balance': total_balance_b,
                    'total_monthly_gross_income' :total_monthly_gross_income_b,
                    'total_monthly_net_income':total_monthly_net_income_b,
                    'total_yearly_gross_income':total_yearly_gross_income_b,
                    'total_yearly_net_income':total_yearly_net_income_b,
                    'closed_at': None
                }

                total_monthly_gross_income = total_monthly_gross_income + total_monthly_gross_income_b
                total_monthly_net_income = total_monthly_net_income + total_monthly_net_income_b
                total_yearly_gross_income = total_yearly_gross_income + total_yearly_gross_income_b
                total_yearly_net_income = total_yearly_net_income + total_yearly_net_income_b

                # Update the income record
                update_data = {
                    "total_net_income": total_net_income,            
                    'total_gross_income': total_gross_income,
                    'total_monthly_gross_income' :total_monthly_gross_income,
                    'total_monthly_net_income':total_monthly_net_income,
                    'total_yearly_gross_income':total_yearly_gross_income,
                    'total_yearly_net_income':total_yearly_net_income,       
                    'updated_at': datetime.now()              
                }

                try:

                    session.add(IncomeTransaction(**income_transaction_list))
                    # Update the status of income boost in the IncomeBoost model
                    session.query(IncomeBoost).filter_by(id=boost_status['id']).update({
                        'next_pay_date_boost': boost_status['next_pay_date_boost'],
                        'total_balance': boost_status['total_balance'],
                        'total_monthly_gross_income': boost_status['total_monthly_gross_income'],
                        'total_monthly_net_income': boost_status['total_monthly_net_income'],
                        'total_yearly_gross_income': boost_status['total_yearly_gross_income'],
                        'total_yearly_net_income': boost_status['total_yearly_net_income'],                        
                        'closed_at': boost_status['closed_at']
                    })

                    session.query(Income).filter_by(id=income_id).update(update_data)

                    app_data = session.query(AppData).filter(AppData.user_id == user_id).first()

                    app_data.total_yearly_gross_income += total_yearly_gross_income_b
                    app_data.total_yearly_net_income += total_yearly_net_income_b
                    app_data.total_monthly_gross_income += total_monthly_gross_income_b
                    app_data.total_monthly_net_income += total_monthly_net_income_b
                    app_data.income_updated_at = None
                    
                    session.add(app_data)

                    cashflow_data = session.query(CashFlow).filter(
                        CashFlow.user_id == user_id,
                        CashFlow.month == current_month
                    ).first()
                    cashflow_data.updated_at = None

                    session.add(cashflow_data)

                    session.commit()

                    result = 1
                    message = 'Income boost added Succefull'

                except Exception as ex:
                                                                
                    income_boost_id = None
                    print('Income Boost Save Exception: ',ex)
                    result = 0
                    message = 'Income boost addition Failed'
                    session.rollback()                     

                        

        else:
                
            try:
                income_boost_entry = IncomeBoost(**merge_data)
                session.add(income_boost_entry)
                session.commit()
                income_boost_id = income_boost_entry.id
                message = 'Income boost added Succefull'
                result = 1
            except Exception as ex:
                income_boost_id = None
                session.rollback()
                print('Income Save Exception: ', ex)
                message = 'Income boost addition Failed'
                result = 0
        
        session.close()

        return jsonify({
            "income_id": income_boost_id,
            "message": message,
            "result": result
        })



