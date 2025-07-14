from flask import request,jsonify, json
from sqlalchemy import func, or_, select, update
from savingutil import calculate_breakdown, calculate_intial_balance
from app import app
import re
from util import *
from datetime import datetime
from models import AppData, Saving,SavingBoost, SavingCategory, SavingContribution, SavingLog
from dbpg import db
from pgutils import new_entry_option_data
from sqlalchemy.orm import joinedload
from db import my_col
saving_accounts_logs = my_col('saving_accounts_logs')
calender_data = my_col('calender_data')

@app.route('/api/delete-savingpg', methods=['POST'])
def delete_saving_pg():
    data = request.get_json()
    user_id = data.get('user_id')
    admin_id = data.get('admin_id')
    saving_id = data.get('id')    
    key = data.get('key')
    action = 'Deleted' if key < 2 else 'Closed'
    field = Saving.deleted_at if key < 2 else Saving.closed_at

    message = None
    error = 0
    deleted_done = 0

    try:
        if key < 2:
            stmt = select(
                Saving.id,                                         
                Saving.total_monthly_balance,
                Saving.current_month                       
            ).where(Saving.id == saving_id)

            previous_saving = db.session.execute(stmt).mappings().first()

            app_data = db.session.query(AppData).filter(AppData.user_id == user_id).first()
            if app_data.current_saving_month == previous_saving['current_month']:
                total_monthly_saving = app_data.total_monthly_saving
                if total_monthly_saving >= previous_saving['total_monthly_balance']:
                   total_monthly_saving -=  previous_saving['total_monthly_balance']
                else:
                    total_monthly_saving = 0

                #app_data.total_monthly_saving = previous_saving['total_monthly_balance'] if app_data.total_monthly_saving >= previous_saving['total_monthly_balance'] else 0       
                app_data.total_monthly_saving = total_monthly_saving
                
                app_data.saving_updated_at = None
                db.session.add(app_data)

                
        # Update the Saving record
        saving_update = db.session.query(Saving).filter(Saving.id == saving_id).update(
            {
                field: datetime.now(),
                Saving.admin_id:admin_id
                #Saving.calender_at: None
            }, synchronize_session=False
        )        


        result = calender_data.delete_one({'module_id': 'saving', 'data.data_id': saving_id} )  

        
        # Ensure the update was successful before committing
        if saving_update:
            db.session.commit()  # Commit only once
            message = f'Saving account {action} Successfully'
            deleted_done = 1
        else:
            db.session.rollback()  # Rollback everything if update fails
            message = f'Saving account {action} Failed'
            error = 1


    except Exception as ex:
        db.session.rollback()
        print('Saving account Delete Exception:', ex)
        message = f'Saving account {action} Failed'
        error = 1

    return jsonify({
        "saving_account_id": saving_id if deleted_done else None,
        "message": message,
        "error": error,
        "deleted_done": deleted_done
    })

