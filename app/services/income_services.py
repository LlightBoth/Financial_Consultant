from app.models.income import Income
from flask import url_for
from app.services.notification_services import NotificationServices
from decimal import Decimal
from app.models.recurring_transaction import RecurringTransaction

from extension import db
from sqlalchemy import func


class IncomeServices:
    @staticmethod
    def get_all_total_income():
        return Income.query.all()
    
    @staticmethod
    def get_all_income(current_user):
        return Income.query.filter(Income.users.any(id=current_user.id)).all()

    @staticmethod
    def get_filter_income(current_user, sort_value=None):
        query = Income.query.filter(Income.users.any(id=current_user.id))
    
        # Filter by date/amount if provided
        if sort_value == "general":
            query = query.order_by(Income.created_at.asc())
        elif sort_value == "amount":
            query = query.order_by(Income.amount.desc())
        elif sort_value == "date":
            query = query.order_by(Income.created_at.desc())
        else:
            # Default sort by date ascending ('day')
            query = query.order_by(Income.created_at.asc())
            
        return query.all()

    @staticmethod
    def get_income_count(current_user):
        return Income.query.filter(Income.users.any(id=current_user.id)).count()
    
    @staticmethod
    def get_income_total(current_user):
        return (
            db.session.query(func.sum(Income.amount)).filter(Income.users.any(id=current_user.id)).scalar()
            or 0
        )

    @staticmethod
    def get_income_id(income_id: int, user_id: int = None):
        query = Income.query.filter(Income.id == income_id)
        if user_id is not None:
            query = query.filter(Income.users.any(id=user_id))
        return query.first()

    @staticmethod
    def create_income(data: dict, user):
        try:
            income_type = data.get("income_type", "onetime")

            # ==================================================
            # ONE-TIME INCOME
            # ==================================================
            if income_type == "onetime":
                income = Income(
                    amount=Decimal(
                        str(data["amount"])
                    ),
                    description=data.get("description"),
                    category=data["category"],
                    income_date=data["income_date"],
                )
                income.users.append(user)

                db.session.add(income)
                db.session.flush()

                NotificationServices.create_notification(
                    user_id=user.id,
                    title="Income recorded",
                    message=(
                        f"Your income of "
                        f"${income.amount:,.2f} was added."
                    ),
                    notification_type="income",
                    link=url_for("incomes.index")
                )
                db.session.commit()

                return income


            # ==================================================
            # RECURRING INCOME
            # ==================================================
            if income_type == "recurring":
                recurring_period = data.get("recurring_period")
                start_date = data.get("start_date")
                end_date = data.get("end_date")

                if not recurring_period:
                    raise ValueError("Recurring period is required.")

                if not start_date:
                    raise ValueError("Start date is required.")

                if end_date and end_date < start_date:
                    raise ValueError("End date cannot be before start date.")

                # Create recurring schedule
                recurring = RecurringTransaction(
                    user_id=user.id,
                    transaction_type="income",
                    description=data.get("description"),
                    category=data["category"],
                    amount=Decimal(
                        str(data["amount"])
                    ),
                    recurring_period=recurring_period,
                    start_date=start_date,
                    next_due_date=start_date,
                    end_date=end_date,
                    is_active=True
                )

                db.session.add(recurring)

                # Get recurring ID
                db.session.flush()

                # Create first actual income
                income = Income(
                    amount=Decimal(
                        str(data["amount"])
                    ),
                    description=data.get("description"),
                    category=data["category"],
                    income_date=start_date,
                    recurring_transaction_id=recurring.id
                )
                income.users.append(user)

                db.session.add(income)

                NotificationServices.create_notification(
                    user_id=user.id,
                    title="Recurring income created",
                    message=(
                        f"Your recurring income of "
                        f"${income.amount:,.2f} "
                        f"({recurring_period}) was added."
                    ),
                    notification_type="income",
                    link=url_for("incomes.index")
                )
                db.session.commit()

                return income

            raise ValueError("Invalid income type. ""Use 'onetime' or 'recurring'.")

        except Exception:
            db.session.rollback()
            raise


    @staticmethod
    def update_income(income: Income, data: dict):
        try:
            income_type = data.get("income_type", "onetime")
            income.amount = Decimal(str(data["amount"]))
            income.description = data.get("description")
            income.category = data["category"]
            income.income_date = data["income_date"]
            # ==================================================
            # ONE-TIME INCOME
            # ==================================================
            if income_type == "onetime":
                # If this income was previously recurring,
                # remove its recurring relationship.
                recurring = income.recurring_transaction
                if recurring:
                    income.recurring_transaction = None
                    db.session.delete(recurring)

            # ==================================================
            # RECURRING INCOME
            # ==================================================
            elif income_type == "recurring":
                recurring_period = data.get("recurring_period")
                start_date = data.get("start_date")
                end_date = data.get("end_date")

                if not recurring_period:
                    raise ValueError("Recurring period is required.")

                if not start_date:
                    raise ValueError("Start date is required.")

                if end_date and end_date < start_date:
                    raise ValueError("End date cannot be before start date.")

                recurring = income.recurring_transaction

                # --------------------------------------------------
                # ONE-TIME -> RECURRING
                # --------------------------------------------------
                if recurring is None:
                    recurring = RecurringTransaction(
                        user_id=income.users[0].id,
                        transaction_type="income",
                        description=income.description,
                        category=income.category,
                        amount=income.amount,
                        recurring_period=recurring_period,
                        start_date=start_date,
                        next_due_date=start_date,
                        end_date=end_date,
                        is_active=True
                    )

                    db.session.add(recurring)
                    db.session.flush()
                    income.recurring_transaction = recurring
                # --------------------------------------------------
                # RECURRING -> RECURRING
                # --------------------------------------------------
                else:
                    recurring.amount = income.amount
                    recurring.description = income.description
                    recurring.category = income.category
                    recurring.recurring_period = recurring_period
                    recurring.start_date = start_date
                    recurring.end_date = end_date
                    recurring.next_due_date = start_date
                    recurring.is_active = True
            else:
                raise ValueError("Invalid income type.")

            db.session.commit()
            return income

        except Exception:
            db.session.rollback()
            raise


    @staticmethod
    def delete_income(income: Income):
        try:
            db.session.delete(income)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            raise