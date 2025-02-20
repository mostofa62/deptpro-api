
import os
from flask import Flask,request,jsonify, json
from util import convertDateTostring
from app import app
from models import SavingCategory, SavingBoostType, Saving
from dbpg import db
from pgutils import RepeatFrequency, SavingInterestType, SavingStrategyType, BoostOperationType

@app.route("/api/savingcategory-dropdownpg/<int:user_id>/<string:boost>", methods=['GET'])
@app.route("/api/savingcategory-dropdownpg/<int:user_id>", methods=['GET'])
def savingcategory_dropdown_pg(user_id: int, boost:str=None):

    saving_category_list = []
    saving_boost_types_list = []
    saving_list = []

    if boost:
        saving_boost_types = (
            db.session.query(SavingBoostType.id, SavingBoostType.name)
            .filter((SavingBoostType.user_id == None) | (SavingBoostType.user_id == user_id))
            .filter(SavingBoostType.deleted_at == None)
            .all()
        )

        saving_boost_types_list = [
            {"value": boost.id, "label": boost.name}
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
    
        # Fetch income source types
        saving_category_types = (
            db.session.query(SavingCategory.id, SavingCategory.name)
            .filter((SavingCategory.user_id == None) | (SavingCategory.user_id == user_id))
            .filter(SavingCategory.deleted_at == None)
            .all()
        )
        
        saving_category_list = [
            {"value": src.id, "label": src.name}
            for src in saving_category_types
        ]


    
    # Fetch income boost types
    
    
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