@app.route('/api/savingpg/<int:user_id>', methods=['POST'])
def list_saving_pg(user_id: int):
    action = request.args.get('action', None)    
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])

    query = Saving.query.filter_by(user_id=user_id, deleted_at=None, closed_at=None, goal_reached=None)
    
    if action:
        query = Saving.query.filter(
            Saving.user_id == user_id,
            Saving.deleted_at.is_(None),
            or_(Saving.goal_reached.isnot(None), Saving.closed_at.isnot(None))
        )
    
    if global_filter:

        # Ensure the subquery is explicitly wrapped in select()
        saving_category_subquery_stmt = select(SavingCategory.id).where(
            SavingCategory.name.ilike(f"%{global_filter}%")
        )
              
        pattern_str = r'^\d{4}-\d{2}-\d{2}$'
        starting_date = convertStringTodate(global_filter) if re.match(pattern_str, global_filter) else None
        
        query = query.filter(or_(
            Saving.saver.ilike(f"%{global_filter}%"),
            Saving.starting_date == starting_date,
            Saving.category_id.in_(saving_category_subquery_stmt)
        ))
    
    sort_params = [Saving.created_at.desc()]
    for sort in sort_by:
        sort_field = getattr(Saving, sort['id'], None)
        if sort_field:
            sort_params.append(sort_field.desc() if sort['desc'] else sort_field.asc())

    if sort_params:
        query = query.order_by(*sort_params)
    
    total_count = query.count()

    savings = (
        query.options(joinedload(Saving.category))
        .offset(page_index * page_size)
        .limit(page_size)
        .all()
    )
    
    data_list = []    
    
    for saving in savings:
        category_name = saving.category.name if saving.category else None
        saving_boosts = SavingBoost.query.filter_by(saving_id=saving.id, deleted_at=None, closed_at=None).all()
        monthly_saving_boost = sum(boost.saving_boost for boost in saving_boosts) if saving_boosts else 0
        
        data_list.append({
            'id': saving.id,
            'saver': saving.saver,
            'nickname': saving.nickname,
            'goal_amount': saving.goal_amount,
            'interest': saving.interest,
            'interest_type': saving.interest_type,
            'savings_strategy':saving.savings_strategy,
            'starting_amount':saving.starting_amount,
            'contribution':saving.contribution,
            'repeat':saving.repeat,
            'starting_date': convertDateTostring(saving.starting_date),
            'next_contribution_date': convertDateTostring(saving.next_contribution_date),
            'goal_reached': convertDateTostring(saving.goal_reached),
            'monthly_saving_boost': monthly_saving_boost,
            'monthly_saving': round(saving.total_monthly_balance, 2),
            'total_balance_xyz':round(saving.total_balance_xyz,2),
            'category': category_name
        })
    
    total_pages = (total_count + page_size - 1) // page_size

    app_data = db.session.query(AppData).filter(AppData.user_id == user_id).first()
    
    total_data = db.session.query(
        func.sum(Saving.goal_amount).label('total_goal_amount'),
        func.sum(Saving.starting_amount).label('total_starting_amount'),
        func.sum(Saving.contribution).label('total_contribution'),
        #func.sum(Saving.total_monthly_balance).label('total_monthly_balance')
    ).filter(Saving.user_id == user_id, Saving.deleted_at.is_(None)).first()
    
    return jsonify({
        'rows': data_list,
        'pageCount': total_pages,
        'totalRows': total_count,
        'extra_payload': {
            'total_goal_amount': total_data.total_goal_amount or 0,
            'total_starting_amount': total_data.total_starting_amount or 0,
            'total_contribution': total_data.total_contribution or 0,
            'total_monthly_saving': app_data.total_monthly_saving if app_data else 0
        }
    })

@app.route("/api/savingpg/<int:id>", methods=['GET'])
def view_saving_pg(id: int):
    # Fetch saving with a join to SavingSourceType
    stmt = (
        select(
            Saving.id,
            Saving.user_id,
            Saving.nickname,
            Saving.category_id,
            Saving.saver,
            Saving.contribution,
            Saving.goal_amount,
            Saving.increase_contribution_by,
            Saving.starting_date,
            Saving.repeat,
            Saving.note,
            Saving.starting_amount,
            SavingCategory.name.label("category_name"),
            Saving.savings_strategy,
            Saving.interest_type,
            Saving.interest,
        )
        .join(SavingCategory, Saving.category_id == SavingCategory.id, isouter=True)
        .where(Saving.id == id)
    )

    saving = db.session.execute(stmt).mappings().first()

    if not saving:
        return jsonify({"error": "Saving record not found"}), 404

    # Convert to dict and format dates
    saving_data = {key: saving[key] for key in saving.keys()}
    
    if saving_data["starting_date"]:
        saving_data["starting_date"] = convertDateTostring(saving_data["starting_date"], "%Y-%m-%d")

    # Attach saving source with value/label structure
    saving_data["category"] = {
        "value": saving_data.pop("category_id"),
        "label": saving_data.pop("category_name", None)  # Handle cases where it's None
    }

    return jsonify({"saving": saving_data})



