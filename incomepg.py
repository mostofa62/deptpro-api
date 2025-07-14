import re
from flask import Flask,request,jsonify
from incomeutil import calculate_periods, generate_new_transaction_data_for_income
from app import app
from bson.json_util import dumps
from util import *
from datetime import datetime
from models import AppData, CashFlow, Income, IncomeBoost, IncomeLog, IncomeTransaction, IncomeSourceType
from dbpg import db
from pgutils import *
from sqlalchemy import func, insert, select, update
#from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import joinedload,aliased
from sqlalchemy import or_, desc, asc

from db import my_col
income_accounts_logs = my_col('income_accounts_logs')
calender_data = my_col('calender_data')

IncomeTxn = aliased(IncomeTransaction)

@app.route('/api/delete-incomepg', methods=['POST'])
async def delete_income_pg():
    data = request.get_json()
    user_id = data.get('user_id')
    admin_id = data.get('admin_id')
    income_id = data.get('id')
    key = data.get('key')
    action = 'Deleted' if key < 2 else 'Closed'
    field = Income.deleted_at if key < 2 else Income.closed_at

    message = None
    error = 0
    deleted_done = 0

    session = db.session

    try:

        stmt = select(
            Income.id,                                         
            Income.total_yearly_gross_income,
            Income.total_yearly_net_income,
            Income.total_monthly_gross_income,
            Income.total_monthly_net_income                     
        ).where(Income.id == income_id)

        previous_income = session.execute(stmt).mappings().first()

        app_data = session.query(AppData).filter(AppData.user_id == user_id).first()

        app_data.total_yearly_gross_income -= previous_income['total_yearly_gross_income'] if app_data.total_yearly_gross_income >= previous_income['total_yearly_gross_income'] else 0
        app_data.total_yearly_net_income -= previous_income['total_yearly_net_income'] if app_data.total_yearly_net_income >= previous_income['total_yearly_net_income']  else 0
        app_data.total_monthly_net_income -= previous_income['total_monthly_net_income'] if app_data.total_monthly_net_income >= previous_income['total_monthly_net_income'] else 0
        app_data.total_monthly_gross_income -= previous_income['total_monthly_gross_income'] if app_data.total_monthly_gross_income >= previous_income['total_monthly_gross_income'] else 0
        app_data.income_updated_at = None
        session.add(app_data)


                
        # Update the Income record
        income_update = session.query(Income).filter(Income.id == income_id).update(
            {
                field: datetime.now(),
                Income.admin_id:admin_id
                #Income.calender_at: None
            }, synchronize_session=False
        )

        result = calender_data.delete_one({'module_id': 'income', 'data.data_id': income_id} )  

                             

        # Ensure the update was successful before committing
        if income_update:
            session.commit()  # Commit only once
            message = f'Income account {action} Successfully'
            deleted_done = 1
        else:
            session.rollback()  # Rollback everything if update fails
            message = f'Income account {action} Failed'
            error = 1


    except Exception as ex:
        session.rollback()
        print('Income account Delete Exception:', ex)
        message = f'Income account {action} Failed'
        error = 1

    finally:
        session.close()

    return jsonify({
        "income_account_id": income_id if deleted_done else None,
        "message": message,
        "error": error,
        "deleted_done": deleted_done
    })

@app.route("/api/income-allpg/<int:id>", methods=['GET'])
async def get_income_all_pg(id:int):

    session = db.session    
    
    stmt = (
        select(
            Income.id,
            Income.user_id,            
            Income.earner,
            Income.gross_income,
            Income.net_income,
            Income.pay_date,
            Income.next_pay_date,
            Income.repeat,
            Income.total_gross_income,
            Income.total_net_income,            
            IncomeSourceType.name.label("income_source_name"),
        )
        .join(IncomeSourceType, Income.income_source_id == IncomeSourceType.id, isouter=True)
        .where(Income.id == id)
    )

    income = session.execute(stmt).mappings().first()

    if not income:
        session.close()
        return jsonify({"income":None,"error": "Income record not found"})

    # Convert to dict and format dates
    income_data = {key: income[key] for key in income.keys()}
    
    income_data['pay_date_word'] = convertDateTostring(income_data['pay_date'])
    income_data['pay_date'] = convertDateTostring(income_data['pay_date'],"%Y-%m-%d")

    income_data['next_pay_date_word'] = convertDateTostring(income_data['next_pay_date'])
    income_data['next_pay_date'] = convertDateTostring(income_data['next_pay_date'],"%Y-%m-%d")


    
    income_data['income_source'] = income_data.pop("income_source_name", None)

    income_data['repeat'] = income_data['repeat']['label']
    
    if session:
        session.close()

    return jsonify({
        "payLoads":{
            "income":income_data
        }
    })


