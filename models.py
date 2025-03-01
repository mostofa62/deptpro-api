import enum
from sqlalchemy import Column, Date, Float, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from dbpg import db
from sqlalchemy.types import Enum as PgEnum
from sqlalchemy.dialects.postgresql import JSON
class User(db.Model):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    refer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Self-referential foreign key

    name = Column(String, nullable=False, index=True)  # 🔹 Indexed
    email = Column(String, unique=True, nullable=False, index=True)  # 🔹 Indexed & Unique
    memberid = Column(String, unique=True, nullable=True, index=True)  # 🔹 Indexed & Unique
    adminid = Column(String, unique=True, nullable=True, index=True)  # 🔹 Indexed & Unique
    phone = Column(String, nullable=False, index=True)  # 🔹 Indexed

    password = Column(String, nullable=False)  # Store hashed password
    role = Column(Integer, nullable=False)

    token = Column(String, nullable=True)
    token_expired_at = Column(DateTime, nullable=True)

    notified_by_email = Column(Boolean, default=False)
    notified_by_sms = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    suspended_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    # Self-referential relationship
    referrer = relationship("User", remote_side=[id], backref="referrals")

    def __repr__(self):
        return f"<User id={self.id} name={self.name} email={self.email}>"

# 🔹 Additional compound indexes (optional but useful for frequent searches)
Index("idx_user_name", User.name)
Index("idx_user_email", User.email)
Index("idx_user_memberid", User.memberid)
Index("idx_user_adminid", User.adminid)
Index("idx_user_phone", User.phone)


# Enum for Debt Payoff Methods
class DebtPayOffMethod(enum.Enum):
    DEBT_SNOWBALL = 1  # lowest balance first
    DEBT_AVALANCHE = 2  # highest interest rate first
    HIGH_CREDIT_UTILIZATION = 8  # highest credit utilization first
    CUSTOM = 3  # custom method

class UserSettings(db.Model):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"),unique=True, nullable=False, index=True)  # Relating to the users table
    debt_payoff_method = Column(JSON, nullable=False)  # Enum for debt payoff methods
    monthly_budget = Column(Float, nullable=True, default=0.0)  # Monthly budget for debt repayment

    # Relationships
    user = relationship("User", backref="user_settings", lazy="joined")

    def __repr__(self):
        return f"<UserSettings user_id={self.user_id} debt_payoff_method={self.debt_payoff_method} monthly_budget={self.monthly_budget}>"


class AppData(db.Model):
    __tablename__ = "app_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"),unique=True, nullable=False, index=True)  # Foreign key to users table
    total_monthly_gross_income = Column(Float, nullable=True, default=0.0)
    total_monthly_net_income = Column(Float, nullable=True, default=0.0)
    total_yearly_gross_income = Column(Float, nullable=True, default=0.0)
    total_yearly_net_income = Column(Float, nullable=True, default=0.0)
    income_updated_at = Column(DateTime, nullable=True)
    total_monthly_saving = Column(Float, nullable=True, default=0.0)
    saving_updated_at = Column(DateTime, nullable=True)
    total_current_gross_income = Column(Float, nullable=True, default=0.0)
    total_current_net_income = Column(Float, nullable=True, default=0.0)

    # Relationship with the user
    user = relationship("User", backref="app_data", lazy="joined")

    def __repr__(self):
        return f"<AppData user_id={self.user_id} total_monthly_gross_income={self.total_monthly_gross_income} total_monthly_net_income={self.total_monthly_net_income}>"


class IncomeSourceType(db.Model):
    __tablename__ = "income_source_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Foreign Key linking to User
    bysystem = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationship with User model
    user = relationship("User", backref="income_sources", lazy="joined")

    def __repr__(self):
        return f"<IncomeSourceType id={self.id} name={self.name} user_id={self.user_id}>"


