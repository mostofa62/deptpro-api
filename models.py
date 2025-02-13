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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Relating to the users table
    debt_payoff_method = Column(PgEnum(DebtPayOffMethod), nullable=False)  # Enum for debt payoff methods
    monthly_budget = Column(Float, nullable=True, default=0.0)  # Monthly budget for debt repayment

    # Relationships
    user = relationship("User", backref="user_settings", lazy="joined")

    def __repr__(self):
        return f"<UserSettings user_id={self.user_id} debt_payoff_method={self.debt_payoff_method} monthly_budget={self.monthly_budget}>"


class AppData(db.Model):
    __tablename__ = "app_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Foreign key to users table
    total_monthly_gross_income = Column(Float, nullable=True, default=0.0)
    total_monthly_net_income = Column(Float, nullable=True, default=0.0)
    total_yearly_gross_income = Column(Float, nullable=True, default=0.0)
    total_yearly_net_income = Column(Float, nullable=True, default=0.0)
    total_monthly_saving = Column(Float, nullable=True, default=0.0)
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
    month = Column(String, nullable=False)  # Example: "2024-12"
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
    income = relationship("Income", backref="income_transactions", lazy="joined")
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
