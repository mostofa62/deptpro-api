import os
from flask import Flask,request,jsonify, json
from sqlalchemy import func, or_, select, update
#from flask_cors import CORS, cross_origin
from savingutil import calculate_breakdown, get_single_breakdown
from app import app
from db import my_col,myclient
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal
from models import Saving,SavingBoost, SavingBoostType, SavingCategory, SavingContribution, SavingMonthlyLog
from dbpg import db
from pgutils import new_entry_option_data
from sqlalchemy.orm import joinedload

@app.route('/api/savingpg/<int:user_id>', methods=['POST'])
def list_saving_pg(user_id: int):
    action = request.args.get('action', None)
    current_month = datetime.now().strftime('%Y-%m')
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
    total_monthly_saving = 0
    
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
    
    total_data = db.session.query(
        func.sum(Saving.goal_amount).label('total_goal_amount'),
        func.sum(Saving.starting_amount).label('total_starting_amount'),
        func.sum(Saving.contribution).label('total_contribution')
    ).filter(Saving.user_id == user_id, Saving.deleted_at.is_(None)).first()
    
    return jsonify({
        'rows': data_list,
        'pageCount': total_pages,
        'totalRows': total_count,
        'extra_payload': {
            'total_goal_amount': total_data.total_goal_amount or 0,
            'total_starting_amount': total_data.total_starting_amount or 0,
            'total_contribution': total_data.total_contribution or 0,
            'total_monthly_saving': round(total_monthly_saving, 2)
        }
    })

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


# Helper function to calculate interest and progress
def calculate_savings(savings):
    # Calculate total savings: starting amount + total contributions + any savings boosts
    total_contributions = savings['contribution'] * savings['months_contributed']
    savings_boost = savings.get('savings_boost', 0)
    total_savings = savings['starting_amount'] + total_contributions + savings_boost
    
    # Calculate interest (assuming monthly compounding for simplicity)
    interest_rate = savings['interest_rate'] / 100
    months = savings['months_contributed']
    interest_earned = total_savings * ((1 + interest_rate / 12) ** months - 1)
    
    # Update progress toward goal
    progress = (total_savings + interest_earned) / savings['goal_amount'] * 100
    
    return total_savings, interest_earned, progress



@app.route('/api/save-saving-accountpg', methods=['POST'])
async def save_saving_pg():
    if request.method == 'POST':
        data = json.loads(request.data)
        user_id = data['user_id']
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

        commit = datetime.now()            
        goal_reached = None                    

        contribution_breakdown = calculate_breakdown(
            starting_amount,
            contribution,
            interest, 
            goal_amount, 
            starting_date,
            repeat,
            i_contribution)
        breakdown = contribution_breakdown['breakdown']
        total_balance = contribution_breakdown['total_balance']
        total_balance_xyz = contribution_breakdown['total_balance_xyz']
        progress  = contribution_breakdown['progress']
        next_contribution_date = contribution_breakdown['next_contribution_date']
        goal_reached = contribution_breakdown['goal_reached']
        period = contribution_breakdown['period']
        is_single = contribution_breakdown['is_single']

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
                    commit=commit
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
                    commit=commit
                )

                db.session.add(saving_data)
                db.session.flush()
                saving_id = saving_data.id

                contribution_data = None                
                
                if is_single > 0:
                    contribution_data = SavingContribution(
                            saving_id=saving_id,
                            deleted_at=None,
                            closed_at=None,
                            commit=commit,
                            user_id=user_id,
                            **breakdown
                        )
                    db.session.add(contribution_data)
                else:
                    contribution_data = [
                            SavingContribution(
                                saving_id=saving_id,
                                deleted_at=None,
                                closed_at=None,
                                commit=commit,
                                user_id=user_id,
                                **todo
                            ) for todo in breakdown
                        ]
                    db.session.bulk_save_objects(contribution_data)                                
                

                monthly_log = SavingMonthlyLog(
                    saving_id=saving_id,
                    user_id=user_id,
                    total_monthly_balance=0,                    
                    updated_at=None
                )

                db.session.add(monthly_log)
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