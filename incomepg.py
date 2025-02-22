import re
from flask import Flask,request,jsonify
from incomeutil import generate_new_transaction_data_for_income
from app import app
from bson.json_util import dumps
from util import *
from datetime import datetime
from models import AppData, CalendarData, Income, IncomeMonthlyLog, IncomeYearlyLog, IncomeTransaction, IncomeSourceType
from dbpg import db
from pgutils import *
from sqlalchemy import insert, select, update
#from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, desc, asc


@app.route('/api/delete-incomepg', methods=['POST'])
def delete_income_pg():
    data = request.get_json()
    user_id = data.get('user_id')
    income_id = data.get('id')
    key = data.get('key')
    action = 'Deleted' if key < 2 else 'Closed'
    field = Income.deleted_at if key < 2 else Income.closed_at

    message = None
    error = 0
    deleted_done = 0

    try:
                
        # Update the Income record
        income_update = db.session.query(Income).filter(Income.id == income_id).update(
            {
                field: datetime.now(),
                #Income.calender_at: None
            }, synchronize_session=False
        )        

        # Delete related CalendarData records
        deleted_rows = db.session.query(CalendarData).filter(
            CalendarData.module_id == "income",
            CalendarData.data_id == income_id
        ).delete(synchronize_session=False)


        deleted_monthly_income = db.session.query(IncomeMonthlyLog).filter(            
            IncomeMonthlyLog.income_id == income_id
        ).delete(synchronize_session=False)

        deleted_yearly_income = db.session.query(IncomeYearlyLog).filter(            
            IncomeYearlyLog.income_id == income_id
        ).delete(synchronize_session=False)


        app_update = db.session.query(AppData).filter(AppData.user_id == user_id).update(
            {
                AppData.total_yearly_gross_income:0,
                AppData.total_yearly_net_income:0,
                AppData.total_monthly_gross_income: 0,
                AppData.total_monthly_net_income: 0,
                AppData.income_updated_at:None

            }, synchronize_session=False
        )       

        # Ensure the update was successful before committing
        if income_update and deleted_rows:
            db.session.commit()  # Commit only once
            message = f'Income account {action} Successfully'
            deleted_done = 1
        else:
            db.session.rollback()  # Rollback everything if update fails
            message = f'Income account {action} Failed'
            error = 1


    except Exception as ex:
        db.session.rollback()
        print('Income account Delete Exception:', ex)
        message = f'Income account {action} Failed'
        error = 1

    return jsonify({
        "income_account_id": income_id if deleted_done else None,
        "message": message,
        "error": error,
        "deleted_done": deleted_done
    })

@app.route("/api/income-allpg/<int:id>", methods=['GET'])
def get_income_all_pg(id:int):    
    
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

    income = db.session.execute(stmt).mappings().first()

    if not income:
        return jsonify({"error": "Income record not found"}), 404

    # Convert to dict and format dates
    income_data = {key: income[key] for key in income.keys()}
    
    income_data['pay_date_word'] = income_data['pay_date'].strftime('%d %b, %Y')
    income_data['pay_date'] = convertDateTostring(income_data['pay_date'],"%Y-%m-%d")

    income_data['next_pay_date_word'] = income_data['next_pay_date'].strftime('%d %b, %Y')
    income_data['next_pay_date'] = convertDateTostring(income_data['next_pay_date'],"%Y-%m-%d")


    
    income_data['income_source'] = income_data.pop("income_source_name", None)

    income_data['repeat'] = income_data['repeat']['label']
    
    

    return jsonify({
        "payLoads":{
            "income":income_data
        }
    })