class IncomeBoostType(db.Model):
    __tablename__ = "income_boost_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Foreign Key linking to User
    # If you have additional fields like bysystem, add it similarly
    bysystem = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationship with User model
    user = relationship("User", backref="income_boosts_type", lazy="joined")

    def __repr__(self):
        return f"<IncomeBoostType id={self.id} name={self.name} user_id={self.user_id}>"
    

class Income(db.Model):
    __tablename__ = "incomes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    income_source_id = Column(Integer, ForeignKey("income_source_types.id", ondelete="SET NULL"), nullable=True)
    earner = Column(String, nullable=False)
    gross_income = Column(Float, nullable=False, default=0.0)
    net_income = Column(Float, nullable=False, default=0.0)
    pay_date = Column(DateTime, nullable=False)
    repeat = Column(JSON, nullable=False)  # Change this to JSON
    note = Column(String, nullable=True, default="")
    total_net_income = Column(Float, nullable=True, default=0.0)
    total_gross_income = Column(Float, nullable=True, default=0.0)
    created_at = Column(DateTime, nullable=False, default=datetime.now())
    updated_at = Column(DateTime, nullable=False, default=datetime.now(), onupdate=datetime.now())
    closed_at = Column(DateTime, nullable=True)
    next_pay_date = Column(DateTime, nullable=True)
    commit = Column(DateTime, nullable=False, default=datetime.now())
    total_monthly_gross_income = Column(Float, nullable=True, default=0.0)
    total_monthly_net_income = Column(Float, nullable=True, default=0.0)
    total_yearly_gross_income = Column(Float, nullable=True, default=0.0)
    total_yearly_net_income = Column(Float, nullable=True, default=0.0)
    calender_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", backref="incomes", lazy="joined")
    income_source = relationship("IncomeSourceType", backref="incomes", lazy="joined")

    def __repr__(self):
        return f"<Income id={self.id} user_id={self.user_id} income_source_id={self.income_source_id} gross_income={self.gross_income}>"
    

class IncomeBoost(db.Model):
    __tablename__ = "income_boosts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Optional
    income_id = Column(Integer, ForeignKey("incomes.id", ondelete="SET NULL"), nullable=True)  # Optional
    income_boost_source_id = Column(Integer, ForeignKey("income_boost_types.id", ondelete="SET NULL"), nullable=True)  # Relating to income_boost_types table
    earner = Column(String, nullable=False)
    income_boost = Column(Float, nullable=False, default=0.0)  # Amount added as income boost
    pay_date_boost = Column(DateTime, nullable=False)
    repeat_boost = Column(JSON, nullable=False)  # Change this to JSON
    note = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now())
    updated_at = Column(DateTime, nullable=False, default=datetime.now(), onupdate=datetime.now())
    deleted_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    next_pay_date_boost = Column(DateTime, nullable=True)
    total_balance = Column(Float, nullable=True, default=0.0)  # Total balance after applying boost

    # Relationships
    user = relationship("User", backref="income_boosts", lazy="joined")
    income = relationship("Income", backref="income_boosts", lazy="joined")
    income_boost_source = relationship("IncomeBoostType", backref="income_boosts", lazy="joined")

    def __repr__(self):
        return f"<IncomeBoost id={self.id} user_id={self.user_id} income_id={self.income_id} income_boost={self.income_boost} total_balance={self.total_balance}>"
    

class IncomeTransaction(db.Model):
    __tablename__ = "income_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    month_word = Column(String, nullable=False)  # Example: "Dec, 2024"
    month = Column(String, nullable=False, index=True)  # Example: "2024-12"
    month_number = Column(Integer, nullable=True)
    pay_date = Column(DateTime, nullable=False)
    next_pay_date = Column(DateTime, nullable=True)
    gross_income = Column(Float, nullable=False, default=0.0)
    net_income = Column(Float, nullable=False, default=0.0)
    total_gross_for_period = Column(Float, nullable=True, default=0.0)
    total_net_for_period = Column(Float, nullable=True, default=0.0)
    income_id = Column(Integer, ForeignKey("incomes.id", ondelete="SET NULL"), nullable=True)  # Relating to incomes table
    income_boost_id = Column(Integer, ForeignKey("income_boosts.id", ondelete="SET NULL"), nullable=True)  # Relating to income_boosts table (nullable)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Relating to users table
    commit = Column(DateTime, nullable=False, default=datetime.now())
    deleted_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    income = relationship("Income", backref="income_transactions", lazy="joined",foreign_keys=[income_id])
    income_boost = relationship("IncomeBoost", backref="income_transactions", lazy="joined")
    user = relationship("User", backref="income_transactions", lazy="joined")

    def __repr__(self):
        return f"<IncomeTransaction id={self.id} month={self.month} pay_date={self.pay_date} gross_income={self.gross_income} net_income={self.net_income}>"
    

