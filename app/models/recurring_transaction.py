from datetime import datetime, date
from extension import db

class RecurringTransaction(db.Model):
    __tablename__ = "recurring_transactions"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # income or expense
    transaction_type = db.Column(db.String(10), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    # weekly, monthly, yearly
    recurring_period = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    next_due_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    last_payment_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = db.relationship("User", back_populates="recurring_transactions")
    expenses = db.relationship("Expense", back_populates="recurring_transaction")
    incomes = db.relationship("Income", back_populates="recurring_transaction")