@app.route("/api/incomepg/<int:id>", methods=['GET'])
def view_income_pg(id: int):
    # Fetch income with a join to IncomeSourceType
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

    income = db.session.execute(stmt).mappings().first()

    if not income:
        return jsonify({"error": "Income record not found"}), 404

    # Convert to dict and format dates
    income_data = {key: income[key] for key in income.keys()}
    
    if income_data["pay_date"]:
        income_data["pay_date"] = convertDateTostring(income_data["pay_date"], "%Y-%m-%d")

    # Attach income source with value/label structure
    income_data["income_source"] = {
        "value": income_data.pop("income_source_id"),
        "label": income_data.pop("income_source_name", None)  # Handle cases where it's None
    }

    return jsonify({"income": income_data})



@app.route('/api/incomepg/<int:user_id>', methods=['POST'])
def list_income_pg(user_id: int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])
    action = request.args.get('action', None)

    query = db.session.query(Income).filter(
        Income.user_id == user_id        
    )

    if action:
        query = query.filter(
            Income.deleted_at == None,
            Income.closed_at != None
        )  # No need for or_() with a single condition

    else:
        query = query.filter(
            Income.deleted_at == None,
            Income.closed_at == None
        )  # No need for or_() with a single condition

    # Handle global search filter
    if global_filter:        

        # Ensure the subquery is explicitly wrapped in select()
        income_source_subquery_stmt = select(IncomeSourceType.id).where(
            IncomeSourceType.name.ilike(f"%{global_filter}%")
        )

        try:
            pay_date = datetime.strptime(global_filter, "%Y-%m-%d")
        except ValueError:
            pay_date = None

        query = query.filter(
            or_(
                Income.earner.ilike(f"%{global_filter}%"),
                Income.pay_date == pay_date,
                Income.income_source_id.in_(income_source_subquery_stmt)
            )
        )


    # Handle sorting
    sort_params = []
    for sort in sort_by:
        sort_field = getattr(Income, sort["id"], None)
        if sort_field:
            sort_params.append(sort_field.desc() if sort["desc"] else sort_field.asc())

    if sort_params:
        query = query.order_by(*sort_params)

    # Apply pagination
    total_count = query.count()
    incomes = (
        query.options(joinedload(Income.income_source))
        .offset(page_index * page_size)
        .limit(page_size)
        .all()
    )

    # Fetch app data in a single query
    app_data = db.session.query(AppData).filter(AppData.user_id == user_id).first()

    # Convert results into response format
    income_list = [
        {
            "id": income.id,
            "earner": income.earner,
            "income_source": income.income_source.name if income.income_source else None,
            'gross_income':income.gross_income,
            'net_income':income.net_income,
            'repeat':income.repeat,
            'total_gross_income':income.total_gross_income,
            'total_net_income':income.total_net_income,            
            "pay_date": convertDateTostring(income.pay_date),
            "next_pay_date": convertDateTostring(income.next_pay_date),
            "total_yearly_net_income": income.total_yearly_net_income,
            
        }
        for income in incomes
    ]

    return jsonify({
        'rows': income_list,
        'pageCount': (total_count + page_size - 1) // page_size,
        'totalRows': total_count,
        'extra_payload': {
            'total_net_income': app_data.total_monthly_net_income if app_data else 0,
            'total_gross_income': app_data.total_monthly_gross_income if app_data else 0
        }
    })