@app.route("/api/incomepg/<int:id>", methods=['GET'])
async def view_income_pg(id: int):
    # Fetch income with a join to IncomeSourceType

    session =  db.session
    stmt = (
        select(
            Income.id,
            Income.user_id,
            Income.income_source_id,
            Income.earner,
            Income.gross_income,
            Income.net_income,
            Income.pay_date,
            Income.repeat,
            Income.note,
            IncomeSourceType.name.label("income_source_name"),
        )
        .join(IncomeSourceType, Income.income_source_id == IncomeSourceType.id, isouter=True)
        .where(Income.id == id)
    )

    income = session.execute(stmt).mappings().first()

    if not income:
        session.close()
        return jsonify({"income":None,"error": "Income record not found"})

    # Convert to dict and format dates
    income_data = {key: income[key] for key in income.keys()}
    
    if income_data["pay_date"]:
        income_data["pay_date"] = convertDateTostring(income_data["pay_date"], "%Y-%m-%d")

    # Attach income source with value/label structure
    income_data["income_source"] = {
        "value": income_data.pop("income_source_id"),
        "label": income_data.pop("income_source_name", None)  # Handle cases where it's None
    }

    if session:
        session.close()

    return jsonify({"income": income_data})



@app.route('/api/incomepg/<int:user_id>', methods=['POST'])
async def list_income_pg(user_id: int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])
    action = request.args.get("action", None)
    current_month = int(datetime.now().strftime('%Y%m'))

    session = db.session
    try:
        # Subquery for monthly net income boost
        income_txn_subquery = (
            select(
                IncomeTransaction.income_id,
                func.sum(IncomeTransaction.net_income).label("net_income_boost_monthly")
            )
            .filter(
                IncomeTransaction.income_boost_id != None,
                IncomeTransaction.month == current_month
            )
            .group_by(IncomeTransaction.income_id)
            .alias("income_txn_subquery")
        )

        # Build base query
        filters = [
            Income.user_id == user_id,
            Income.deleted_at == None
        ]
        filters.append(Income.closed_at != None if action else Income.closed_at == None)

        query = session.query(
            Income,
            func.coalesce(income_txn_subquery.c.net_income_boost_monthly, 0).label("net_income_boost_monthly")
        ).outerjoin(
            income_txn_subquery, income_txn_subquery.c.income_id == Income.id
        ).filter(*filters)

        # Global filter
        if global_filter:
            income_source_subquery = select(IncomeSourceType.id).where(
                IncomeSourceType.name.ilike(f"%{global_filter}%")
            )
            try:
                pay_date = convertStringTodate(global_filter, "%Y-%m-%d")
            except ValueError:
                pay_date = None

            query = query.filter(
                or_(
                    Income.earner.ilike(f"%{global_filter}%"),
                    Income.pay_date == pay_date,
                    Income.income_source_id.in_(income_source_subquery)
                )
            )

        # Sorting
        sort_params = []
        for sort in sort_by:
            field = getattr(Income, sort["id"], None)
            if field is not None:
                sort_params.append(field.desc() if sort["desc"] else field.asc())
        if sort_params:
            query = query.order_by(*sort_params)

        # Count before pagination
        total_count = query.count()

        # Pagination
        query = query.offset(page_index * page_size).limit(page_size)
        results = query.all()

        # App data
        app_data = session.query(AppData).filter(AppData.user_id == user_id).first()

        income_list = [
            {
                "id": inc.id,
                "earner": inc.earner,
                "income_source": inc.income_source.name if inc.income_source else None,
                "gross_income": inc.gross_income,
                "net_income": inc.net_income,
                "repeat": inc.repeat,
                "total_gross_income": inc.total_gross_income,
                "total_net_income": inc.total_net_income,
                "pay_date": convertDateTostring(inc.pay_date),
                "next_pay_date": convertDateTostring(inc.next_pay_date),
                "total_monthly_gross_income": inc.total_monthly_gross_income,
                "total_monthly_net_income": inc.total_monthly_net_income,
                "total_yearly_net_income": inc.total_yearly_net_income,
                "total_yearly_gross_income": inc.total_yearly_gross_income,
                "net_income_boost_monthly": net_boost if net_boost is not None else 0,
            }
            for inc, net_boost in results
        ]

        return jsonify({
            'rows': income_list,
            'pageCount': (total_count + page_size - 1) // page_size,
            'totalRows': total_count,
            'extra_payload': {
                'total_net_income': app_data.total_monthly_net_income if app_data else 0,
                'total_gross_income': app_data.total_monthly_gross_income if app_data else 0,
                'total_net_income_yearly': app_data.total_yearly_net_income if app_data else 0,
                'total_gross_income_yearly': app_data.total_yearly_gross_income if app_data else 0
            }
        })

    except Exception as e:
        return jsonify({
            'rows': [],
            'pageCount': 0,
            'totalRows': 0,
            'extra_payload': {
                'total_net_income': 0,
                'total_gross_income': 0
            },
            'error': str(e)
        })

    finally:
        session.close()



