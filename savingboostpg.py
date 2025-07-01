import os
from flask import request,jsonify, json
from sqlalchemy import func, or_, select
#from flask_cors import CORS, cross_origin
from savingutil import calculate_breakdown, calculate_breakdown_ontime, get_next_contribution_date
from pgutils import new_entry_option_data
from app import app
import re
from util import *
from datetime import datetime

from models import AppData, Saving, SavingBoost, SavingBoostType, SavingContribution
from dbpg import db


@app.route('/api/delete-saving-boostpg', methods=['POST'])
def delete_saving_boost_pg():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']             
        key = data['key']
        action = 'Deleted' if key < 2 else 'Closed'
        field = SavingBoost.deleted_at if key < 2 else SavingBoost.closed_at
        saving_boost_id = id
        
        message = None
        error = 0
        deleted_done = 0

        try:
            with db.session.begin():
                if key < 2:
                    stmt = select(
                        SavingBoost.id,                                         
                        SavingBoost.total_monthly_balance,
                        SavingBoost.user_id                       
                    ).where(SavingBoost.id == saving_boost_id)

                    previous_saving = db.session.execute(stmt).mappings().first()
                    user_id =previous_saving['user_id']

                    app_data = db.session.query(AppData).filter(AppData.user_id == user_id).first()

                    app_data.total_monthly_saving -= previous_saving['total_monthly_balance'] if app_data.total_monthly_saving >= previous_saving['total_monthly_balance'] else 0       
                    app_data.saving_updated_at = None
                    db.session.add(app_data)
                # Update the SavingBoost record
                saving_boost_update = db.session.query(SavingBoost).filter(SavingBoost.id == saving_boost_id).update(
                    {field: datetime.now()}, synchronize_session=False
                )

                '''
                saving_contribution_update = db.session.query(SavingContribution).filter(SavingContribution.id == saving_boost_id).update(
                    {field: datetime.now()}, synchronize_session=False
                )
                '''

                if saving_boost_update:
                    message = f'SavingBoost boost {action} Successfully'
                    deleted_done = 1
                    db.session.commit()
                else:
                    message = f'SavingBoost boost {action} Failed'
                    db.session.rollback()
                    error = 1

        except Exception as ex:
            db.session.rollback()
            print('SavingBoost boost Delete Exception:', ex)
            message = f'SavingBoost boost {action} Failed'
            error = 1

        
        return jsonify({
            "saving_account_id":saving_boost_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })



@app.route('/api/saving-boostpg/<int:saving_id>', methods=['POST'])
def list_saving_boost_pg(saving_id:int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])

    query = db.session.query(
    SavingBoost.id,
    SavingBoost.saver,
    SavingBoost.pay_date_boost,
    SavingBoost.next_contribution_date,
    SavingBoost.saving_boost,    
    SavingBoost.repeat_boost,
    SavingBoost.total_balance,
    SavingBoost.boost_operation_type,
    Saving.saver.label('saving_ac'),
    SavingBoostType.name.label("saving_boost_source")
    ).filter(
        SavingBoost.saving_id == saving_id,
        SavingBoost.deleted_at.is_(None),
        SavingBoost.closed_at.is_(None)
    )\
    .join(Saving, SavingBoost.saving_id == Saving.id, isouter=True)\
    .join(SavingBoostType, SavingBoost.saving_boost_source_id == SavingBoostType.id, isouter=True)


    
    if global_filter:        

        pattern_str = r'^\d{4}-\d{2}-\d{2}$'
        pay_date_boost = None        
        
        if re.match(pattern_str, global_filter):
            pay_date_boost = datetime.strptime(global_filter,"%Y-%m-%d")                    
                    

        query = query.filter(or_(
            SavingBoost.saver.ilike(f"%{global_filter}%"),
            SavingBoost.pay_date_boost == pay_date_boost,
            SavingBoostType.name.ilike(f"%{global_filter}%")
        ))

    # Sorting
    sort_params = [SavingBoost.created_at.desc()]  # Default sorting
    for sort in sort_by:
        sort_field = getattr(SavingBoost, sort['id'], None)
        if sort_field:
            sort_params.append(sort_field.desc() if sort['desc'] else sort_field.asc())

    query = query.order_by(*sort_params)

    total_count = query.count()
    total_pages = (total_count + page_size - 1) // page_size
    results = query.offset(page_index * page_size).limit(page_size).all()

    # Formatting results
    data_list = []
    for entry in results:
        data_list.append({
            'id': entry.id,
            'saver': entry.saver,
            'saving_boost_source':entry.saving_boost_source if entry.saving_boost_source else None,
            'pay_date_boost': convertDateTostring(entry.pay_date_boost),
            'next_contribution_date': convertDateTostring(entry.next_contribution_date),            
            'saving_boost': entry.saving_boost,
            'repeat_boost':entry.repeat_boost,
            'total_balance':entry.total_balance,
            'saving':entry.saving_ac,
            'boost_operation_type':entry.boost_operation_type,
            'op_type_value':entry.boost_operation_type['value']
        })

    

    # Aggregate total saving boost
    total_saving_boost = db.session.query(func.sum(SavingBoost.saving_boost)).filter(
        SavingBoost.saving_id == saving_id,
        SavingBoost.deleted_at.is_(None)
    ).scalar() or 0   
        
    return jsonify({
        'rows': data_list,
        'pageCount': total_pages,
        'totalRows': total_count,
        'extra_payload':{
            'total_saving_boost':total_saving_boost,                                  
        }
    })