@app.route("/api/saving-allpg/<int:id>", methods=['GET'])
def get_saving_all_pg(id:int):
    
    
    stmt = (
        select(
            Saving.id,
            Saving.user_id,
            Saving.category_id,
            Saving.saver,
            Saving.goal_amount,
            Saving.contribution,
            Saving.next_contribution_date,
            Saving.interest_type,
            Saving.savings_strategy,
            Saving.repeat,
            Saving.starting_date,
            Saving.goal_reached,
            Saving.note,
            Saving.total_balance,
            Saving.total_balance_xyz,
            Saving.nickname,
            Saving.interest,
            Saving.starting_amount,
            Saving.increase_contribution_by,
            Saving.progress,
            SavingCategory.name.label("saving_category_name"),
        )
        .join(SavingCategory, Saving.category_id == SavingCategory.id, isouter=True)
        .where(Saving.id == id)
    )

    saving_data = db.session.execute(stmt).mappings().first()
    
    saving = {

    }
    
    saving['starting_date_word'] = convertDateTostring(saving_data['starting_date'])
    saving['starting_date'] = convertDateTostring(saving_data['starting_date'],"%Y-%m-%d")

    saving['next_contribution_date_word'] = convertDateTostring(saving_data['next_contribution_date'])
    saving['next_contribution_date'] = convertDateTostring(saving_data['next_contribution_date'],"%Y-%m-%d")


    saving['goal_reached_word'] = convertDateTostring(saving_data['goal_reached'])
    saving['goal_reached'] = convertDateTostring(saving_data['goal_reached'],"%Y-%m-%d")
      
    saving['user_id'] = saving_data['user_id']


    saving['category'] = saving_data['saving_category_name']

    saving['repeat'] = saving_data['repeat']['label']

    saving['interest_type'] = saving_data['interest_type']['label']
    saving['savings_strategy'] = saving_data['savings_strategy']['label']
    
    saving['goal_amount'] = saving_data['goal_amount']
    saving['contribution'] = saving_data['contribution']
    saving['total_balance'] = saving_data['total_balance']
    saving['total_balance_xyz'] = saving_data['total_balance_xyz']
    saving['saver'] = saving_data['saver']
    saving['nickname'] = saving_data['nickname']
    saving['interest'] = saving_data['interest']
    saving['note'] = saving_data['note']
    saving['starting_amount'] = saving_data['starting_amount']
    saving['increase_contribution_by'] = saving_data['increase_contribution_by']
    saving['progress'] = saving_data['progress']

    return jsonify({
        "payLoads":{
            "saving":saving
        }
    })


def saving_accounts_log_entry(
                            saving_id,          
                            user_id,
                            saving_account_log_data
                              ):
    saving_account_data = None    

    saving_acc_query = {
                "saving_id": saving_id,                
                "user_id":user_id,
                
    }

    print('saving_account_log_data',saving_account_log_data)
    newvalues = { "$set":  saving_account_log_data }
    saving_account_data = saving_accounts_logs.update_one(saving_acc_query,newvalues,upsert=True)
    return saving_account_data