@app.route('/api/create-income', methods=['POST'])
def create_income():
    if request.method == 'POST':
        data = request.get_json()

        user_id = data['user_id']
        admin_id = data['admin_id']

        income_id = None
        message = ''
        result = 0
        current_month = int(convertDateTostring(datetime.now(),'%Y%m'))

        # Get a database session from get_db
        session = db.session
        try:            
            
                # Begin transaction                
                net_income = float(data.get("net_income", 0))
                gross_income = float(data.get("gross_income", 0))

                repeat = int(data['repeat']['value']) if int(data['repeat']['value']) > 0 else None                
                pay_date = convertStringTodate(data['pay_date'])
                income_source_id = new_entry_option_data(data['income_source'], IncomeSourceType, user_id)  # Removed the comma

                total_gross_income = 0
                total_net_income = 0
                total_monthly_gross_income = 0
                total_monthly_net_income = 0
                total_yearly_gross_income = 0
                total_yearly_net_income = 0
                
                commit = datetime.now()

                del data['income_source']

                append_data = {
                        'income_source_id':income_source_id,                        
                        'user_id':user_id,
                        'admin_id':admin_id,
                        'net_income':net_income,
                        'gross_income':gross_income,
                        'total_net_income':total_net_income,
                        'total_gross_income':total_gross_income,                                                
                        "created_at":datetime.now(),
                        "updated_at":datetime.now(),
                        "deleted_at":None,
                        "closed_at":None,
                        'pay_date':pay_date,
                        'next_pay_date':None,
                        'commit':commit,
                        "deleted_at":None,
                        "closed_at":None                               
                    }
                    #print('data',data)
                    #print('appendata',append_data)            

                merge_data = data | append_data                

                # Create the income record
                income_record = Income(                    
                    **merge_data
                )

                # Add the income record to the session
                session.add(income_record)

                # Flush the session to generate the ID without committing
                session.flush()


                # Get the generated income ID
                income_id = income_record.id

                # Generate transactions based on income details
                income_transaction_generate = generate_new_transaction_data_for_income(
                    gross_income, net_income, pay_date, repeat, commit, income_id, user_id
                )
                

                income_transaction_list = income_transaction_generate['income_transaction']
                total_gross_income = income_transaction_generate['total_gross_for_period']
                total_net_income = income_transaction_generate['total_net_for_period']
                next_pay_date = income_transaction_generate['next_pay_date']
                is_single = income_transaction_generate['is_single']
                total_monthly_gross_income = income_transaction_generate['total_monthly_gross_income']
                total_monthly_net_income = income_transaction_generate['total_monthly_net_income']
                total_yearly_gross_income = income_transaction_generate['total_yearly_gross_income']
                total_yearly_net_income = income_transaction_generate['total_yearly_net_income']

                #print('generate monthly',total_monthly_gross_income, total_monthly_net_income)
                #print('generated yearly', total_yearly_gross_income, total_yearly_net_income)

                income_transaction_data = None
                if len(income_transaction_list) > 0:
                    # Insert transactions into the database
                    if is_single > 0:
                        income_transaction_data = IncomeTransaction(**income_transaction_list)
                        session.add(income_transaction_data)
                    else:
                        income_transaction_data = [IncomeTransaction(**txn) for txn in income_transaction_list]
                        session.add_all(income_transaction_data)

                

                # Update income record with transaction totals
                income_record.total_gross_income = total_gross_income
                income_record.total_net_income = total_net_income
                income_record.next_pay_date = next_pay_date
                income_record.total_monthly_gross_income = total_monthly_gross_income
                income_record.total_monthly_net_income = total_monthly_net_income
                income_record.total_yearly_gross_income = total_yearly_gross_income
                income_record.total_yearly_net_income = total_yearly_net_income
                income_record.updated_at = datetime.now()

                               
                app_data = session.query(AppData).filter(AppData.user_id == user_id).first()

                if app_data:
                    # Update the existing record
                    app_data.total_yearly_gross_income += total_yearly_gross_income
                    app_data.total_yearly_net_income += total_yearly_net_income
                    app_data.total_monthly_gross_income += total_monthly_gross_income
                    app_data.total_monthly_net_income += total_monthly_net_income
                    app_data.income_updated_at = None
                    
                    
                else:
                    # Insert a new record if the user doesn't exist
                    app_data = AppData(
                        user_id=user_id,
                        total_yearly_gross_income=total_yearly_gross_income,
                        total_yearly_net_income=total_yearly_net_income,
                        total_monthly_gross_income=total_monthly_gross_income,
                        total_monthly_net_income=total_monthly_net_income,
                        income_updated_at=None
                    )

                session.add(app_data)
                print('income_id', income_id)

                cashflow_data = session.query(CashFlow).filter(
                        CashFlow.user_id == user_id,
                        CashFlow.month == current_month
                    ).first()
                if not cashflow_data:
                    cashflow_data = CashFlow(
                        user_id = user_id,
                        amount = 0,
                        month = current_month,
                        updated_at = None
                    )
                else:
                    cashflow_data.updated_at = None
                
                session.add(cashflow_data)
                
                message = 'Income account added successfully'
                session.commit()  # Commit the transaction
                result = 1
                
        except Exception as e:
            income_id = None
            message = 'Income account addition failed'
            session.rollback()  # Rollback on error
            print(f"Error income income data: {str(e)}")
            result = 0
        finally:
            session.close()            

        return jsonify({
            "income_id": income_id,
            "message": message,
            "result": result
        })


