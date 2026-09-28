from calendar import monthrange
from datetime import date
from decimal import Decimal
from app.models.budget import BudgetGoal
from extension import db


DEFAULT_PERCENTAGES = {
    "Housing": 0,
    "Food": 0,
    "Transportation": 0,
    "Utilities": 0,
    "Healthcare": 0,
    "Education": 0,
    "Shopping": 0,
    "Entertainment": 0,
    "Debt": 0,
    "Other": 0,
}

class BudgetServices:
    @staticmethod
    def get_monthly_income(user, year, month):
        total = Decimal("0")

        for income in user.incomes:
            if (
                income.income_date.year == year
                and income.income_date.month == month
            ):
                total += Decimal(str(income.amount))

        return total

    @staticmethod
    def get_monthly_expenses(user, year, month):
        expenses = []

        for expense in user.expenses:
            if (
                expense.expense_date.year == year
                and expense.expense_date.month == month
            ):
                expenses.append(expense)

        return expenses

    @staticmethod
    def calculate_category_spending(expenses):
        spending = {}

        for expense in expenses:
            category = expense.category or "Other"

            amount = Decimal(str(expense.amount))

            spending[category] = (
                spending.get(category, Decimal("0"))
                + amount
            )

        return spending


    @staticmethod
    def get_user_category_percentages(user):
        """
        Fetches user's saved category percentage goals from DB.
        Falls back to DEFAULT_PERCENTAGES for missing or None goals.
        """
        percentages = {cat: Decimal(str(pct)) for cat, pct in DEFAULT_PERCENTAGES.items()}

        if hasattr(user, "budget_goals") and user.budget_goals:
            for goal in user.budget_goals:
                # Only override if custom percentage is explicitly defined
                if goal.percentage is not None:
                    percentages[goal.category] = Decimal(str(goal.percentage))

        return percentages

    @staticmethod
    def calculate_budget(user, year, month):
        income = BudgetServices.get_monthly_income(user, year, month)
        expenses = BudgetServices.get_monthly_expenses(user, year, month)
        spending = BudgetServices.calculate_category_spending(expenses)

        total_expense = sum(spending.values(), Decimal("0"))
        remaining = income - total_expense

        # 1. Fetch category percentages lookup (custom or default)
        category_percentages = BudgetServices.get_user_category_percentages(user)

        # 2. Build direct lookup for user's explicit BudgetGoal models
        user_goals = {}
        if hasattr(user, "budget_goals") and user.budget_goals:
            user_goals = {goal.category: goal for goal in user.budget_goals}

        # 3. Merge all categories (defaults + saved goals + logged spending)
        all_categories = set(category_percentages.keys()).union(set(spending.keys()))

        categories = []

        for category in all_categories:
            goal = user_goals.get(category)
            spent = spending.get(category, Decimal("0"))

            # --- PRIORITY LOGIC ---
            # Priority 1: Fixed dollar amount override (if explicitly set)
            if goal and goal.amount is not None:
                budget_amount = Decimal(str(goal.amount))
                # Compute equivalent percentage for UI display
                percentage = (budget_amount / income * Decimal("100")) if income > 0 else Decimal("0")

            # Priority 2: Custom or default percentage allocation
            else:
                percentage = category_percentages.get(category, Decimal("0"))
                budget_amount = (income * percentage) / Decimal("100")

            remaining_category = budget_amount - spent

            # Calculate usage percentage
            if budget_amount > 0:
                usage = (spent / budget_amount) * Decimal("100")
            else:
                usage = Decimal("100") if spent > 0 else Decimal("0")

            # Determine alert status
            if usage >= 100:
                status, status_text = "danger", "Over budget"
            elif usage >= 80:
                status, status_text = "warning", "Near limit"
            else:
                status, status_text = "normal", "On track"

            categories.append({
                "category": category,
                "percentage": round(float(percentage), 1),
                "budget": float(budget_amount),
                "spent": float(spent),
                "remaining": float(remaining_category),
                "usage": round(float(usage), 1),
                "status": status,
                "status_text": status_text,
                "is_fixed_amount": bool(goal and goal.amount is not None)
            })

        # Sort highest spent category first
        categories.sort(key=lambda x: x["spent"], reverse=True)

        data = {
            "year": year,
            "month": month,
            "income": float(income),
            "total_expense": float(total_expense),
            "remaining": float(remaining),
            "categories": categories
        }

        data["recommendations"] = BudgetServices.generate_budget_recommendations(data)
        return data

    @staticmethod
    def calculate_category_spending(expenses):
        spending = {}
        for expense in expenses:
            category = expense.category or "Other"
            amount = Decimal(str(expense.amount))
            spending[category] = spending.get(category, Decimal("0")) + amount
        return spending


    @staticmethod
    def generate_budget_recommendations(data):
        recommendations = []

        income = data["income"]
        expense = data["total_expense"]
        remaining = data["remaining"]

        if income <= 0:
            recommendations.append({
                "type": "danger",
                "title": "No income recorded",
                "message": (
                    "Add your income information "
                    "to create a meaningful budget."
                )
            })

            return recommendations

        if expense > income:
            recommendations.append({
                "type": "danger",
                "title": "Expenses exceed income",
                "message": (
                    f"Your expenses are "
                    f"${expense:,.2f} while income is "
                    f"${income:,.2f}."
                )
            })

        elif remaining > 0:
            saving_rate = (
                remaining / income
            ) * 100

            recommendations.append({
                "type": "success",
                "title": "Positive cash flow",
                "message": (
                    f"You have ${remaining:,.2f} "
                    f"remaining after expenses."
                ),
                "saving_rate": round(
                    float(saving_rate),
                    1
                )
            })

        for category in data["categories"]:

            if category["status"] == "danger":

                recommendations.append({
                    "type": "danger",
                    "title": f"{category['category']} is over budget",
                    "message": (
                        f"You spent "
                        f"${category['spent']:,.2f} "
                        f"against a "
                        f"${category['budget']:,.2f} budget."
                    )
                })

            elif category["status"] == "warning":

                recommendations.append({
                    "type": "warning",
                    "title": (
                        f"{category['category']} "
                        "is near its limit"
                    ),
                    "message": (
                        f"You have "
                        f"${max(category['remaining'], 0):,.2f} "
                        "remaining."
                    )
                })

        return recommendations


    @staticmethod
    def update_user_goals(user_id, goals_data):
        """
        Updates or creates category percentage goals for a given user.
        Expects goals_data = {"Housing": 30, "Food": 15, ...}
        """
        if not isinstance(goals_data, dict):
            return False, "Invalid payload format"

        total_pct = Decimal("0")

        for category, percentage in goals_data.items():
            try:
                pct_val = Decimal(str(percentage))
                if pct_val < 0:
                    continue
            except Exception:
                continue

            # Check if goal exists for user and category
            goal = BudgetGoal.query.filter_by(user_id=user_id, category=category).first()

            if goal:
                goal.percentage = pct_val
            else:
                goal = BudgetGoal(user_id=user_id, category=category, percentage=pct_val)
                db.session.add(goal)

        db.session.commit()
        return True, "Budget goals updated successfully"

    @staticmethod
    def save_category_goal(user_id, category, percentage=None, amount=None):
        """
        Creates or updates a single category budget goal for a user.
        Mutually clears percentage if amount is provided, and vice versa.
        """
        if not category:
            return False, "Category is required."

        # Helper to convert empty inputs, strings, or zeroes to None/Decimal
        def clean_decimal(val):
            if val is None:
                return None
            s = str(val).strip()
            if not s or s in ("None", "nan"):
                return None
            try:
                d = Decimal(s)
                return d if d > Decimal("0") else None
            except Exception:
                return None

        pct_val = clean_decimal(percentage)
        amt_val = clean_decimal(amount)

        # MUTUAL EXCLUSIVITY RULE:
        # If amount is provided, amount overrides percentage -> clear percentage.
        # If percentage is provided and amount is empty -> clear amount.
        if amt_val is not None:
            pct_val = None
        elif pct_val is not None:
            amt_val = None

        goal = BudgetGoal.query.filter_by(user_id=user_id, category=category).first()

        if goal:
            goal.percentage = pct_val
            goal.amount = amt_val  # <-- Explicitly clears old fixed amount to None when switching to percentage!
        else:
            goal = BudgetGoal(
                user_id=user_id,
                category=category,
                percentage=pct_val,
                amount=amt_val
            )
            db.session.add(goal)

        db.session.commit()
        return True, f"Budget goal for '{category}' saved successfully."