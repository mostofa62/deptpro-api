

from flask import request,jsonify
from sqlalchemy import String, and_, func

from app import app

from util import *
from datetime import datetime,timedelta


from models import Saving,  SavingCategory, SavingContribution
from dbpg import db

def transaction_previous(id: int, column: str = 'saving_id'):
    twelve_months_ago = datetime.now() - timedelta(days=365)

    # If column is 'user_id', we need to get saving_id-wise maximum total_net_for_period, and then sum it by month
    if column == 'user_id':
        # Get the max total_net_for_period for each saving_id and month, and then sum those by month
        subquery = db.session.query(
            SavingContribution.month,
            SavingContribution.saving_id,
            func.max(SavingContribution.total_balance_xyz).label('max_total_balance'),
            #func.min(SavingContribution.month_word).label('month_word')
        ).join(Saving, 
          and_(
          Saving.id == SavingContribution.saving_id,
          Saving.commit == SavingContribution.commit
          )
    ).filter(
            SavingContribution.contribution_date >= twelve_months_ago,
            Saving.deleted_at == None,
            Saving.closed_at == None,
            SavingContribution.user_id == id  # Here we filter by user_id
        ).group_by(
            SavingContribution.month,
            SavingContribution.saving_id
        ).subquery()

        # Now sum those max_total_net_for_periods by month
        result = db.session.query(
            subquery.c.month,
            func.sum(subquery.c.max_total_balance).label('total_balance'),
            #func.min(subquery.c.month_word).label('month_word')
            func.to_char(
                    func.to_date(subquery.c.month.cast(String), 'YYYYMM'), 
                    'Mon, YYYY')
                    .label('year_month_word'),
        ).group_by(
            subquery.c.month
        ).order_by(
            subquery.c.month.asc()
        ).limit(12)

    else:
        # Get the max total_net_for_period for each month and saving_id
        subquery = db.session.query(
            SavingContribution.month,
            SavingContribution.saving_id,
            func.max(SavingContribution.total_balance_xyz).label('total_balance'),
            #func.min(SavingContribution.month_word).label('month_word')
        ).join(Saving, 
          and_(
          Saving.id == SavingContribution.saving_id,
          Saving.commit == SavingContribution.commit
          )
    ).filter(
            SavingContribution.contribution_date >= twelve_months_ago,
            Saving.deleted_at == None,
            Saving.closed_at == None,
            SavingContribution.saving_id == id  # Filter dynamically by saving_id
        ).group_by(
            SavingContribution.month,
            SavingContribution.saving_id
        ).subquery()

        # Now, we just return the results directly without summing
        result = db.session.query(
            subquery.c.month,
            subquery.c.total_balance,
            #subquery.c.month_word
            func.to_char(
                    func.to_date(subquery.c.month.cast(String), 'YYYYMM'), 
                    'Mon, YYYY')
                    .label('year_month_word'),
        ).order_by(
            subquery.c.month.asc()
        ).limit(12)


    # Prepare the result
    year_month_wise_counts = []
    for row in result:
        year_month_wise_counts.append({
            'year_month_word': row.year_month_word,
            'total_balance': row.total_balance
        })

    return year_month_wise_counts



@app.route('/api/saving-contributions-previouspgu/<int:user_id>', methods=['GET'])
def saving_contributions_previous_pgu(user_id:int):

    year_month_wise_counts = transaction_previous(user_id,'user_id')

    # 7. Get the total monthly balance
    total_monthly_balance = 0    
   

    return jsonify({
        "payLoads":{                        
            "year_month_wise_counts":year_month_wise_counts,            
            "total_monthly_balance":total_monthly_balance

        }        
    })


@app.route('/api/saving-contributions-previouspg/<int:saving_id>', methods=['GET'])
def saving_contributions_previous_pg(saving_id:int):

    year_month_wise_counts = transaction_previous(saving_id)

    # 7. Get the total monthly balance
    total_monthly_balance = 0
    if saving_id is not None:
        saving_monthly_log_data = db.session.query(Saving.total_monthly_balance).filter_by(id=saving_id).first()
        if saving_monthly_log_data is not None:
            total_monthly_balance = saving_monthly_log_data.total_monthly_balance
   

    return jsonify({
        "payLoads":{                        
            "year_month_wise_counts":year_month_wise_counts,            
            "total_monthly_balance":total_monthly_balance

        }        
    })