class IncomeMonthlyLog(db.Model):
    __tablename__ = "income_monthly_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    income_id = Column(Integer, ForeignKey("incomes.id", ondelete="SET NULL"), nullable=True)  # Relating to the incomes table
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Relating to the users table
    total_monthly_gross_income = Column(Float, nullable=True, default=0.0)
    total_monthly_net_income = Column(Float, nullable=True, default=0.0)
    updated_at = Column(DateTime, nullable=True)

    # Relationships
    income = relationship("Income", backref="income_monthly_logs", lazy="joined")
    user = relationship("User", backref="income_monthly_logs", lazy="joined")

    def __repr__(self):
        return f"<IncomeMonthlyLog income_id={self.income_id} user_id={self.user_id} total_monthly_gross_income={self.total_monthly_gross_income} total_monthly_net_income={self.total_monthly_net_income}>"
    

class IncomeYearlyLog(db.Model):
    __tablename__ = "income_yearly_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    income_id = Column(Integer, ForeignKey("incomes.id", ondelete="SET NULL"), nullable=True)  # Relating to the incomes table
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Relating to the users table
    total_yearly_gross_income = Column(Float, nullable=True, default=0.0)
    total_yearly_net_income = Column(Float, nullable=True, default=0.0)
    updated_at = Column(DateTime, nullable=True)

    # Relationships
    income = relationship("Income", backref="income_yearly_logs", lazy="joined")
    user = relationship("User", backref="income_yearly_logs", lazy="joined")

    def __repr__(self):
        return f"<IncomeYearlyLog income_id={self.income_id} user_id={self.user_id} total_yearly_gross_income={self.total_yearly_gross_income} total_yearly_net_income={self.total_yearly_net_income}>"