@app.route('/api/create-income', methods=['POST'])
def create_income():
    if request.method == 'POST':
        data = request.get_json()

        user_id = data['user_id']

        income_id = None
        message = ''
        result = 0

        # Get a database session from get_db
        session = db.session
        with session.begin():

            try:
                # Begin transaction                
                net_income = float(data.get("net_income", 0))
                gross_income = float(data.get("gross_income", 0))

                repeat = int(data['repeat']['value']) if int(data['repeat']['value']) > 0 else None                
                pay_date = convertStringTodate(data['pay_date'])
                income_source_id = new_entry_option_data(data['income_source'], IncomeSourceType, user_id)  # Removed the comma

                total_gross_income = 0
                total_net_income = 0

                commit = datetime.now()

                del data['income_source']

                append_data = {
                        'income_source_id':income_source_id,                        
                        'user_id':user_id,
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

                income_transaction_data = None
                if len(income_transaction_list) > 0:
                    # Insert transactions into the database
                    if is_single > 0:
                        income_transaction_data = IncomeTransaction(**income_transaction_list[0])
                        session.add(income_transaction_data)
                    else:
                        income_transaction_data = [IncomeTransaction(**txn) for txn in income_transaction_list]
                        session.add_all(income_transaction_data)

                # Update income record with transaction totals
                income_record.total_gross_income = total_gross_income
                income_record.total_net_income = total_net_income
                income_record.next_pay_date = next_pay_date
                income_record.updated_at = datetime.now()

                # Update monthly and yearly logs
                monthly_log = IncomeMonthlyLog(
                    income_id=income_id,
                    user_id=user_id,
                    total_monthly_gross_income=0,
                    total_monthly_net_income=0,
                    updated_at=None
                )

                yearly_log = IncomeYearlyLog(
                    income_id=income_id,
                    user_id=user_id,
                    total_yearly_gross_income=0,
                    total_yearly_net_income=0,
                    updated_at=None
                )
                # Query to check if the user already exists
                app_data = session.query(AppData).filter(AppData.user_id == user_id).first()

                if app_data:
                    # Update the existing record
                    app_data.total_yearly_gross_income = 0
                    app_data.total_yearly_net_income = 0
                    app_data.total_monthly_gross_income = 0
                    app_data.total_monthly_net_income = 0
                    app_data.income_updated_at = None
                    
                    
                else:
                    # Insert a new record if the user doesn't exist
                    app_data = AppData(
                        user_id=user_id,
                        total_yearly_gross_income=0,
                        total_yearly_net_income=0,
                        total_monthly_gross_income=0,
                        total_monthly_net_income=0,
                        income_updated_at=None
                    )
    


                session.add(monthly_log)
                session.add(yearly_log)
                session.add(app_data)
                print('income_id', income_id)

                
                message = 'Income account added successfully'
                session.commit()  # Commit the transaction
                result = 1
                

            except Exception as e:
                income_id = None
                message = 'Income account addition failed'
                session.rollback()  # Rollback on error
                print(f"Error saving income data: {str(e)}")
                result = 0
            finally:
                session.close()            

        return jsonify({
            "income_id": income_id,
            "message": message,
            "result": result
        })
    



@app.route('/api/edit-income/<int:id>', methods=['POST'])
async def edit_income(id: int):
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']
        income_id = id
        message = ''
        result = 0
        
        stmt = select(
            Income.id,                              
            Income.gross_income,
            Income.net_income,
            Income.pay_date,
            Income.repeat,  
            Income.commit                     
        ).where(Income.id == income_id)

        previous_income = db.session.execute(stmt).mappings().first()       

        net_income = float(data.get("net_income", 0))
        gross_income = float(data.get("gross_income", 0))
        
        repeat = data['repeat']['value'] if data['repeat']['value'] > 0 else None

        previous_gross_income = float(previous_income['gross_income'])
        previous_net_income = float(previous_income['net_income'])
        previous_repeat = previous_income['repeat']['value'] if previous_income['repeat']['value'] > 0 else None
        previous_commit = previous_income['commit']
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
            'net_income': net_income,
            'gross_income': gross_income,                                                       
            "updated_at": datetime.now(),                                                                                   
        }

        merge_data = data | append_data

        del merge_data['income_source']
        del merge_data['pay_date']
        

        # If we found any changes on gross_income, net_income or repeat values
        if any_change:        
            # Get a database session from get_db
            session = db.session
            
            try:
                del merge_data['total_gross_income']
                del merge_data['total_net_income']

                # Get latest commit
                commit = datetime.now() 
                # Generate new transaction data and save them
                income_transaction_generate = generate_new_transaction_data_for_income(
                    gross_income,
                    net_income,
                    pay_date,
                    repeat,
                    commit,
                    income_id,
                    user_id
                )                        

                income_transaction_list = income_transaction_generate['income_transaction']
                total_gross_income = income_transaction_generate['total_gross_for_period']
                total_net_income = income_transaction_generate['total_net_for_period']
                next_pay_date = income_transaction_generate['next_pay_date']                        
                is_single = income_transaction_generate['is_single']
            
                income_transaction_data = None
                if len(income_transaction_list) > 0:
                    # Insert transactions into the database
                    if is_single > 0:
                        income_transaction_data = IncomeTransaction(**income_transaction_list[0])
                        session.add(income_transaction_data)
                    else:
                        income_transaction_data = [IncomeTransaction(**txn) for txn in income_transaction_list]
                        session.add_all(income_transaction_data)

                # Create the update statement for Income
                stmt = update(Income).where(Income.id == income_id).values(
                    total_gross_income=total_gross_income,
                    total_net_income=total_net_income,
                    next_pay_date=next_pay_date,                      
                    commit=commit,  # Replace with the actual commit value
                    **merge_data  # This unpacks additional fields to update
                )

                session.execute(stmt)

                # Step 1: Delete Previous Commit Data from IncomeTransaction
                stmt_delete = update(IncomeTransaction).where(
                    IncomeTransaction.income_id == income_id,
                    IncomeTransaction.commit == previous_commit
                ).values(deleted_at=datetime.now())

                session.execute(stmt_delete)

                # Step 2: Upsert IncomeMonthlyLog
                stmt_monthly_log = update(IncomeMonthlyLog).where(
                    IncomeMonthlyLog.income_id == income_id,
                    IncomeMonthlyLog.user_id == user_id
                ).values(
                    income_id=income_id,
                    user_id=user_id,
                    total_monthly_gross_income=0,
                    total_monthly_net_income=0,
                    updated_at=None
                )

                session.execute(stmt_monthly_log)

                # Step 3: Upsert IncomeYearlyLog
                stmt_yearly_log = update(IncomeYearlyLog).where(
                    IncomeMonthlyLog.income_id == income_id,
                    IncomeMonthlyLog.user_id == user_id
                ).values(
                    income_id=income_id,
                    user_id=user_id,
                    total_yearly_gross_income=0,
                    total_yearly_net_income=0,
                    updated_at=None
                )

                session.execute(stmt_yearly_log)


                # Query to check if the user already exists
                app_data = session.query(AppData).filter(AppData.user_id == user_id).first()

                if app_data:
                    # Update the existing record
                    app_data.total_yearly_gross_income = 0
                    app_data.total_yearly_net_income = 0
                    app_data.total_monthly_gross_income = 0
                    app_data.total_monthly_net_income = 0
                    app_data.income_updated_at = None
                    
                    
                else:
                    # Insert a new record if the user doesn't exist
                    app_data = AppData(
                        user_id=user_id,
                        total_yearly_gross_income=0,
                        total_yearly_net_income=0,
                        total_monthly_gross_income=0,
                        total_monthly_net_income=0,
                        income_updated_at=None
                    )
                    
                session.add(app_data)
                # Commit the transaction
                session.commit()
                message = 'Income account updated successfully'                        
                result = 1
            except Exception as ex:
                print('Income Update Exception: ', ex)
                result = 0
                message = 'Income account update failed'
                session.rollback()
            finally:
                session.close()
        else:
            # If no change is found, just update the income record
            try:
                stmt_update = update(Income).where(Income.id == income_id).values(merge_data)
                session = db.session
                session.execute(stmt_update)
                session.commit()
                message = 'Income account updated successfully'
                result = 1
            except Exception as ex:
                print('Income Update Exception: ', ex)
                result = 0
                message = 'Income account update failed'
                session.rollback()

        return jsonify({
            "income_id": income_id,
            "message": message,
            "result": result
        })

