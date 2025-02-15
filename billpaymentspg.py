import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from app import app
from util import *
from billextra import extra_type
from models import *

@app.route('/api/bill-paymentspg/<int:tranid>', methods=['GET'])
def get_bill_trans_paymentspg(tranid: int):
    # Query the BillPayments model with the necessary filters and sorting
    payments = (
        db.session.query(BillPayments)
        .filter(
            BillPayments.bill_trans_id == tranid,
            BillPayments.deleted_at.is_(None)
        )
        .order_by(BillPayments.pay_date.desc())
        .all()
    )

    # Serialize the data
    payments_list = [
        {
            'amount': payment.amount,
            'pay_date': payment.pay_date.isoformat() if payment.pay_date else None
        }
        for payment in payments
    ]

    return jsonify({
        'payments': payments_list
    })


@app.route('/api/bill-transpg/<int:accntid>', methods=['POST'])
def get_bill_trans_pg(accntid: int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)    
    op_type = extra_type[0]['value']

    # Build query using SQLAlchemy
    query = db.session.query(BillTransactions).filter(
        BillTransactions.bill_acc_id == accntid,
        BillTransactions.type == op_type,
        BillTransactions.deleted_at.is_(None)
    ).order_by(BillTransactions.created_at.desc())

    # Get total count for pagination
    total_count = query.count()

    # Apply pagination
    transactions = query.offset(page_index * page_size).limit(page_size).all()

    # Serialize the data
    data_list = [
        {
            'id': trans.id,
            'amount': trans.amount,
            'type': trans.type,
            'payor': trans.payor,
            'note': trans.note,
            'current_amount': trans.current_amount,
            'due_date': convertDateTostring(trans.due_date,"%Y-%m-%d"),
            'created_at': trans.created_at if trans.created_at else None,
            'updated_at': trans.updated_at if trans.updated_at else None,
            'user_id': trans.user_id,
            'bill_acc_id': trans.bill_acc_id,
            'payment_status': trans.payment_status,
            'deleted_at': trans.deleted_at if trans.deleted_at else None,
            'closed_at': trans.closed_at if trans.closed_at else None,
            'latest_payment_id': trans.latest_payment_id
        }
        for trans in transactions
    ]

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size

    return jsonify({
        'rows': data_list,
        'pageCount': total_pages,
        'totalRows': total_count
    })




@app.route("/api/pay-billpg/<int:accntid>", methods=['POST'])
def pay_bill_transaction_pg(accntid: int):
    if request.method == 'POST':
        data = request.get_json()
        bill_trans_id = data['trans_id']
        bill_account_id = accntid
        trans_payment_id = None
        message = ''
        result = 0

        try:
            # Start transaction
            
            amount = float(data['amount'])
            pay_date = convertStringTodate(data['pay_date'])

            # Create new BillPayment
            new_payment = BillPayments(
                amount=amount,
                pay_date=pay_date,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                bill_trans_id=bill_trans_id,
                bill_account_id=bill_account_id,
                deleted_at=None
            )
            db.session.add(new_payment)
            db.session.flush()  # Get the new payment ID
            trans_payment_id = new_payment.id

            # Fetch and update BillTransactions
            bill_transaction = BillTransactions.query.filter_by(id=bill_trans_id).first()

            if not bill_transaction:
                raise Exception("Bill transaction not found")

            previous_amount = float(bill_transaction.amount)
            current_trans_amount = float(bill_transaction.current_amount)

            # Calculate the new current amount
            current_trans_amount -= amount
            payment_status = 1 if current_trans_amount <= 0 else 0

            # Update BillTransactions
            bill_transaction.current_amount = current_trans_amount
            bill_transaction.payment_status = payment_status
            bill_transaction.latest_payment_id = trans_payment_id
            db.session.add(bill_transaction)

            # Fetch and update BillAccounts
            bill_account = BillAccounts.query.filter_by(id=bill_account_id).first()

            if not bill_account:
                raise Exception("Bill account not found")

            # Calculate the new current amount and paid total
            current_amount = abs(bill_account.current_amount - amount)
            paid_total = bill_account.paid_total or 0
            paid_total += amount

            # Update BillAccounts
            bill_account.current_amount = current_amount
            bill_account.paid_total = paid_total
            bill_account.updated_at = datetime.now()
            db.session.add(bill_account)

            # Commit transaction
            db.session.commit()

            result = 1
            message = 'Bill payment Successful'

        except Exception as ex:
            db.session.rollback()
            print('BILL SAVE PAYMENT ERROR: ', ex)

            bill_account_id = None
            trans_payment_id = None
            result = 0
            message = 'Bill payment Failed!'

        #print(message, result, bill_account_id, bill_trans_id, trans_payment_id)
        return jsonify({
            "bill_account_id": bill_account_id,
            "bill_trans_id": bill_trans_id,
            "trans_payment_id": trans_payment_id,
            "message": message,
            "result": result
        })