@app.route('/api/edit-saving-accountpg/<int:id>', methods=['POST'])
async def edit_saving_pg(id:int):
    if request.method == 'POST':
        data = json.loads(request.data)
        user_id = data['user_id']
        admin_id = data['admin_id']        
        message = ''
        result = 0
        saving_id = id

        session = db.session

        stmt = select(
            Saving.id,
            Saving.saver,
            Saving.category,
            Saving.category_id,
            Saving.interest,
            Saving.interest_type,
            Saving.savings_strategy,
            Saving.contribution,
            Saving.increase_contribution_by,                                    
            Saving.starting_amount,
            Saving.starting_date,
            Saving.goal_amount,
            Saving.total_balance,
            Saving.total_balance_xyz,
            Saving.total_monthly_balance,
            Saving.repeat,  
            Saving.commit                     
        ).where(Saving.id == saving_id)

        goal_amount = round(float(data.get("goal_amount", 0)),2)
        interest = round(float(data.get("interest", 0)),2)
        interest_type = data['interest_type']['value']
        starting_amount = round(float(data.get("starting_amount", 0)),2)
        contribution = round(float(data.get("contribution", 0)),2)
        i_contribution = round(float(data.get("increase_contribution_by", 0)),2)
        repeat = data['repeat']['value'] if data['repeat']['value'] > 0 else None
        financial_freedom_target = round(float(data.get("financial_freedom_target", 0)),2)

        previous_saving = session.execute(stmt).mappings().first()

        previous_commit = previous_saving['commit']
        previous_category_id = previous_saving['category_id']
        
        
        category_id = data['category']['value']
        if category_id == previous_category_id:
            category_id = previous_category_id
        else:    
            category_id = new_entry_option_data(data['category'], SavingCategory, user_id)


        previous_starting_amount = float(previous_saving['starting_amount'])
        previous_goal_amount = float(previous_saving['goal_amount'])
        previous_repeat = previous_saving['repeat']['value'] if previous_saving['repeat']['value'] > 0 else None
        previous_interest = float(previous_saving['interest'])
        previous_contribution = float(previous_saving['contribution'])
        previous_i_contribution = float(previous_saving['increase_contribution_by'])
        previous_interest_type =  previous_saving['interest_type']['value']

        

        change_found_goal_amount = False if are_floats_equal(previous_goal_amount, goal_amount) else True
        change_found_interest = False if are_floats_equal(previous_interest, interest) else True
        change_found_starting_amount = False if are_floats_equal(previous_starting_amount, starting_amount) else True
        change_found_previous_contribution = False if are_floats_equal(previous_contribution, contribution) else True
        change_found_previous_i_contribution = False if are_floats_equal(previous_i_contribution, i_contribution) else True
        change_found_repeat = False if previous_repeat == repeat else True
        change_found_interest_type= False if previous_interest_type == interest_type else True


        any_change = change_found_goal_amount or change_found_interest or \
        change_found_starting_amount or \
        change_found_previous_contribution or \
        change_found_repeat or \
        change_found_previous_i_contribution or \
        change_found_interest_type

        append_data = {
            'category_id': category_id,
            'user_id': user_id,
            'admin_id':admin_id,
            'goal_amount': goal_amount,
            'starting_amount': starting_amount,
            'contribution':contribution,
            'increase_contribution_by':i_contribution,
            'interest':interest,                                                       
            "updated_at": datetime.now(),
            "financial_freedom_target":financial_freedom_target                                                                                   
        }

        merge_data = data | append_data

        del merge_data['category']
        del merge_data['starting_date']
        del merge_data['savings_strategy']

        try:

            if any_change:

                commit = datetime.now()

                stmt_update = update(Saving).where(Saving.id == saving_id).values(                                            
                        calender_at=None,
                        commit=commit,  # Replace with the actual commit value
                        **merge_data  # This unpacks additional fields to update
                    )
                session.execute(stmt_update)

                existing_log = db.session.query(SavingLog).filter_by(
                    saving_id=saving_id,
                    commit=previous_commit
                ).first()

                if not existing_log:
                    previous_saving_row = dict(previous_saving)
                    previous_saving_row['starting_date'] = convertDateTostring(previous_saving['starting_date'],"%Y-%m-%d %H:%M:%S.%f")
                    previous_saving_row['commit'] = convertDateTostring(previous_commit,"%Y-%m-%d %H:%M:%S.%f")
                    print('previous_saving_row',previous_saving_row)
                    new_log = SavingLog(
                        saving_id=saving_id,
                        user_id=user_id,           # supply actual user_id
                        admin_id=admin_id,       # or actual admin_id if available
                        commit=previous_commit,
                        data=previous_saving_row  # or actual data dict
                    )

                    session.add(new_log)
                
                session.commit()
                message = 'Saving account updated successfully'
                result = 1
            else:
                
                stmt_update = update(Saving).where(Saving.id == saving_id).values(merge_data)
                session.execute(stmt_update)
                session.commit()
                message = 'Saving account updated successfully'
                result = 1



        except Exception as ex:
            saving_id = None
            print('Saving Save Exception: ',ex)
            result = 0
            message = 'Saving account addition Failed'
            session.rollback()

        finally:            
            session.close()


        return jsonify({
            "saving_id": saving_id,
            "message": message,
            "result": result
        })


