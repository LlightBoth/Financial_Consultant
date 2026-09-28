from extension import db
from datetime import datetime

class BudgetGoal(db.Model):
    __tablename__ = "budget_goals"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    
    # Matches Expense.category ("Food", "Housing", etc.)
    category = db.Column(db.String(50), nullable=False)
    
    # Store fixed target amount (e.g., $500.00) or dynamic percentage (e.g., 10.00%)
    amount = db.Column(db.Numeric(12, 2), nullable=True)
    percentage = db.Column(db.Numeric(5, 2), nullable=True)

    # Prevent duplicate category goals per user
    __table_args__ = (
        db.UniqueConstraint("user_id", "category", name="uq_user_category_budget"),
    )

    user = db.relationship("User", back_populates="budget_goals")