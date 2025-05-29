from flask import request,jsonify, json
from sqlalchemy import asc, func, update
#from flask_cors import CORS, cross_origin
from app import app
from util import *
from datetime import datetime
from dbpg import db
from models import BillAccounts, BillPayments, BillTransactions
from pgutils import ExtraType, RepeatFrequency


@app.route("/api/delete-bill-transactionpg/<string:accntid>", methods=['POST'])
def delete_bill_transaction_pg(accntid:str):
    if request.method == 'POST':
        data = json.loads(request.data)
        bill_account_id = accntid
        bill_trans_id = data['id']
        admin_id = data['admin_id']
        message = None
        error = 0
        deleted_done = 0
        try:
            # Get the bill account object by ID
            account_current_amount, account_paid_total = db.session.query(
                BillAccounts.current_amount,
                BillAccounts.paid_total
            ).filter_by(id=bill_account_id).first() or (0, 0)

            transaction_current_amount = db.session.query(
                BillTransactions.amount
            ).filter_by(id=bill_trans_id).scalar()

            total_paid_amount = db.session.query(
                func.coalesce(func.sum(BillPayments.amount), 0)
            ).filter(
                BillPayments.bill_trans_id == bill_trans_id
            ).scalar()
            if total_paid_amount > 0:
                account_current_amount += total_paid_amount
                account_paid_total -= total_paid_amount

            
            account_current_amount -= transaction_current_amount

            BillPayments.query.filter_by(bill_trans_id=bill_trans_id).delete()

            # Delete BillTransactions by ID
            BillTransactions.query.filter_by(id=bill_trans_id).delete()
            # Update BillAccounts current_amount
            BillAccounts.query.filter_by(id=bill_account_id).update({
                BillAccounts.current_amount: account_current_amount,
                BillAccounts.paid_total:account_paid_total,
                BillAccounts.admin_id:admin_id,
                BillAccounts.updated_at:datetime.now()
            })

            db.session.commit()  # Commit the changes to the database
            message = f'Bill transaction deleted Successfully'
            deleted_done = 1
            error = 0

        except Exception as ex:
            print('Bill transaction deletion Exception: ', ex)
            message = f'Bill transaction deletion Failed'
            error = 1
            deleted_done = 0
            db.session.rollback()  # Rollback the transaction in case of error

        return jsonify({
            "bill_trans_id": bill_trans_id,
            "message": message,
            "error": error,
            "deleted_done": deleted_done
        })

def distribute_amount(bill_account_id,withdraw_amount):


    documents = (
        db.session.query(BillTransactions.id,BillTransactions.current_amount, BillTransactions.due_date)
        .join(BillAccounts, BillTransactions.bill_acc_id == BillAccounts.id)
        .filter(BillTransactions.bill_acc_id == bill_account_id)
        .filter(BillTransactions.type == ExtraType[0]['value'])
        .filter(BillTransactions.deleted_at.is_(None))
        .order_by(asc(BillTransactions.due_date))
        .all()
    )
    
    affected_ids = []
    remaining_amount = withdraw_amount

    for doc in documents:
        if remaining_amount <= 0:
            break
        
        # Determine how much can be taken from the current document
        amount_to_allocate = min(doc.current_amount, remaining_amount)

        
        
        # Update current_amount in the document
        new_current_amount = doc.current_amount - amount_to_allocate

        payment_status = 1 if new_current_amount <= 0 else 0
        

        db.session.query(BillTransactions).filter(BillTransactions.id == doc.id).update({
            'current_amount': new_current_amount,
            'payment_status': payment_status
        })
        db.session.commit()
        
        if payment_status > 0:
            return []
            # Track the affected document ID
        affected_ids.append({'trans_id':doc.id, 'amount':amount_to_allocate, 'due_date':doc.due_date})
        
        # Update remaining_amount for the next iteration
        remaining_amount -= amount_to_allocate

    # Check if the full withdrawal amount was distributed
    if remaining_amount > 0:
        return []
        #return f"Error: Unable to fully distribute the withdraw_amount. Remaining: {remaining_amount}"

    return affected_ids

# Example usage
#withdraw_amount = 300  # Replace with your desired withdrawal amount
#result = distribute_amount(withdraw_amount)
#print(result)


