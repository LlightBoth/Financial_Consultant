from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional
from app.models.budget import BudgetGoal

# Matches your Expense.category options
EXPENSE_CATEGORIES = [
    ("Food", ("food")),
    ("Transportation", ("transportation")),
    ("Housing", ("housing")),
    ("Utilities", ("utilities")),
    ("Education", ("education")),
    ("Healthcare", ("healthcare")),
    ("Shopping", ("shopping")),
    ("Entertainment", ("entertainment")),
    ("Debt", ("debt")),
    ("Other", ("other")),
]

class BudgetGoalForm(FlaskForm):
    category = SelectField(
        ("category"),
        choices=EXPENSE_CATEGORIES,
        validators=[DataRequired(message=("required"))]
    )
    percentage = DecimalField(
        ("percentage"),
        places=2,
        validators=[
            Optional(),
            NumberRange(min=0, max=100, message=("percentage_range"))
        ]
    )
    amount = DecimalField(
        ("amount"),
        places=2,
        validators=[
            Optional(),
            NumberRange(min=0, message=("amount_positive"))
        ]
    )
    submit = SubmitField(("save_goal"))


class EditBudgetGoalForm(FlaskForm):
    category = SelectField(
        ("category"),
        choices=EXPENSE_CATEGORIES,
        validators=[DataRequired(message=("required"))]
    )
    percentage = DecimalField(
        ("percentage"),
        places=2,
        validators=[
            Optional(),
            NumberRange(min=0, max=100, message=("percentage_range"))
        ]
    )
    amount = DecimalField(
        ("amount"),
        places=2,
        validators=[
            Optional(),
            NumberRange(min=0, message=("amount_positive"))
        ]
    )
    submit = SubmitField(("save_goal"))

    def __init__(self, original_budget: BudgetGoal, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.original_budget = original_budget
    
    
# ----- ConfirmDeleteForm -----
class BudgetGoalDeleteForm(FlaskForm):
    submit = SubmitField("Confirm Delete")