def income_accounts_log_entry(
                            income_id,          
                            user_id,
                            income_account_log_data
                              ):
    income_account_data = None    

    income_acc_query = {
                "income_id": income_id,                
                "user_id":user_id,
                
    }
    newvalues = { "$set":  income_account_log_data }
    income_account_data = income_accounts_logs.update_one(income_acc_query,newvalues,upsert=True)
    return income_account_data

@app.route('/api/edit-income/<int:id>', methods=['POST'])
def edit_income(id: int):

    if request.method == 'POST':
        data = json.loads(request.data)
        user_id = data['user_id']
        admin_id = data['admin_id']
        income_id = id
        message = ''
        result = 0
        session = db.session
        stmt = select(
            Income.id,
            Income.earner,
            Income.income_source,
            Income.income_source_id,                              
            Income.gross_income,
            Income.net_income,
            Income.pay_date,
            Income.total_net_income,
            Income.total_gross_income,           
            Income.total_yearly_gross_income,
            Income.total_yearly_net_income,
            Income.total_monthly_gross_income,
            Income.total_monthly_net_income,
            Income.repeat,  
            Income.commit,                     
        ).where(Income.id == income_id)
        previous_income = session.execute(stmt).mappings().first()       
        net_income = float(data.get("net_income", 0))
        gross_income = float(data.get("gross_income", 0))
        
        repeat = data['repeat']['value'] if data['repeat']['value'] > 0 else None

        previous_gross_income = float(previous_income['gross_income'])
        previous_net_income = float(previous_income['net_income'])
        previous_repeat = previous_income['repeat']['value'] if previous_income['repeat']['value'] > 0 else None
        previous_commit = previous_income['commit']
        previous_income_source_id = previous_income['income_source_id']

        income_source_id = data['income_source']['value']
        if income_source_id == previous_income_source_id:
            income_source_id = previous_income_source_id
        else:    
            income_source_id = new_entry_option_data(data['income_source'], IncomeSourceType, user_id)  # Removed the comma

        change_found_gross = False if are_floats_equal(previous_gross_income, gross_income) else True
        change_found_net = False if are_floats_equal(previous_net_income, net_income) else True
        change_found_repat = False if previous_repeat == repeat else True

        any_change = change_found_gross or change_found_net or change_found_repat
        append_data = {
            'income_source_id': income_source_id,
            'user_id': user_id,
            'admin_id':admin_id,
            'net_income': net_income,
            'gross_income': gross_income,                                                       
            "updated_at": datetime.now(),                                                                                   
        }

        merge_data = data | append_data

        del merge_data['income_source']
        del merge_data['pay_date']
        del merge_data['total_gross_income']
        del merge_data['total_net_income']
        try:

            if any_change:
                commit = datetime.now()

                stmt_update = update(Income).where(Income.id == income_id).values(                                            
                        calender_at=None,
                        commit=commit,  # Replace with the actual commit value
                        **merge_data  # This unpacks additional fields to update
                    )
                session.execute(stmt_update)
                existing_log = db.session.query(IncomeLog).filter_by(
                    income_id=income_id,
                    commit=previous_commit
                ).first()

                if not existing_log:
                    previous_income_row = dict(previous_income)
                    previous_income_row['pay_date'] = convertDateTostring(previous_income['pay_date'],"%Y-%m-%d %H:%M:%S.%f")
                    previous_income_row['commit'] = convertDateTostring(previous_commit,"%Y-%m-%d %H:%M:%S.%f")
                    print('previous_income_row',previous_income_row)
                    new_log = IncomeLog(
                        income_id=income_id,
                        user_id=user_id,           # supply actual user_id
                        admin_id=admin_id,       # or actual admin_id if available
                        commit=previous_commit,
                        data=previous_income_row  # or actual data dict
                    )

                    session.add(new_log)
                
                session.commit()
                message = 'Income account updated successfully'
                result = 1
            else:
                
                stmt_update = update(Income).where(Income.id == income_id).values(merge_data)
                session.execute(stmt_update)
                session.commit()
                message = 'Income account updated successfully'
                result = 1



        except Exception as ex:
            income_id = None
            print('Income Save Exception: ',ex)
            result = 0
            message = 'Income account addition Failed'
            session.rollback()

        finally:            
            session.close()

    return jsonify({
        "income_id": income_id,
        "message": message,
        "result": result
    })