@app.route('/api/save-saving-boostpg', methods=['POST'])
async def save_saving_boost_pg():
    if request.method == 'POST':
        data = json.loads(request.data)
        user_id = data['user_id']
        saving_id = data['saving']['value']
        saving_boost_id = None
        message = ''
        result = 0
        total_balance = \
        total_balance_xyz = \
        total_monthly_balance =\
        total_monthly_balance_boost= 0.0

        # Retrieve the Saving record using SQLAlchemy query
        saving_entry = db.session.query(
            Saving.total_balance,
            Saving.total_balance_xyz,
            Saving.total_monthly_balance,            
            Saving.commit, 
            Saving.user_id,
            Saving.goal_amount,
            Saving.interest,
            Saving.interest_type,
            Saving.savings_strategy
        ).filter_by(
            id=saving_id           
        ).first()

        total_balance,total_balance_xyz, total_monthly_balance, commit, user_id,\
        goal_amount, interest, interest_type, savings_strategy = saving_entry


        starting_amount = total_balance_xyz
        contribution = round(float(data.get("saving_boost", 0)),2)
        i_contribution = 0
        repeat = data['repeat_boost']['value']
        goal_reached = None 
        period = 0
        op_type = data['boost_operation_type']['value']        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        pay_date_boost = convertStringTodate(data['pay_date_boost'])
        interest_type = interest_type['value']
        savings_strategy = savings_strategy['value']            
        
        merge_data = {    
            'saving_id': saving_id,            
            'saving_boost_source_id': new_entry_option_data(data['saving_boost_source'], SavingBoostType, user_id),                
            'user_id': user_id,
            'saver':data['saver'],
            'repeat_boost':data['repeat_boost'], 
            'boost_operation_type':data['boost_operation_type'],   
            'saving_boost': contribution,         
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "deleted_at": None,
            "closed_at": None,  
            'pay_date_boost': pay_date_boost,                
            'next_contribution_date':None,
            'total_balance': 0,
            'note':data['note'] if 'note' in data and data['note']!='' else None,
            'total_balance':0                                   
        }

        session = db.session
        if pay_date_boost <= today:
            
            saving_boost_entry = SavingBoost(**merge_data)
            session.add(saving_boost_entry)
                       

            if repeat > 0:

                contribution_breakdown = calculate_breakdown(
                    starting_amount,
                    contribution,
                    interest, 
                    goal_amount, 
                    pay_date_boost,
                    repeat,
                    i_contribution,
                    period,
                    interest_type,
                    savings_strategy,
                    op_type                    
                    )
                breakdown = contribution_breakdown['breakdown']
                total_balance = contribution_breakdown['total_balance']
                total_balance_xyz= contribution_breakdown['total_balance_xyz']
                total_balance_boost = contribution_breakdown['total_balance_boost']
                progress  = contribution_breakdown['progress']
                next_contribution_date_b = contribution_breakdown['next_contribution_date']
                goal_reached = contribution_breakdown['goal_reached']
                period = contribution_breakdown['period']
                is_single = contribution_breakdown['is_single']                
                total_monthly_balance_boost = contribution_breakdown['total_monthly_balance_boost']

                len_breakdown = len(breakdown)

                if next_contribution_date_b == None:
                    goal_reached = goal_reached if len_breakdown > 0 else None

                if len_breakdown < 1:
                    session.commit()
                    saving_boost_id = saving_boost_entry.id                    
                    message = 'Saving boost added Succefull'

                else:

                    
                    session.flush()
                    saving_boost_id = saving_boost_entry.id 

                    boost_status = {
                        'id': saving_boost_id,
                        'next_contribution_date': next_contribution_date_b,
                        'total_balance': total_balance_boost,
                        'total_monthly_balance':total_monthly_balance_boost,                    
                        'closed_at': goal_reached
                    }
                    total_monthly_balance = total_monthly_balance + total_monthly_balance_boost

                    update_data = {
                        "total_balance": total_balance,            
                        'total_balance_xyz': total_balance_xyz, 
                        'total_monthly_balance' :total_monthly_balance,                    
                        'progress':progress,
                        'updated_at': datetime.now()              
                    }

                    try:

                        
                        contribution_data = None                
            
                        if is_single > 0:
                            contribution_data = SavingContribution(
                                    saving_id=saving_id,
                                    saving_boost_id=saving_boost_id,                            
                                    commit=commit,
                                    user_id=user_id,
                                    **breakdown
                                )
                            session.add(contribution_data)
                        else:
                            contribution_data = [
                                    SavingContribution(
                                        saving_id=saving_id,
                                        saving_boost_id=saving_boost_id,                                
                                        commit=commit,
                                        user_id=user_id,
                                        **todo
                                    ) for todo in breakdown
                                ]
                            session.bulk_save_objects(contribution_data)

                        session.query(SavingBoost).filter_by(id=boost_status['id']).update({
                            'next_contribution_date': boost_status['next_contribution_date'],
                            'total_balance': boost_status['total_balance'],
                            'total_monthly_balance': boost_status['total_monthly_balance'],                            
                            'closed_at': boost_status['closed_at']
                        })

                        session.query(Saving).filter_by(id=saving_id).update(update_data)
                        
                        app_data = db.session.query(AppData).filter(AppData.user_id == user_id).first()

                                          
                        app_data.total_monthly_saving += total_monthly_balance_boost                    
                        app_data.saving_updated_at = None
                            
                            
                        

                        session.add(app_data)
                        session.commit()
                        message = 'Saving boost added Succefull'
                        result = 1

                    except Exception as ex:

                        saving_boost_id = None
                        print('Saving Save Exception: ',ex)
                        result = 0
                        message = 'Saving boost addition Failed'
                        session.rollback()

            else:

                contribution_breakdown = calculate_breakdown_ontime(
                    starting_amount,
                    contribution,
                    interest, 
                    goal_amount, 
                    pay_date_boost,                    
                    period,
                    interest_type,
                    savings_strategy,
                    op_type                    
                    )
                breakdown = contribution_breakdown['breakdown']
                total_balance = contribution_breakdown['total_balance']
                total_balance_xyz= contribution_breakdown['total_balance_xyz']
                total_balance_boost = contribution_breakdown['total_balance_boost']
                progress  = contribution_breakdown['progress']
                next_contribution_date_b = contribution_breakdown['next_contribution_date']
                goal_reached = contribution_breakdown['goal_reached']
                period = contribution_breakdown['period']
                is_single = contribution_breakdown['is_single']
                total_monthly_balance_boost = contribution_breakdown['total_monthly_balance_boost']

                len_breakdown = len(breakdown)

                if next_contribution_date_b == None:
                    goal_reached = goal_reached if len_breakdown > 0 else None

                if len_breakdown < 1:
                    session.commit()
                    saving_boost_id = saving_boost_entry.id                    
                    message = 'Saving boost added Succefull'

                else:

                    
                    session.flush()
                    saving_boost_id = saving_boost_entry.id 

                    boost_status = {
                        'id': saving_boost_id,
                        'next_contribution_date': next_contribution_date_b,
                        'total_balance': total_balance_boost,
                        'total_monthly_balance':total_monthly_balance_boost,                    
                        'closed_at': goal_reached
                    }
                    total_monthly_balance = total_monthly_balance + total_monthly_balance_boost

                    update_data = {
                        "total_balance": total_balance,            
                        'total_balance_xyz': total_balance_xyz, 
                        'total_monthly_balance' :total_monthly_balance,                    
                        'progress':progress,
                        'updated_at': datetime.now()              
                    }

                    try:

                        contribution_data = SavingContribution(
                                    saving_id=saving_id,
                                    saving_boost_id=saving_boost_id,                            
                                    commit=commit,
                                    user_id=user_id,
                                    **breakdown
                                )
                        session.add(contribution_data)

                        session.query(SavingBoost).filter_by(id=boost_status['id']).update({
                            'next_contribution_date': boost_status['next_contribution_date'],
                            'total_balance': boost_status['total_balance'],
                            'total_monthly_balance': boost_status['total_monthly_balance'],                            
                            'closed_at': boost_status['closed_at']
                        })

                        session.query(Saving).filter_by(id=saving_id).update(update_data)
                        
                        app_data = db.session.query(AppData).filter(AppData.user_id == user_id).first()

                                          
                        app_data.total_monthly_saving += total_monthly_balance_boost                    
                        app_data.saving_updated_at = None
                            
                            
                        

                        session.add(app_data)
                        session.commit()
                        message = 'Saving boost added Succefull'
                        result = 1

                    except Exception as ex:

                        saving_boost_id = None
                        print('Saving Save Exception: ',ex)
                        result = 0
                        message = 'Saving boost addition Failed'
                        session.rollback()
                

                

        else:

            try:
                saving_boost_entry = SavingBoost(**merge_data)
                session.add(saving_boost_entry)
                session.commit()
                saving_boost_id = saving_boost_entry.id
                result = 1 if saving_boost_id!=None else 0
                message = 'Saving boost added Succefull'
            except Exception as ex:

                saving_boost_id = None
                print('Saving Save Exception: ',ex)
                result = 0
                message = 'Saving boost addition Failed'
                session.rollback()
        

        session.close()       

        
        return jsonify({
            "saving_id":saving_boost_id,
            "message":message,
            "result":result
        })