'''
@app.route('/api/edit-saving-accountpg/<int:id>', methods=['POST'])
async def edit_saving_pg(id:int):
    if request.method == 'POST':
        data = json.loads(request.data)
        user_id = data['user_id']
        saving_id = id
        message = ''
        result = 0

        session = db.session

        stmt = select(
            Saving.id,
            Saving.interest,
            Saving.contribution,
            Saving.increase_contribution_by,                                    
            Saving.starting_amount,
            Saving.starting_date,
            Saving.goal_amount,
            Saving.total_balance,
            Saving.total_balance_xyz,
            Saving.total_monthly_balance,
            Saving.repeat,  
            Saving.commit                     
        ).where(Saving.id == id)

        

        
        goal_amount = round(float(data.get("goal_amount", 0)),2)
        interest = round(float(data.get("interest", 0)),2)
        starting_amount = round(float(data.get("starting_amount", 0)),2)
        contribution = round(float(data.get("contribution", 0)),2)
        i_contribution = round(float(data.get("increase_contribution_by", 0)),2)
        repeat = data['repeat']['value'] if data['repeat']['value'] > 0 else None
        financial_freedom_target = round(float(data.get("financial_freedom_target", 0)),2)


        previous_saving = session.execute(stmt).mappings().first()                              


        previous_starting_amount = float(previous_saving['starting_amount'])
        previous_goal_amount = float(previous_saving['goal_amount'])
        previous_repeat = previous_saving['repeat']['value'] if previous_saving['repeat']['value'] > 0 else None
        previous_interest = float(previous_saving['interest'])
        previous_contribution = float(previous_saving['contribution'])
        previous_i_contribution = float(previous_saving['increase_contribution_by'])
        starting_date = previous_saving['starting_date']

        change_found_goal_amount = False if are_floats_equal(previous_goal_amount, goal_amount) else True
        change_found_interest = False if are_floats_equal(previous_interest, interest) else True
        change_found_starting_amount = False if are_floats_equal(previous_starting_amount, starting_amount) else True
        change_found_previous_contribution = False if are_floats_equal(previous_contribution, contribution) else True
        change_found_previous_i_contribution = False if are_floats_equal(previous_i_contribution, i_contribution) else True
        change_found_repeat = False if previous_repeat == repeat else True


        any_change = change_found_goal_amount or change_found_interest or \
        change_found_starting_amount or \
        change_found_previous_contribution or \
        change_found_repeat or \
        change_found_previous_i_contribution

        category_id = new_entry_option_data(data['category'], SavingCategory, user_id)

        append_data = {
            'category_id': category_id,
            'user_id': user_id,
            'goal_amount': goal_amount,
            'starting_amount': starting_amount,
            'contribution':contribution,
            'increase_contribution_by':i_contribution,
            'interest':interest,                                                       
            "updated_at": datetime.now(),
            "financial_freedom_target":financial_freedom_target                                                                                   
        }

        merge_data = data | append_data

        del merge_data['category']
        del merge_data['starting_date']        

                    
        
        
        

        try:

            #print('merge_data',merge_data)

            
            if any_change:
                                
                commit = datetime.now()
                total_balance = 0
                total_balance_xyz = 0
                total_monthly_balance = 0
                progress = 0
                period = 0

                stmt = select(
                    SavingBoost.id.label('saving_boost_id'),
                    SavingBoost.total_balance,
                    SavingBoost.saving_boost.label('contribution'),
                    SavingBoost.pay_date_boost.label('start_date'),
                    SavingBoost.repeat_boost.label('boost_frequency'),
                    SavingBoost.boost_operation_type.label('op_type'),
                ).where(SavingBoost.saving_id == saving_id,                         
                        SavingBoost.deleted_at == None,
                        SavingBoost.closed_at == None

                    )
                
                results = session.execute(stmt).fetchall()
                #print('results',results)
                app_data = session.query(AppData).filter(AppData.user_id == user_id).first()

                saving_account_data = None

                saving_account_log_data = \
                {                    
                    "saving":{
                        "id":saving_id,
                        "total_balance":total_balance,
                        "total_balance_xyz":total_balance_xyz,
                        "total_monthly_balance":total_monthly_balance,
                        "p_total_balance":previous_saving['total_balance'],
                        "p_total_balance_xyz":previous_saving['total_balance_xyz'],
                        "p_total_monthly_balance":previous_saving['total_monthly_balance'],
                        'p_goal_amount':previous_saving['goal_amount'],
                        'p_starting_amount':previous_saving['starting_amount'], 
                        'p_contribution':previous_saving['contribution'],
                        'p_increase_contribution_by':previous_saving['increase_contribution_by'],
                        'p_interest':previous_saving['interest'],
                        'goal_amount':goal_amount,
                        'starting_amount':starting_amount, 
                        'contribution':contribution,
                        'increase_contribution_by':i_contribution,
                        'interest':interest,                     
                        "total_balance":total_balance,
                        "total_balance_xyz":total_balance_xyz,                        
                        "progress":0,
                        "period":0,
                        "starting_date":starting_date,
                        "repeat":repeat,
                        "completed_at":None,
                    },
                    "boost":{},
                    "app_data":{
                        'total_monthly_saving':app_data.total_monthly_saving,                        
                    },
                    "total_balance":0,
                    "total_balance_xyz":0,
                    "commit":commit,
                    "finished_at":None
                }

                if len(results) > 0:

                    for row in results:

                        #boost_frequency =  row.boost_frequency['value'] if row.boost_frequency['value'] < 1 else  repeat
                        boost_frequency =  row.boost_frequency['value']

                        saving_account_log_data["boost"][f"{row.saving_boost_id}"]={
                            "id":row.saving_boost_id,
                            "total_balance":total_balance,
                            "total_monthly_balance":0,
                            "p_total_monthly_balance":row.total_monthly_balance,
                            "contribution":row.contribution,
                            "start_date":row.start_date,
                            "repeat_boost":boost_frequency,
                            "op_type":row.op_type,
                            "completed_at":None,
                        }

                print('saving_account_log_data',saving_account_log_data)

                   
                saving_account_data = saving_accounts_log_entry(
                        saving_id,
                        user_id,
                        saving_account_log_data
                    )
                    

                if saving_account_data!=None:
                    # Create the update statement for Saving
                    stmt_update = update(Saving).where(Saving.id == saving_id).values(
                        total_balance=total_balance,
                        total_balance_xyz=total_balance_xyz,
                        total_monthly_balance = total_monthly_balance,
                        progress = progress,
                        period = period,
                        next_contribution_date=None,
                        goal_reached=None,
                        calender_at=None,
                        commit=commit,  # Replace with the actual commit value
                        **merge_data  # This unpacks additional fields to update
                    )
                    session.execute(stmt_update)
                    session.commit()
                    message = 'Saving account updated successfully'
                    result = 1
                else:
                    result = 0
                    message = 'Saving account update failed'

            else:
                stmt_update = update(Saving).where(Saving.id == saving_id).values(merge_data)
                session.execute(stmt_update)
                session.commit()
                message = 'Saving account updated successfully'
                result = 1



        except Exception as ex:
            saving_id = None
            print('Saving Save Exception: ',ex)
            result = 0
            message = 'Saving account addition Failed'
            session.rollback()

        finally:
            print('here comes')
            session.close()


        return jsonify({
            "saving_id": saving_id,
            "message": message,
            "result": result
        })

'''       

