from app.models.expense import Expense
from flask import url_for
from app.services.notification_services import NotificationServices
from app.models.recurring_transaction import RecurringTransaction

from decimal import Decimal
from extension import db
from sqlalchemy import func



class ExpenseServices:
    @staticmethod
    def get_all_total_expense():
        return Expense.query.all()
    
    @staticmethod
    def get_all_expense(current_user):
        return Expense.query.filter(Expense.users.any(id=current_user.id)).all()

    @staticmethod
    def get_filter_expense(current_user, sort_value=None):
        query = Expense.query.filter(Expense.users.any(id=current_user.id))
    
        # Filter by date/amount if provided
        if sort_value == "general":
            query = query.order_by(Expense.created_at.asc())
        elif sort_value == "amount":
            query = query.order_by(Expense.amount.desc())
        elif sort_value == "date":
            query = query.order_by(Expense.created_at.desc())
        else:
            # Default sort by date ascending ('day')
            query = query.order_by(Expense.created_at.asc())
            
        return query.all()

    @staticmethod
    def get_expense_count(current_user):
        return Expense.query.filter(Expense.users.any(id=current_user.id)).count()
    
    @staticmethod
    def get_expense_total(current_user):
        return (
            db.session.query(func.sum(Expense.amount)).filter(Expense.users.any(id=current_user.id)).scalar()
            or 0
        )

    @staticmethod
    def get_expense_id(expense_id: int, user_id: int = None):
        query = Expense.query.filter(Expense.id == expense_id)
        if user_id is not None:
            query = query.filter(Expense.users.any(id=user_id))
        return query.first()

    @staticmethod
    def create_expense(data: dict, user):
        try:
            expense_type = data.get("expense_type", "onetime")

            # ==================================================
            # ONE-TIME EXPENSE
            # ==================================================
            if expense_type == "onetime":
                expense = Expense(
                    amount=Decimal(str(data["amount"])),
                    description=data.get("description"),
                    category=data["category"],
                    expense_date=data["expense_date"],
                )
                expense.users.append(user)

                db.session.add(expense)
                db.session.flush()

                NotificationServices.create_notification(
                    user_id=user.id,
                    title="Expense recorded",
                    message=(f"Your expense of "
                        f"${expense.amount:,.2f} was added."
                    ),
                    notification_type="expense",
                    link=url_for("expenses.index")
                )
                db.session.commit()

                return expense


            # ==================================================
            # RECURRING EXPENSE
            # ==================================================

            if expense_type == "recurring":
                recurring_period = data.get("recurring_period")
                start_date = data.get("start_date")
                end_date = data.get("end_date")

                if not recurring_period:
                    raise ValueError("Recurring period is required.")

                if not start_date:
                    raise ValueError("Start date is required.")

                if end_date and end_date < start_date:
                    raise ValueError("End date cannot be before start date.")

                # ----------------------------------------------
                # Create recurring schedule
                # ----------------------------------------------

                recurring = RecurringTransaction(
                    user_id=user.id,
                    transaction_type="expense",
                    description=data.get(
                        "description"
                    ),
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

                # Get recurring.id
                db.session.flush()


                # ----------------------------------------------
                # Create first actual expense
                # ----------------------------------------------
                expense = Expense(
                    amount=Decimal(str(data["amount"])),
                    description=data.get("description"),
                    category=data["category"],
                    expense_date=start_date,
                    recurring_transaction_id=recurring.id
                )

                expense.users.append(user)
                db.session.add(expense)

                NotificationServices.create_notification(
                    user_id=user.id,
                    title="Recurring expense created",
                    message=(
                        f"Your recurring expense of "
                        f"${expense.amount:,.2f} "
                        f"({recurring_period}) was added."
                    ),
                    notification_type="expense",
                    link=url_for("expenses.index")
                )
                db.session.commit()

                return expense

            raise ValueError("Invalid expense type. ""Use 'onetime' or 'recurring'.")

        except Exception:
            db.session.rollback()
            raise


    @staticmethod
    def update_expense(expense: Expense, data: dict):
        try:
            expense_type = data.get("expense_type", "onetime")
            # ==================================================
            # UPDATE BASIC EXPENSE
            # ==================================================
            expense.amount = Decimal(str(data["amount"]))
            expense.description = data.get("description")
            expense.category = data["category"]
            expense.expense_date = data["expense_date"]
            # ==================================================
            # ONE-TIME EXPENSE
            # ==================================================

            if expense_type == "onetime":
                recurring = expense.recurring_transaction

                if recurring:
                    expense.recurring_transaction = None

                    db.session.delete(recurring)

            # ==================================================
            # RECURRING EXPENSE
            # ==================================================

            elif expense_type == "recurring":
                recurring_period = data.get("recurring_period")
                start_date = data.get("start_date")
                end_date = data.get("end_date")

                if not recurring_period:
                    raise ValueError("Recurring period is required.")

                if not start_date:
                    raise ValueError("Start date is required.")

                if end_date and end_date < start_date:
                    raise ValueError("End date cannot be before start date.")
                recurring = expense.recurring_transaction
                # ----------------------------------------------
                # ONE-TIME -> RECURRING
                # ----------------------------------------------
                if recurring is None:
                    user_id = expense.users[0].id
                    recurring = RecurringTransaction(
                        user_id=user_id,
                        transaction_type="expense",
                        description=expense.description,
                        category=expense.category,
                        amount=expense.amount,
                        recurring_period=recurring_period,
                        start_date=start_date,
                        next_due_date=start_date,
                        end_date=end_date,
                        is_active=True
                    )
                    db.session.add(recurring)
                    db.session.flush()

                    expense.recurring_transaction = recurring
                # ----------------------------------------------
                # RECURRING -> RECURRING
                # ----------------------------------------------
                else:
                    recurring.amount = expense.amount
                    recurring.description = expense.description
                    recurring.category = expense.category
                    recurring.recurring_period = recurring_period
                    recurring.start_date = start_date
                    recurring.end_date = end_date
                    recurring.next_due_date = start_date
                    recurring.is_active = True
            else:
                raise ValueError("Invalid expense type.")
            
            db.session.commit()

            return expense

        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def delete_expense(expense: Expense):
        try:
            db.session.delete(expense)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            raise