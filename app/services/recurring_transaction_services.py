from datetime import date
from decimal import Decimal

from extension import db
from app.models.recurring_transaction import RecurringTransaction


class RecurringTransactionServices:
    @staticmethod
    def create(user_id, data):
        recurring = RecurringTransaction(
            user_id=user_id,
            transaction_type=data["transaction_type"],
            description=data["description"],
            category=data["category"],
            amount=Decimal(str(data["amount"])),
            recurring_period=data["recurring_period"],
            start_date=data["start_date"],
            next_due_date=data["next_due_date"],
            end_date=data.get("end_date"),
            is_active=data.get("is_active", True),
        )

        db.session.add(recurring)
        db.session.commit()

        return recurring

    @staticmethod
    def get_all(user_id, active_only=False):
        query = RecurringTransaction.query.filter_by(user_id=user_id)

        if active_only:
            query = query.filter_by(is_active=True)

        return query.order_by(RecurringTransaction.next_due_date.asc()).all()

    @staticmethod
    def get_by_id(user_id, recurring_id):
        return RecurringTransaction.query.filter_by(id=recurring_id, user_id=user_id).first()

    @staticmethod
    def update(user_id, recurring_id, data):
        recurring = RecurringTransactionServices.get_by_id(user_id, recurring_id)

        if not recurring:
            return None

        allowed_fields = [
            "transaction_type",
            "description",
            "category",
            "amount",
            "recurring_period",
            "start_date",
            "next_due_date",
            "end_date",
            "is_active",
        ]

        for field in allowed_fields:
            if field in data:
                value = data[field]

                if field == "amount":
                    value = Decimal(str(value))

                setattr(recurring, field, value)

        db.session.commit()

        return recurring

    @staticmethod
    def delete(user_id, recurring_id):
        recurring = RecurringTransactionServices.get_by_id(user_id, recurring_id)

        if not recurring:
            return False

        db.session.delete(recurring)
        db.session.commit()

        return True

    @staticmethod
    def deactivate(user_id, recurring_id):
        recurring = RecurringTransactionServices.get_by_id(user_id, recurring_id)

        if not recurring:
            return None

        recurring.is_active = False
        db.session.commit()

        return recurring

    @staticmethod
    def get_due_transactions(user_id):
        today = date.today()

        return RecurringTransaction.query.filter(
            RecurringTransaction.user_id == user_id,
            RecurringTransaction.is_active == True,
            RecurringTransaction.next_due_date <= today,
            db.or_(
                RecurringTransaction.end_date.is_(None),
                RecurringTransaction.next_due_date <= RecurringTransaction.end_date
            )
        ).order_by(
            RecurringTransaction.next_due_date.asc()
        ).all()