'''
@app.route('/api/edit-income/<int:id>', methods=['POST'])
def edit_income(id: int):

    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']
        admin_id = data['admin_id']
        print('admin id',admin_id)
        income_id = id
        message = ''
        result = 0
        session = db.session
        
        stmt = select(
            Income.id,                              
            Income.gross_income,
            Income.net_income,
            Income.pay_date,
            Income.repeat,  
            Income.commit,
            Income.total_yearly_gross_income,
            Income.total_yearly_net_income,
            Income.total_monthly_gross_income,
            Income.total_monthly_net_income                     
        ).where(Income.id == income_id)

        previous_income = session.execute(stmt).mappings().first()       

        net_income = float(data.get("net_income", 0))
        gross_income = float(data.get("gross_income", 0))
        
        repeat = data['repeat']['value'] if data['repeat']['value'] > 0 else None

        previous_gross_income = float(previous_income['gross_income'])
        previous_net_income = float(previous_income['net_income'])
        previous_repeat = previous_income['repeat']['value'] if previous_income['repeat']['value'] > 0 else None
        #previous_commit = previous_income['commit']
        pay_date = previous_income['pay_date']

        change_found_gross = False if are_floats_equal(previous_gross_income, gross_income) else True
        change_found_net = False if are_floats_equal(previous_net_income, net_income) else True
        change_found_repat = False if previous_repeat == repeat else True

        any_change = change_found_gross or change_found_net or change_found_repat

        print('change_found_gross', change_found_gross)
        print('change_found_net', change_found_net)
        print('change_found_repat', change_found_repat)

        print('any change', any_change)

        income_source_id = new_entry_option_data(data['income_source'], IncomeSourceType, user_id)  # Removed the comma

        append_data = {
            'income_source_id': income_source_id,
            'user_id': user_id,
            'admin_id':admin_id,
            'net_income': net_income,
            'gross_income': gross_income,                                                       
            "updated_at": datetime.now(),                                                                                   
        }

        merge_data = data | append_data

        del merge_data['income_source']
        del merge_data['pay_date']
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                        
        # If no change is found, just update the income record
        try:

            if any_change:
                del merge_data['total_gross_income']
                del merge_data['total_net_income']
                print('merge_data',merge_data)                
                # Get latest commit
                commit = datetime.now()
                total_gross_income =0 
                total_net_income = 0
                total_balance = 0                
                stmt = select(
                    IncomeBoost.id.label('income_boost_id'),
                    IncomeBoost.total_balance,
                    IncomeBoost.income_boost.label('contribution'),
                    IncomeBoost.pay_date_boost.label('start_date'),
                    IncomeBoost.repeat_boost.label('boost_frequency'),
                    IncomeBoost.total_monthly_gross_income,
                    IncomeBoost.total_monthly_net_income,
                    IncomeBoost.total_yearly_gross_income,
                    IncomeBoost.total_yearly_net_income,
                ).where(IncomeBoost.income_id == income_id,                         
                        IncomeBoost.deleted_at == None,
                        IncomeBoost.closed_at == None,
                        IncomeBoost.pay_date_boost <= today

                    )
                                
                results = session.execute(stmt).fetchall()

                app_data = session.query(AppData).filter(AppData.user_id == user_id).first()
          
                income_account_data = None

                income_account_log_data = \
                {                    
                    "income":{
                        "id":income_id,                        
                        "total_gross_income":total_gross_income,
                        "total_net_income":total_net_income,
                        "total_yearly_gross_income":0,
                        "total_yearly_net_income":0,
                        "total_monthly_gross_income":0,
                        "total_monthly_net_income":0,                        
                        "p_total_yearly_gross_income":previous_income['total_yearly_gross_income'],
                        "p_total_yearly_net_income":previous_income['total_yearly_net_income'],
                        "p_total_monthly_gross_income":previous_income['total_monthly_gross_income'],
                        "p_total_monthly_net_income":previous_income['total_monthly_net_income'],
                        "p_gross_income":previous_income['gross_income'],
                        "p_net_income":previous_income['net_income'],
                        "gross_income":gross_income,
                        "net_income":net_income,
                        "pay_date":pay_date,
                        "repeat":repeat,
                        "completed_at":None,
                    },
                    "boost":{},
                    "app_data":{
                        'total_yearly_gross_income':app_data.total_yearly_gross_income,
                        'total_yearly_net_income':app_data.total_yearly_net_income,
                        'total_monthly_gross_income':app_data.total_monthly_gross_income,
                        'total_monthly_net_income':app_data.total_monthly_net_income
                    },
                    "total_gross_income":0,
                    "total_net_income":0,                    
                    "commit":commit,
                    "finished_at":None
                }

                for row in results:
                    #boost_frequency =  row.boost_frequency['value'] if row.boost_frequency['value'] < 1 else  repeat
                    boost_frequency =  row.boost_frequency['value']

                    income_account_log_data["boost"][f"{row.income_boost_id}"]={
                        "id":row.income_boost_id,
                        "total_balance":total_balance,
                        "total_yearly_gross_income":0,
                        "total_yearly_net_income":0,
                        "total_monthly_gross_income":0,
                        "total_monthly_net_income":0,
                        "p_total_yearly_gross_income":row.total_yearly_gross_income,
                        "p_total_yearly_net_income":row.total_yearly_net_income,
                        "p_total_monthly_gross_income":row.total_monthly_gross_income,
                        "p_total_monthly_net_income":row.total_monthly_net_income,
                        "contribution":row.contribution,
                        "start_date":row.start_date,
                        "repeat_boost":boost_frequency,
                        "completed_at":None,
                    }

                #print('income_account_log_data',income_account_log_data)
                   
                income_account_data = income_accounts_log_entry(
                    income_id,
                    user_id,
                    income_account_log_data
                )
                
                if income_account_data!=None:
                    # Create the update statement for Income
                    stmt_update = update(Income)\
                    .where(Income.id == income_id)\
                    .values(
                        calender_at=None,                                     
                        commit=commit,  # Replace with the actual commit value
                        **merge_data  # This unpacks additional fields to update
                    )
                    session.execute(stmt_update)

                    session.commit()
                    message = 'Income account updateded successfully,\nplease reload few mintues later'
                    result = 1
                else:
                    result = 0
                    message = 'Income account update failed'


            else:
                stmt_update = update(Income).where(Income.id == income_id).values(merge_data)
                session.execute(stmt_update)
                session.commit()
                message = 'Income account updateded successfully'
                result = 1
               
            
        except Exception as ex:
            print('Income Update Exception: ', ex)
            result = 0
            message = 'Income account update failed'
            session.rollback()

        finally:
            session.close()

        return jsonify({
            "income_id": income_id,
            "message": message,
            "result": result
        })
'''

