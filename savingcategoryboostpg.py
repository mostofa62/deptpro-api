
from datetime import datetime
from flask import json, jsonify, request
from sqlalchemy import func, select, update
from util import convertDateTostring
from app import app
from models import SavingBoost, SavingCategory, SavingBoostType, Saving
from dbpg import db
from pgutils import RepeatFrequency, SavingInterestType, SavingStrategyType, BoostOperationType


@app.route('/api/delete-savingboost-sourcepg', methods=['POST'])
def delete_saving_boost_source_pg():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']                   

        saving_source_id = id
        message = None
        error = 0
        deleted_done = 0

        auto_assigned_id = None
        
        try:
            saving_count = db.session.query(func.count()).filter(SavingBoost.saving_boost_source_id == id).scalar()
            if saving_count > 0:
                auto_assigned_id = db.session.execute(
                    select(SavingBoostType.id).where(SavingBoostType.auto_assigned == 1).limit(1)
                ).scalar_one_or_none()

            if auto_assigned_id:
                stmt_update = update(SavingBoost)\
                        .where(SavingBoost.saving_boost_source_id == id)\
                        .values(
                        saving_boost_source_id=auto_assigned_id                                    
                        )
                db.session.execute(stmt_update)

            

            stmt_update = update(SavingBoostType)\
                        .where(SavingBoostType.id == id)\
                        .values(
                        deleted_at=datetime.now()                                    
                        )
            db.session.execute(stmt_update)
            db.session.commit()
            saving_source_id = id
            error = 0
            deleted_done = 1
            message = f'Saving boost type deleted Successfully'

        except Exception as ex:
            print('EX',ex)
            db.session.rollback()
            saving_source_id = None
            error = 1
            deleted_done = 0
            message = f'Saving boost type deleted Failed'


           


        return jsonify({
            "saving_source_id":saving_source_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })

        

   

@app.route('/api/delete-saving-sourcepg', methods=['POST'])
def delete_saving_source_pg():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']                   

        saving_source_id = id
        message = None
        error = 0
        deleted_done = 0

        auto_assigned_id = None
        
        try:
            saving_count = db.session.query(func.count()).filter(Saving.category_id == id).scalar()
            if saving_count > 0:
                auto_assigned_id = db.session.execute(
                    select(SavingCategory.id).where(SavingCategory.auto_assigned == 1).limit(1)
                ).scalar_one_or_none()

            if auto_assigned_id:
                stmt_update = update(Saving)\
                        .where(Saving.category_id == id)\
                        .values(
                        category_id=auto_assigned_id                                    
                        )
                db.session.execute(stmt_update)

            

            stmt_update = update(SavingCategory)\
                        .where(SavingCategory.id == id)\
                        .values(
                        deleted_at=datetime.now()                                    
                        )
            db.session.execute(stmt_update)
            db.session.commit()
            saving_source_id = id
            error = 0
            deleted_done = 1
            message = f'Saving source deleted Successfully'

        except Exception as ex:
            print('EX',ex)
            db.session.rollback()
            saving_source_id = None
            error = 1
            deleted_done = 0
            message = f'Saving source deleted Failed'


           


        return jsonify({
            "saving_source_id":saving_source_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })


@app.route("/api/savingcategory-dropdownpg/<int:user_id>/<string:boost>", methods=['GET'])
@app.route("/api/savingcategory-dropdownpg/<int:user_id>", methods=['GET'])
def savingcategory_dropdown_pg(user_id: int, boost:str=None):

    saving_category_list = []
    saving_boost_types_list = []
    saving_list = []

    if boost:
        saving_boost_types = (
            db.session.query(SavingBoostType.id, SavingBoostType.name, SavingBoostType.bysystem)
            .filter((SavingBoostType.user_id == None) | (SavingBoostType.user_id == user_id))
            .filter(SavingBoostType.auto_assigned == 0)
            .filter(SavingBoostType.deleted_at == None)
            .all()
        )

        saving_boost_types_list = [
            {"value": boost.id, "label": boost.name,"bysystem": boost.bysystem}
            for boost in saving_boost_types
        ]

        savings = (
        db.session.query(Saving.id, Saving.saver, Saving.repeat, Saving.next_contribution_date)
        .filter(Saving.user_id == user_id, Saving.deleted_at == None, Saving.closed_at == None)
        .all()
        )
        
        saving_list = [
            {
                "value": str(inc.id),
                "label": inc.saver,
                "repeat_boost": inc.repeat,  # Enum value as name
                "pay_date_boost": convertDateTostring(inc.next_contribution_date,"%Y-%m-%d")
            }
            for inc in savings
        ] 

    else:   
    
        # Fetch saving source types
        saving_category_types = (
            db.session.query(SavingCategory.id, SavingCategory.name, SavingCategory.bysystem)
            .filter((SavingCategory.user_id == None) | (SavingCategory.user_id == user_id))
            .filter(SavingCategory.auto_assigned == 0)
            .filter(SavingCategory.deleted_at == None)
            .all()
        )
        
        saving_category_list = [
            {"value": src.id, "label": src.name,"bysystem": src.bysystem}
            for src in saving_category_types
        ]


    
    # Fetch saving boost types
    
    
    # Fetch savings
    
    
    return jsonify({
        "payLoads": {
            "saving_category": saving_category_list,
            "saving_boost_source": saving_boost_types_list,
            "saving_interest_type":SavingInterestType,
            "saving_strategy_type": SavingStrategyType,
            "repeat_frequency":RepeatFrequency,
            "saving_list":saving_list,
            'boost_operation_type':BoostOperationType
        }
    })