#BILL MODELS
class BillType(db.Model):
    __tablename__ = 'bill_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('bill_types.id'), nullable=True)
    #parent_id = db.Column(db.Integer, nullable=True) # use this avoid conflict
    deleted_at = db.Column(db.DateTime, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ordering = db.Column(db.Integer, nullable=True)

    parent = db.relationship('BillType', remote_side=[id], backref='children', lazy='joined')
    user = db.relationship('User', backref='bill_types', lazy='joined')

    def __repr__(self):
        return f"<BillType(name={self.name}, parent_id={self.parent_id}, user_id={self.user_id})>"


class BillAccounts(db.Model):
    __tablename__ = 'bill_accounts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    bill_type_id = db.Column(db.Integer, db.ForeignKey('bill_types.id', ondelete='SET NULL'), nullable=True)
    payor = db.Column(db.String(100), nullable=True)
    default_amount = db.Column(db.Float, nullable=True)
    current_amount = db.Column(db.Float, nullable=True)
    paid_total = db.Column(db.Float, nullable=True)
    next_due_date = db.Column(DateTime, nullable=True)
    repeat_frequency = db.Column(db.Integer, nullable=True)
    reminder_days = db.Column(db.Integer, nullable=True)
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(DateTime, default=db.func.now())
    updated_at = db.Column(DateTime, default=db.func.now(), onupdate=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    latest_transaction_id = db.Column(db.Integer, db.ForeignKey('bill_transactions.id', ondelete='SET NULL'), nullable=True)
    deleted_at = db.Column(DateTime, nullable=True)
    closed_at = db.Column(DateTime, nullable=True)
    calender_at = db.Column(DateTime, nullable=True)

    bill_type = relationship('BillType', backref='bill_accounts', lazy='joined')
    user = relationship('User', backref='bill_accounts', lazy='joined')
    latest_transaction = relationship(
        'BillTransactions',
        backref='bill_accounts',
        lazy='joined',
        foreign_keys=[latest_transaction_id]  # Explicitly specify the foreign key to use
    )
    def __repr__(self):
        return f"<BillAccounts(name={self.name}, bill_type_id={self.bill_type_id}, payor={self.payor})>"



class BillTransactions(db.Model):
    __tablename__ = 'bill_transactions'

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.Integer, nullable=False)
    payor = db.Column(db.String(100), nullable=True)
    note = db.Column(db.String(255), nullable=True)
    current_amount = db.Column(db.Float, nullable=True)
    due_date = db.Column(DateTime, nullable=True)
    created_at = db.Column(DateTime, default=db.func.now())
    updated_at = db.Column(DateTime, default=db.func.now(), onupdate=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    bill_acc_id = db.Column(db.Integer, db.ForeignKey('bill_accounts.id', ondelete='SET NULL'), nullable=True)    
    payment_status = db.Column(db.Integer, nullable=True)
    deleted_at = db.Column(DateTime, nullable=True)
    closed_at = db.Column(DateTime, nullable=True)
    latest_payment_id = db.Column(db.Integer, db.ForeignKey('bill_payments.id', ondelete='SET NULL'), nullable=True)
    

    bill_account = relationship(
        'BillAccounts',
        backref='bill_transactions',
        lazy='joined',
        foreign_keys=[bill_acc_id]  # Explicitly specify the foreign key to use
    )
    user = relationship('User', backref='bill_transactions', lazy='joined')
    latest_payment = relationship(
        'BillPayments', 
        backref='bill_transactions', 
        lazy='joined',
        foreign_keys=[latest_payment_id]
    )

    def __repr__(self):
        return f"<BillTransactions(amount={self.amount}, bill_acc_id={self.bill_acc_id}, payment_status={self.payment_status})>"




class BillPayments(db.Model):
    __tablename__ = 'bill_payments'

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    pay_date = db.Column(DateTime, nullable=False)
    created_at = db.Column(DateTime, default=db.func.now())
    updated_at = db.Column(DateTime, default=db.func.now(), onupdate=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    bill_trans_id = db.Column(db.Integer, db.ForeignKey('bill_transactions.id', ondelete='SET NULL'), nullable=True)
    bill_account_id = db.Column(db.Integer, db.ForeignKey('bill_accounts.id', ondelete='SET NULL'), nullable=True)
    deleted_at = db.Column(DateTime, nullable=True)

    bill_transaction = relationship(
        'BillTransactions', 
        backref='bill_payments', 
        lazy='joined',
        foreign_keys=[bill_trans_id]
    )
    user = relationship('User', backref='bill_payments', lazy='joined')
    bill_account = relationship(
        'BillAccounts', 
        backref='bill_payments', 
        lazy='joined',
        foreign_keys=[bill_account_id]
    )

    def __repr__(self):
        return f"<BillPayments(amount={self.amount}, bill_trans_id={self.bill_trans_id}, bill_account_id={self.bill_account_id})>"


#DEBT modesl
class DebtType(db.Model):
    __tablename__ = 'debt_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('debt_types.id'), nullable=True)
    #parent_id = db.Column(db.Integer, nullable=True) # use this avoid conflict
    deleted_at = db.Column(db.DateTime, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ordering = db.Column(db.Integer, nullable=True)
    in_calculation = db.Column(db.Integer, nullable=True)

    parent = db.relationship('DebtType', remote_side=[id], backref='children', lazy='joined')
    user = db.relationship('User', backref='debt_types', lazy='joined')

    def __repr__(self):
        return f"<DebtType(name={self.name}, parent_id={self.parent_id}, user_id={self.user_id})>"


class DebtAccounts(db.Model):
    __tablename__ = 'debt_accounts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    debt_type_id = db.Column(db.Integer, db.ForeignKey('debt_types.id', ondelete='SET NULL'), nullable=True)
    payor = db.Column(db.String(100), nullable=True)
    balance = db.Column(db.Float, nullable=True)
    highest_balance = db.Column(db.Float, nullable=True)
    monthly_payment = db.Column(db.Float, nullable=True)
    credit_limit = db.Column(db.Float, nullable=True)
    interest_rate = db.Column(db.Float, nullable=True)
    start_date = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    monthly_interest = db.Column(db.Float, nullable=True)
    note = db.Column(db.Text, nullable=True)
    promo_rate = db.Column(db.Float, nullable=True)
    deffered_interest = db.Column(db.Float, nullable=True)
    promo_interest_rate = db.Column(db.Float, nullable=True)
    promo_good_through_month = db.Column(db.Integer, nullable=True)
    promo_good_through_year = db.Column(db.Integer, nullable=True)
    promo_monthly_interest = db.Column(db.Float, nullable=True)
    autopay = db.Column(db.Boolean, default=False)
    inlclude_payoff = db.Column(db.Boolean, default=False)
    payoff_order = db.Column(db.Integer, nullable=True)
    custom_payoff_order = db.Column(db.Integer, nullable=True)
    reminder_days = db.Column(db.Integer, nullable=True)
    monthly_payment_option = db.Column(db.Float, nullable=True)
    percentage = db.Column(db.Float, nullable=True)
    lowest_payment = db.Column(db.Float, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, onupdate=datetime.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    months_to_payoff = db.Column(db.Integer, nullable=True)
    month_debt_free = db.Column(db.DateTime, nullable=True)
    total_payment_sum = db.Column(db.Float, nullable=True)
    total_interest_sum = db.Column(db.Float, nullable=True)
    calender_at = db.Column(db.DateTime, nullable=True)
    ammortization_at = db.Column(db.DateTime, nullable=True)

    debt_type = db.relationship(
        'DebtType', 
        backref='debt_account', 
        lazy='joined',
        foreign_keys=[debt_type_id]
        )
    user = db.relationship('User', backref='debt_account', lazy='joined')
    #transactions = db.relationship('DebtTransactions', backref='debt_account', lazy=True)


class DebtTransactions(db.Model):
    __tablename__ = 'debt_transactions'

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    previous_balance = db.Column(db.Float, nullable=True)
    new_balance = db.Column(db.Float, nullable=True)
    trans_date = db.Column(db.DateTime, nullable=True)
    type = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=True)
    year = db.Column(db.Integer, nullable=True)
    autopay = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, onupdate=datetime.now())
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    debt_acc_id = db.Column(db.Integer, db.ForeignKey('debt_accounts.id'), nullable=True)
    payment_status = db.Column(db.Integer, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)


    user = db.relationship('User', backref='debt_transaction', lazy='joined')

    debtAccount = db.relationship(
        'DebtAccounts', 
        backref='debt_transaction', 
        lazy=True,
        foreign_keys=[debt_acc_id]
        )



class PaymentBoost(db.Model):
    __tablename__ = 'payment_boosts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False, index=True)  # Relating to the users table
    amount = db.Column(db.Float, nullable=False)  # The payment boost amount
    pay_date_boost = db.Column(db.DateTime, nullable=False)  # The date for the boost
    comment = db.Column(db.String(255), nullable=True)  # Optional comment field
    month = db.Column(db.String(50), nullable=False)  # Month in string format
    created_at = db.Column(db.DateTime, default=datetime.now())  # Automatically sets the creation date
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())  # Automatically updates on modification
    deleted_at = db.Column(db.DateTime, nullable=True)  # Can be used for soft delete functionality

    # Relationship with User
    user = db.relationship('User', backref='payment_boosts', lazy='select')

    def __repr__(self):
        return f"<PaymentBoost(id={self.id}, user_id={self.user_id}, amount={self.amount}, pay_date_boost={self.pay_date_boost}, month={self.month}, created_at={self.created_at}, updated_at={self.updated_at}, deleted_at={self.deleted_at})>"



class PayoffStrategy(db.Model):
    __tablename__ = 'payoff_strategies'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False, index=True)  # Relating to the users table
    debt_payoff_method = db.Column(JSON, nullable=False)  # Storing method as JSON (value, label)
    selected_month = db.Column(JSON, nullable=False)  # Storing selected month as JSON (value, label)
    monthly_budget = db.Column(db.Integer, nullable=False)

    # Relationship to Users with lazy loading
    user = db.relationship('User', backref='payoff_strategies', lazy='select')

    def __repr__(self):
        return f"<PayoffStrategy(id={self.id}, user_id={self.user_id}, debt_payoff_method={self.debt_payoff_method}, selected_month={self.selected_month}, monthly_budget={self.monthly_budget})>"
    




class SavingCategory(db.Model):
    __tablename__ = 'saving_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('saving_categories.id'), nullable=True)
    #parent_id = db.Column(db.Integer, nullable=True) # use this avoid conflict
    deleted_at = db.Column(db.DateTime, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ordering = db.Column(db.Integer, nullable=True)
    in_dashboard_cal = db.Column(db.Integer, nullable=True,default= 0)

    parent = db.relationship('SavingCategory', remote_side=[id], backref='children', lazy='joined')
    user = db.relationship('User', backref='saving_categories', lazy='joined')

    def __repr__(self):
        return f"<SavingCategory(name={self.name}, parent_id={self.parent_id}, user_id={self.user_id})>"



class Saving(db.Model):
    __tablename__ = 'savings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('saving_categories.id'), nullable=False)
    savings_strategy = db.Column(JSON, nullable=False)
    saver = db.Column(db.String(10), nullable=False)
    nickname = db.Column(db.String(100), nullable=True)
    goal_amount = db.Column(db.Float, nullable=False)
    interest = db.Column(db.Float, nullable=False)
    interest_type = db.Column(JSON, nullable=False)
    starting_date = db.Column(db.DateTime, nullable=False)
    starting_amount = db.Column(db.Float, nullable=False)
    contribution = db.Column(db.Float, nullable=False)
    increase_contribution_by = db.Column(db.Float, nullable=True, default=0)
    repeat = db.Column(JSON, nullable=False)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now(), nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    goal_reached = db.Column(db.Boolean, nullable=True)
    next_contribution_date = db.Column(db.DateTime, nullable=True)
    total_balance = db.Column(db.Float, nullable=False, default=0)
    total_balance_xyz = db.Column(db.Float, nullable=False, default=0)
    progress = db.Column(db.Float, nullable=False, default=0)
    period = db.Column(db.Integer, nullable=False, default=0)
    commit = db.Column(db.DateTime, nullable=False, default=datetime.now())
    calender_at = db.Column(db.DateTime, nullable=True)
    total_monthly_balance = db.Column(db.Float, nullable=False, default=0)

    category = db.relationship('SavingCategory', backref='savings', lazy='joined')
    user = db.relationship('User', backref='savings', lazy='joined')

    def __repr__(self):
        return f"<Saving(nickname={self.nickname}, goal_amount={self.goal_amount}, total_balance={self.total_balance})>"



class SavingBoostType(db.Model):
    __tablename__ = 'saving_boost_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref='saving_boost_types', lazy='joined')

    def __repr__(self):
        return f"<SavingBoostType(name={self.name}, user_id={self.user_id})>"
    

class SavingBoost(db.Model):
    __tablename__ = 'saving_boosts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    saving_id = db.Column(db.Integer, db.ForeignKey('savings.id'), nullable=False)
    saver = db.Column(db.String(10), nullable=False)
    saving_boost = db.Column(db.Float, nullable=False)
    saving_boost_source_id = db.Column(db.Integer, db.ForeignKey('saving_boost_types.id'), nullable=False)
    pay_date_boost = db.Column(db.DateTime, nullable=False)
    repeat_boost = db.Column(JSON, nullable=False)
    boost_operation_type = db.Column(JSON, nullable=False)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now(), nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    next_contribution_date = db.Column(db.DateTime, nullable=True)
    total_balance = db.Column(db.Float, nullable=False, default=0)

    saving = db.relationship('Saving', backref='saving_boosts', lazy='select')
    saving_boost_source = db.relationship('SavingBoostType', backref='saving_boosts', lazy='select')
    user = db.relationship('User', backref='saving_boosts', lazy=True)

    def __repr__(self):
        return f"<SavingBoost(saving_boost={self.saving_boost}, total_balance={self.total_balance})>"



class SavingContribution(db.Model):
    __tablename__ = 'saving_contributions'

    id = db.Column(db.Integer, primary_key=True)
    saving_id = db.Column(db.Integer, db.ForeignKey('savings.id'), nullable=False)
    saving_boost_id = db.Column(db.Integer, db.ForeignKey('saving_boosts.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    period = db.Column(db.Integer, nullable=False)
    month = Column(String, nullable=False, index=True)
    month_word = db.Column(db.String(20), nullable=False)
    interest = db.Column(db.Float, nullable=False)
    interest_xyz = db.Column(db.Float, nullable=False)
    contribution = db.Column(db.Float, nullable=False)
    contribution_i = db.Column(db.Float, nullable=False)
    contribution_i_intrs = db.Column(db.Float, nullable=False)
    contribution_i_intrs_xyz = db.Column(db.Float, nullable=False)
    increase_contribution = db.Column(db.Float, nullable=False)
    increase_contribution_prd = db.Column(db.Float, nullable=False)
    total_balance = db.Column(db.Float, nullable=False)
    total_balance_xyz = db.Column(db.Float, nullable=False)
    progress = db.Column(db.Float, nullable=False)
    progress_xyz = db.Column(db.Float, nullable=False)
    contribution_date = db.Column(db.DateTime, nullable=False)
    next_contribution_date = db.Column(db.DateTime, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    commit = db.Column(db.DateTime, nullable=False, default=datetime.now())

    saving = db.relationship('Saving', backref='saving_contributions', lazy='joined')
    saving_boost = db.relationship('SavingBoost', backref='saving_contributions', lazy='joined')
    user = db.relationship('User', backref='saving_contributions', lazy='joined')

    def __repr__(self):
        return f"<SavingContribution(month={self.month}, contribution={self.contribution}, total_balance={self.total_balance})>"



class SavingMonthlyLog(db.Model):
    __tablename__ = 'saving_monthly_logs'

    id = db.Column(db.Integer, primary_key=True)
    saving_id = db.Column(db.Integer, db.ForeignKey('savings.id'), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total_monthly_balance = db.Column(db.Float, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=True)

    saving = db.relationship('Saving', backref='saving_monthly_logs', lazy='joined')
    user = db.relationship('User', backref='saving_monthly_logs', lazy='joined')

    def __repr__(self):
        return f"<SavingMonthlyLog(saving_id={self.saving_id}, total_monthly_balance={self.total_monthly_balance})>"



class CalendarData(db.Model):
    __tablename__ = 'calendar_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    module_name = db.Column(db.String(255), nullable=False)
    module_id = db.Column(db.String(255), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # Format: YYYY-MM
    month_word = db.Column(db.String(50), nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    data_id = db.Column(db.Integer, nullable=False)  # Simple integer, no foreign key relation
    data = db.Column(JSON, nullable=True)  # JSON column to store additional data
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def to_dict(self):
        """Serialize the model to a dictionary."""
        return {
            'id': self.id,
            'module_name': self.module_name,
            'module_id': self.module_id,
            'month': self.month,
            'month_word': self.month_word,
            'event_date': self.event_date.isoformat() if self.event_date else None,  # Date to ISO format
            'data_id': self.data_id,
            'data': self.data,
            'user_id': self.user_id
        }