@app.route('/api/saving-contributionspg/<int:saving_id>', methods=['POST'])
def list_saving_contributions_pg(saving_id: int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)

    # Create a base query for SavingTransaction model
    query = db.session.query(
        SavingContribution.id,
        SavingContribution.total_balance,
        SavingContribution.total_balance_xyz,
        SavingContribution.month,
        SavingContribution.contribution_i,
        SavingContribution.interest_xyz,
        SavingContribution.contribution_date,
        SavingContribution.next_contribution_date
    )\
    .join(Saving, 
          and_(
          Saving.id == SavingContribution.saving_id,
          Saving.commit == SavingContribution.commit
          )
    )\
    .filter(
        SavingContribution.saving_id == saving_id,
        SavingContribution.saving_boost_id == None,
        Saving.deleted_at == None,
        Saving.closed_at == None
    )

    # Get the total count of records matching the query
    total_count = query.count()

    # Sorting parameters: Here we're sorting by 'pay_date' in descending order
    query = query.order_by(SavingContribution.contribution_date.desc())

    # Pagination
    query = query.offset(page_index * page_size).limit(page_size)

    

    # Execute the query and get the results
    data_list = query.all()

    # Process the result to format dates
    formatted_data = []
    for todo in data_list:
        formatted_todo = {
            'id':todo.id,            
            'total_balance_xyz':todo.total_balance_xyz,
            'total_balance':todo.total_balance,
            'month_word':convertNumberToDate(todo.month),
            'contribution':todo.contribution_i,
            'contribution_date_word': convertDateTostring(todo.contribution_date),
            'interest_xyz':todo.interest_xyz ,
            'next_contribution_date_word': convertDateTostring(todo.next_contribution_date),
            #'next_pay_date': convertDateTostring(todo.next_pay_date, "%Y-%m-%d"),
           
        }
        formatted_data.append(formatted_todo)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size

    return jsonify({
        'rows': formatted_data,
        'pageCount': total_pages,
        'totalRows': total_count,
    })





@app.route('/api/saving-boost-contributionspg/<int:saving_id>', methods=['POST'])
def list_saving_boost_contributions_pg(saving_id: int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)

    # Create a base query for SavingTransaction model
    query = db.session.query(
        SavingContribution.id,
        SavingContribution.total_balance,
        SavingContribution.total_balance_xyz,
        SavingContribution.month,
        SavingContribution.contribution_i_intrs_xyz,
        SavingContribution.interest_xyz,
        SavingContribution.contribution_date,
        SavingContribution.next_contribution_date
    )\
    .join(Saving, 
          and_(
          Saving.id == SavingContribution.saving_id,
          Saving.commit == SavingContribution.commit
          )
    )\
    .filter(
        SavingContribution.saving_id == saving_id,
        SavingContribution.saving_boost_id != None,
        Saving.deleted_at == None,
        Saving.closed_at == None
    )

    # Get the total count of records matching the query
    total_count = query.count()

    # Sorting parameters: Here we're sorting by 'pay_date' in descending order
    query = query.order_by(SavingContribution.contribution_date.desc())

    # Pagination
    query = query.offset(page_index * page_size).limit(page_size)

    

    # Execute the query and get the results
    data_list = query.all()

    # Process the result to format dates
    formatted_data = []
    for todo in data_list:
        formatted_todo = {
            'id':todo.id,            
            'total_balance_xyz':todo.total_balance_xyz,
            'total_balance':todo.total_balance,
            'month_word':convertNumberToDate(todo.month),
            'contribution':todo.contribution_i_intrs_xyz,
            'contribution_date_word': convertDateTostring(todo.contribution_date),
            'interest_xyz':todo.interest_xyz ,
            'next_contribution_date_word': convertDateTostring(todo.next_contribution_date),
            #'next_pay_date': convertDateTostring(todo.next_pay_date, "%Y-%m-%d"),
           
        }
        formatted_data.append(formatted_todo)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size

    return jsonify({
        'rows': formatted_data,
        'pageCount': total_pages,
        'totalRows': total_count,
    })




@app.route('/api/saving-typewise-infopg/<int:user_id>', methods=['GET'])
def get_typewise_saving_info_pg(user_id:int):

    # Get current month in 'YYYY-MM' format
    #current_month_str = datetime.now().strftime("%Y-%m")
    current_month = int(datetime.now().strftime('%Y%m'))

    #print('current_month_str',current_month_str)

    query = db.session.query(
        Saving.category_id.label('id'),
        SavingCategory.name.label("name"),
        func.sum(SavingContribution.contribution_i_intrs_xyz).label("balance"),
        func.count(Saving.category_id).label('count'),
    ).join(Saving, 
          and_(
          Saving.id == SavingContribution.saving_id,
          Saving.commit == SavingContribution.commit
          )
    )\
     .join(SavingCategory, Saving.category_id == SavingCategory.id) \
     .filter(
         SavingContribution.month == current_month,
         Saving.user_id == user_id,  # Filter by user_id
         Saving.deleted_at == None,
         Saving.closed_at == None
     ) \
     .group_by(
         Saving.category_id,
         SavingCategory.name
     )
    
    #print('query',query)


    results = query.all()

    category_type_counts = []
    category_type_names = {}
    total_balance = 0
    total_saving_source_type=0

    for row in results:
        total_balance +=row.balance
        total_saving_source_type+=1
        category_type_names[row.id]=row.name
        category_type_counts.append({"_id": row.id, "name": row.name, "balance": row.balance, "count": row.count})

    

    

    return jsonify({
        "payLoads":{            
            "category_type_counts":category_type_counts,
            "total_saving_source_type":total_saving_source_type,
            "total_balance":total_balance,
            "category_type_names":category_type_names


        }        
    })

