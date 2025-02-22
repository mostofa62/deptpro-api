import os
from flask import request,jsonify, json
from sqlalchemy import func, or_
#from flask_cors import CORS, cross_origin
from pgutils import new_entry_option_data
from app import app
import re
from util import *
from datetime import datetime

from models import Saving, SavingBoost, SavingBoostType, SavingContribution
from dbpg import db


@app.route('/api/delete-saving-boostpg', methods=['POST'])
def delete_saving_boost_pg():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']
        key = data['key']
        action = 'Deleted' if key < 2 else 'Closed'
        field = SavingBoost.deleted_at if key < 2 else SavingBoost.closed_at
        saving_boost_id = None
        
        message = None
        error = 0
        deleted_done = 0

        try:
            with db.session.begin():
                # Update the SavingBoost record
                saving_boost_update = db.session.query(SavingBoost).filter(SavingBoost.id == saving_boost_id).update(
                    {field: datetime.now()}, synchronize_session=False
                )

                saving_contribution_update = db.session.query(SavingContribution).filter(SavingContribution.id == saving_boost_id).update(
                    {field: datetime.now()}, synchronize_session=False
                )

                if saving_boost_update and saving_contribution_update:
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
    ).join(SavingBoostType, SavingBoost.saving_boost_source_id == SavingBoostType.id, isouter=True)


    
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
        

        # Retrieve the Saving record using SQLAlchemy query
        saving_entry = db.session.query(
            Saving.total_balance_xyz,            
            Saving.commit, 
            Saving.user_id,
            Saving.next_contribution_date
        ).filter_by(id=saving_id).first()

        

        pay_date_boost = saving_entry.next_contribution_date              
        saving_boost = float(data.get("saving_boost", 0))
       


        merge_data = {    
            'saving_id': saving_id,            
            'saving_boost_source_id': new_entry_option_data(data['saving_boost_source'], SavingBoostType, user_id),                
            'user_id': user_id,
            'saver':data['saver'],
            'repeat_boost':data['repeat_boost'], 
            'boost_operation_type':data['boost_operation_type'],   
            'saving_boost': saving_boost,         
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "deleted_at": None,
            "closed_at": None,  
            'pay_date_boost': pay_date_boost,                
            'next_contribution_date': None, 
            'total_balance': 0,
            'note':data['note'] if 'note' in data and data['note']!='' else None,
            'total_balance':0                                   
        }

        try:            
            saving_boost_entry = SavingBoost(**merge_data)
            db.session.add(saving_boost_entry)
            db.session.commit()  # To get the ID of the inserted record
            saving_boost_id = saving_boost_entry.id
            result = 1 if saving_boost_id!=None else 0
            message = 'Saving boost added Succefull'
        except Exception as ex:
            saving_boost_id = None
            print('Saving Save Exception: ',ex)
            result = 0
            message = 'Saving boost addition Failed'

        
        return jsonify({
            "saving_id":saving_boost_id,
            "message":message,
            "result":result
        })