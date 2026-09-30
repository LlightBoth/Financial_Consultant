from datetime import date

from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
)
from flask_login import login_required, current_user

from app.services.recurring_transaction_services import RecurringTransactionServices
from app.forms.income_forms import IncomeForm
from app.forms.expense_forms import ExpenseForm
from app.services import IncomeServices, ExpenseServices


recurring_transaction_bp = Blueprint(
    "recurring_transactions",
    __name__,
    url_prefix="/recurring_transactions"
)


def recurring_to_dict(recurring):
    return {
        "id": recurring.id,
        "user_id": recurring.user_id,
        "transaction_type": recurring.transaction_type,
        "description": recurring.description,
        "category": recurring.category,
        "amount": float(recurring.amount),
        "recurring_period": recurring.recurring_period,

        "start_date": (
            recurring.start_date.isoformat()
            if recurring.start_date else None
        ),

        "next_due_date": (
            recurring.next_due_date.isoformat()
            if recurring.next_due_date else None
        ),

        "end_date": (
            recurring.end_date.isoformat()
            if recurring.end_date else None
        ),

        "last_payment_date": (
            recurring.last_payment_date.isoformat()
            if recurring.last_payment_date else None
        ),

        "is_active": recurring.is_active,

        "created_at": (
            recurring.created_at.isoformat()
            if recurring.created_at else None
        ),

        "updated_at": (
            recurring.updated_at.isoformat()
            if recurring.updated_at else None
        ),
    }


def parse_date(value):
    if not value:
        return None

    return date.fromisoformat(value)


# ---------------------------------------------------------
# PAGE
# ---------------------------------------------------------

@recurring_transaction_bp.route("/", methods=["GET"])
@login_required
def index():
    income_form = IncomeForm()
    expense_form = ExpenseForm()

    return render_template(
        "recurring_transactions/index.html",
        income_form=income_form,
        expense_form=expense_form,
    )


# ---------------------------------------------------------
# CREATE
# ---------------------------------------------------------

@recurring_transaction_bp.route("/api", methods=["POST"])
@login_required
def create_recurring_transaction():

    data = request.get_json(silent=True) or {}

    required_fields = [
        "transaction_type",
        "description",
        "category",
        "amount",
        "recurring_period",
        "start_date",
        "next_due_date",
    ]

    missing = [
        field
        for field in required_fields
        if data.get(field) in (None, "")
    ]

    if missing:
        return jsonify({
            "message": "Missing required fields",
            "fields": missing
        }), 400

    try:
        data["start_date"] = parse_date(
            data["start_date"]
        )

        data["next_due_date"] = parse_date(
            data["next_due_date"]
        )

        data["end_date"] = parse_date(
            data.get("end_date")
        )

        data["amount"] = float(data["amount"])

        if data["amount"] <= 0:
            return jsonify({
                "message": "Amount must be greater than zero."
            }), 400

        recurring = RecurringTransactionServices.create(
            current_user.id,
            data
        )

        return jsonify({
            "message": "Recurring transaction created successfully",
            "data": recurring_to_dict(recurring)
        }), 201

    except ValueError:
        return jsonify({
            "message": "Invalid date or amount format."
        }), 400

    except Exception as e:
        return jsonify({
            "message": "Failed to create recurring transaction",
            "error": str(e)
        }), 500


# ---------------------------------------------------------
# GET ALL
# ---------------------------------------------------------

@recurring_transaction_bp.route("/api", methods=["GET"])
@login_required
def get_recurring_transactions():

    active_only = (
        request.args.get("active_only", "false").lower()
        == "true"
    )

    transactions = RecurringTransactionServices.get_all(
        current_user.id,
        active_only=active_only
    )

    return jsonify({
        "data": [
            recurring_to_dict(transaction)
            for transaction in transactions
        ]
    }), 200


# ---------------------------------------------------------
# GET ONE
# ---------------------------------------------------------

@recurring_transaction_bp.route(
    "/api/<int:recurring_id>",
    methods=["GET"]
)
@login_required
def get_recurring_transaction(recurring_id):

    recurring = RecurringTransactionServices.get_by_id(
        current_user.id,
        recurring_id
    )

    if not recurring:
        return jsonify({
            "message": "Recurring transaction not found"
        }), 404

    return jsonify({
        "data": recurring_to_dict(recurring)
    }), 200