@app.route('/api/save-saving-accountpg', methods=['POST'])
async def save_saving_pg():
    if request.method == 'POST':
        data = json.loads(request.data)
        user_id = data['user_id']
        admin_id = data['admin_id'] 
        saving_id = None
        message = ''
        result = 0
        starting_date = convertStringTodate(data['starting_date'])
        goal_amount = round(float(data.get("goal_amount", 0)),2)
        interest = round(float(data.get("interest", 0)),2)
        starting_amount = round(float(data.get("starting_amount", 0)),2)
        contribution = round(float(data.get("contribution", 0)),2)
        i_contribution = round(float(data.get("increase_contribution_by", 0)),2)
        repeat = data['repeat']['value'] if data['repeat']['value'] > 0 else None        
        financial_freedom_target = round(float(data.get("financial_freedom_target", 0)),2)
        interest_type = data['interest_type']['value']
        savings_strategy= data['savings_strategy']['value']
        commit = datetime.now()            
        goal_reached = None 
        period = 0
        current_saving_month = int(convertDateTostring(datetime.now(),'%Y%m'))                   
        total_monthly_balance = 0
        starting_breakdown = None


        if starting_amount > 0:
            get_initial = calculate_intial_balance(
                starting_amount,
                interest,
                starting_date,
                period,
                interest_type
            )
            starting_amount = get_initial['total_balance_xyz']
            total_monthly_balance = get_initial['total_monthly_balance_xyz']
            starting_breakdown = get_initial['breakdown']




        contribution_breakdown = calculate_breakdown(
            starting_amount,
            contribution,
            interest, 
            goal_amount, 
            starting_date,
            repeat,
            i_contribution,
            period,
            interest_type,
            savings_strategy,
            1,
            0,
            total_monthly_balance
            )
        breakdown = contribution_breakdown['breakdown']
        total_balance = contribution_breakdown['total_balance']
        total_balance_xyz = contribution_breakdown['total_balance_xyz']
        progress  = contribution_breakdown['progress']
        next_contribution_date = contribution_breakdown['next_contribution_date']
        goal_reached = contribution_breakdown['goal_reached']
        period = contribution_breakdown['period']
        is_single = contribution_breakdown['is_single']
        total_monthly_balance_xyz = contribution_breakdown['total_monthly_balance_xyz']

        len_breakdown = len(breakdown)

        if next_contribution_date == None:
            goal_reached = goal_reached if len_breakdown > 0 else None

       

        if len_breakdown < 1:

            saving_data = Saving(
                    savings_strategy= data['savings_strategy'],
                    saver= data['saver'],
                    nickname= data['nickname'],
                    interest_type = data['interest_type'],
                    repeat = data['repeat'],
                    note = data['note'] if 'note' in data and data['note']!='' else None,

                    category_id=new_entry_option_data(data['category'], SavingCategory, user_id),
                    user_id=user_id,
                    admin_id=admin_id,
                    goal_amount=goal_amount,
                    interest=interest,
                    starting_amount=starting_amount,
                    contribution=contribution,
                    increase_contribution_by=i_contribution,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    deleted_at=None,
                    closed_at=None,
                    goal_reached=goal_reached,
                    starting_date=starting_date,
                    next_contribution_date=next_contribution_date,
                    total_balance=total_balance,
                    total_balance_xyz=total_balance_xyz,
                    progress=progress,
                    period=period,
                    commit=commit,
                    total_monthly_balance = total_monthly_balance_xyz,
                    calender_at=None,
                    financial_freedom_target=financial_freedom_target,
                    current_month = current_saving_month
                )
            db.session.add(saving_data)
            db.session.commit()
            saving_id = saving_data.id
            result = 1 if saving_id!=None else 0

            if result:
                message = 'Saving account added Succefull'
              
            else:
                message = 'Saving account addition Failed'
                

        else:
            
                       
            try:
                
                saving_data = Saving(
                    savings_strategy= data['savings_strategy'],
                    saver= data['saver'],
                    nickname= data['nickname'],
                    interest_type = data['interest_type'],
                    repeat = data['repeat'],
                    note = data['note'] if 'note' in data and data['note']!='' else None,

                    category_id=new_entry_option_data(data['category'], SavingCategory, user_id),
                    user_id=user_id,
                    admin_id=admin_id,
                    goal_amount=goal_amount,
                    interest=interest,
                    starting_amount=starting_amount,
                    contribution=contribution,
                    increase_contribution_by=i_contribution,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    deleted_at=None,
                    closed_at=None,
                    goal_reached=goal_reached,
                    starting_date=starting_date,
                    next_contribution_date=next_contribution_date,
                    total_balance=total_balance,
                    total_balance_xyz=total_balance_xyz,
                    progress=progress,
                    period=period,
                    commit=commit,
                    calender_at=None,
                    total_monthly_balance=total_monthly_balance_xyz,
                    financial_freedom_target=financial_freedom_target,
                    current_month = current_saving_month
                )

                db.session.add(saving_data)
                db.session.flush()
                saving_id = saving_data.id

                contribution_data = None                
                
                if is_single > 0:
                    if starting_breakdown == None:
                        contribution_data = SavingContribution(
                                saving_id=saving_id,                            
                                commit=commit,
                                user_id=user_id,
                                **breakdown
                            )
                        db.session.add(contribution_data)
                    else:
                        contribution_data = [
                            SavingContribution(
                                saving_id=saving_id,                            
                                commit=commit,
                                user_id=user_id,
                                **starting_breakdown
                            ),
                            SavingContribution(
                                saving_id=saving_id,                            
                                commit=commit,
                                user_id=user_id,
                                **breakdown
                            )
                        ]
                        db.session.bulk_save_objects(contribution_data)
                else:
                    if starting_breakdown == None:
                        contribution_data = [
                            SavingContribution(
                                saving_id=saving_id,                                
                                commit=commit,
                                user_id=user_id,
                                **todo
                            ) for todo in breakdown
                        ]
                    else:
                        contribution_data = [
                            SavingContribution(
                                saving_id=saving_id,                            
                                commit=commit,
                                user_id=user_id,
                                **starting_breakdown
                            ),
                            *[
                            SavingContribution(
                                saving_id=saving_id,                                
                                commit=commit,
                                user_id=user_id,
                                **todo
                            ) for todo in breakdown
                            ]
                        ]
                    db.session.bulk_save_objects(contribution_data)                                
                

                

                # Query to check if the user already exists
                app_data = db.session.query(AppData).filter(AppData.user_id == user_id).first()

                if app_data:
                    # Update the existing record                    
                    if app_data.current_saving_month!= None and app_data.current_saving_month == current_saving_month:
                        app_data.total_monthly_saving += total_monthly_balance_xyz
                    else:
                        app_data.total_monthly_saving =  total_monthly_balance_xyz
                        app_data.current_saving_month = current_saving_month                   
                    app_data.saving_updated_at = None
                    
                    
                else:
                    # Insert a new record if the user doesn't exist
                    app_data = AppData(
                        user_id=user_id,
                        current_saving_month = current_saving_month,
                        total_monthly_saving=total_monthly_balance_xyz,                        
                        saving_updated_at=None
                    )

                
                db.session.add(app_data)
                db.session.commit()
                message = 'Saving account added Succefull'
                result = 1

            except Exception as ex:
                saving_id = None
                print('Saving Save Exception: ',ex)
                result = 0
                message = 'Saving account addition Failed'
                db.session.rollback()

        return jsonify({
            "saving_id":saving_id,
            "message":message,
            "result":result
        })