@app.route("/api/save-bill-transactionpg", methods=['POST'])
def save_bill_transactions_pg():

    if request.method == 'POST':
        data = json.loads(request.data)
        bill_account_id = data['bill']['value']
        user_id = data["user_id"]
        admin_id = data["admin_id"]
        bill_trans_id = None
        message = ''
        result = 0

        current_amount = 0
        

        previous_bill_acc = (
            db.session.query(BillAccounts.current_amount)
            .filter(BillAccounts.id == bill_account_id)            
            .first()
        )
        if previous_bill_acc !=None:
            current_amount = previous_bill_acc.current_amount

        try:

            amount = float(data.get("amount", 0))
            due_date = convertStringTodate(data['due_date'])
            op_type = data['type']['value']

            if op_type < 2:
                current_amount = current_amount + amount
                bill_trans_data = BillTransactions(
                    amount=amount, 
                    type=op_type,
                    payor=data["payor"],
                    note=data["note"] if "note" in data and data["note"]!="" else None,
                    current_amount=amount,                        
                    due_date=due_date,                                                                              
                    created_at=datetime.now(),
                    updated_at=datetime.now(),                        
                    user_id=user_id,
                    admin_id=admin_id,
                    bill_acc_id=bill_account_id,
                    payment_status=0,
                    deleted_at=None,
                    closed_at=None
                )

                db.session.add(bill_trans_data)
                db.session.commit()  # Commit to get the bill_account ID     
                bill_trans_id = bill_trans_data.id

            else:
                current_amount = current_amount - amount
                bill_trans_id = None
                affected_ids = distribute_amount(
                            withdraw_amount=amount,
                            bill_account_id=bill_account_id                            
                        )
                if len(affected_ids) > 0:
                    for af_id in affected_ids:
                        trans_due_date = max(due_date, af_id['due_date'])
                        
                        # Insert into BillPayment table
                        trans_payment_data = BillPayments(
                            amount=af_id['amount'],
                            pay_date=trans_due_date,
                            created_at=datetime.now(),
                            updated_at=datetime.now(),
                            bill_trans_id=af_id['trans_id'],
                            user_id=user_id,
                            admin_id=admin_id,
                            bill_account_id=bill_account_id,
                            deleted_at=None
                        )
                        db.session.add(trans_payment_data)
                        db.session.commit()  # Commit each payment entry separately, or batch it if needed
                       
                        
                    # Insert into BillTransaction table
                    bill_trans_data = BillTransactions(
                        amount=amount,
                        type=op_type,
                        payor=data['payor'],
                        note=data["note"] if "note" in data and data["note"]!="" else None,
                        current_amount=amount,
                        due_date=due_date,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                        user_id=user_id,
                        admin_id=admin_id,
                        bill_acc_id=bill_account_id,
                        payment_status=0,
                        deleted_at=None,
                        closed_at=None
                    )
                    db.session.add(bill_trans_data)
                    db.session.commit()

                    bill_trans_id = bill_trans_data.id  # Get the inserted transaction's ID


            new_values = {
                'current_amount': current_amount,
                'latest_transaction_id': bill_trans_id,  # Assuming this is a foreign key or just an ID
                'updated_at': datetime.now()
            }

            # Perform the update using the `update()` method
            db.session.execute(
                update(BillAccounts)
                .where(BillAccounts.id == bill_account_id)
                .values(new_values)
            )

            db.session.commit()
            message = 'Bill Transaction Succefull'
            bill_account_id = bill_account_id
            result = 1

        
        except Exception as ex:
            print('BILL EXP: ',ex)
            bill_account_id = None
            bill_trans_id = None
            result = 0
            message = 'Bill Transaction Failed!'
            db.session.rollback()
        


        return jsonify({
                    "bill_account_id":bill_account_id,
                    "bill_trans_id":bill_trans_id,
                    "message":message,
                    "result":result
                })
    




@app.route('/api/bill-extraspg/<int:bill_id>', methods=['POST'])
def list_extras_pg(bill_id: int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    sort_by = data.get('sortBy', [])

    # Construct SQLAlchemy query filter
    bill_account_id = bill_id  # Assuming bill_id is the BillAccount's id
    query = BillTransactions.query.with_entities(
        BillTransactions.id,
        BillTransactions.amount, 
        BillTransactions.due_date,
        BillTransactions.pay_date,
        BillTransactions.type,
        BillTransactions.repeat_frequency
        )\
    .join(BillAccounts, BillTransactions.bill_acc_id == BillAccounts.id) \
    .filter(
        BillTransactions.bill_acc_id == bill_account_id,
        BillAccounts.deleted_at == None,
        BillAccounts.closed_at == None
    )

    # Clone for count
    total_count = query.with_entities(db.func.count()).scalar()

    # Handle sorting
    for sort in sort_by:
        sort_field = sort['id']
        sort_direction = 'desc' if sort['desc'] else 'asc'
        query = query.order_by(getattr(BillTransactions, sort_field).desc() if sort_direction == 'desc' else getattr(BillTransactions, sort_field))

    # Apply pagination
    query = query.offset(page_index * page_size).limit(page_size)

    # Fetch data from the database
    transactions = query.all()

    # total_count = BillTransactions.query.filter(
    #     BillTransactions.bill_acc_id == bill_account_id,
    #     BillTransactions.deleted_at == None
    # ).count()

    # Prepare the response data
    data_list = []
    for transaction in transactions:
          # Assuming you have a `to_dict()` method on your model
        
        # Format `due_date` similarly to MongoDB version
        transaction_data={
            'due_date_word': convertDateTostring(transaction.due_date),
            'pay_date_word': convertDateTostring(transaction.pay_date),
            'pay_date': convertDateTostring(transaction.pay_date,('%Y-%m-%d')),
            'due_date': convertDateTostring(transaction.due_date,('%Y-%m-%d')),
            'type':None,
            'amount':transaction.amount,
            "repeat_frequency": next(
                (d['label'] for d in RepeatFrequency if d['value'] == transaction.repeat_frequency),
                None
            ),
        }
        
        # Add `type` label instead of number
        matching_dict = next((item for item in ExtraType if item['value'] == transaction.type), None)
        if matching_dict:
            transaction_data['type'] = matching_dict['label']
        
        # Add the transaction data to the result list
        data_list.append(transaction_data)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size

    # Return the result as JSON
    return jsonify({
        'rows': data_list,
        'pageCount': total_pages,
        'totalRows': total_count
    })