# ---------------------------------------------------------
# UPDATE
# ---------------------------------------------------------

@recurring_transaction_bp.route(
    "/api/<int:recurring_id>",
    methods=["PUT", "PATCH"]
)
@login_required
def update_recurring_transaction(recurring_id):

    data = request.get_json(silent=True) or {}

    try:

        if "start_date" in data:
            data["start_date"] = parse_date(
                data["start_date"]
            )

        if "next_due_date" in data:
            data["next_due_date"] = parse_date(
                data["next_due_date"]
            )

        if "end_date" in data:
            data["end_date"] = parse_date(
                data["end_date"]
            )

        if "amount" in data:
            data["amount"] = float(data["amount"])

        recurring = RecurringTransactionServices.update(
            current_user.id,
            recurring_id,
            data
        )

        if not recurring:
            return jsonify({
                "message": "Recurring transaction not found"
            }), 404

        return jsonify({
            "message": "Recurring transaction updated successfully",
            "data": recurring_to_dict(recurring)
        }), 200

    except ValueError:
        return jsonify({
            "message": "Invalid date or amount format."
        }), 400

    except Exception as e:
        return jsonify({
            "message": "Failed to update recurring transaction",
            "error": str(e)
        }), 500


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------
@recurring_transaction_bp.route(
    "/api/<int:recurring_id>",
    methods=["DELETE"]
)
@login_required
def delete_recurring_transaction(recurring_id):
    recurring = RecurringTransactionServices.get_by_id(
        recurring_id,
        current_user.id
    )

    if recurring is None:
        return jsonify({
            "message": "Recurring transaction not found."
        }), 404


    try:

        if recurring.transaction_type == "income":

            income = IncomeServices.get_income_id(
                recurring.transaction_id,
                current_user.id
            )

            if income:
                IncomeServices.delete_income(income)


        elif recurring.transaction_type == "expense":

            expense = ExpenseServices.get_expense_id(
                recurring.transaction_id,
                current_user.id
            )

            if expense:
                ExpenseServices.delete_expense(expense)


        else:

            return jsonify({
                "message": "Invalid transaction type."
            }), 400


        return jsonify({
            "success": True,
            "message": "Recurring transaction deleted."
        }), 200


    except Exception as e:

        current_app.logger.exception(
            "Failed to delete recurring transaction"
        )

        return jsonify({
            "message": "Unable to delete recurring transaction."
        }), 500



# ---------------------------------------------------------
# DEACTIVATE / PAUSE
# ---------------------------------------------------------

@recurring_transaction_bp.route(
    "/api/<int:recurring_id>/deactivate",
    methods=["PATCH"]
)
@login_required
def deactivate_recurring_transaction(recurring_id):

    recurring = RecurringTransactionServices.deactivate(
        current_user.id,
        recurring_id
    )

    if not recurring:
        return jsonify({
            "message": "Recurring transaction not found"
        }), 404

    return jsonify({
        "message": "Recurring transaction deactivated successfully",
        "data": recurring_to_dict(recurring)
    }), 200


# ---------------------------------------------------------
# DUE
# ---------------------------------------------------------

@recurring_transaction_bp.route(
    "/api/due",
    methods=["GET"]
)
@login_required
def get_due_transactions():

    transactions = (
        RecurringTransactionServices.get_due_transactions(
            current_user.id
        )
    )

    return jsonify({
        "data": [
            recurring_to_dict(transaction)
            for transaction in transactions
        ]
    }), 200

@recurring_transaction_bp.route(
    "/api/<int:recurring_id>/activate",
    methods=["PATCH"]
)
@login_required
def activate_recurring_transaction(recurring_id):

    recurring = RecurringTransactionServices.update(
        current_user.id,
        recurring_id,
        {
            "is_active": True
        }
    )

    if not recurring:
        return jsonify({
            "message": "Recurring transaction not found"
        }), 404

    return jsonify({
        "message": "Recurring transaction activated successfully",
        "data": recurring_to_dict(recurring)
    }), 200


