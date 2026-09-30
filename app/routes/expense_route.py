from flask import Blueprint, render_template, redirect, url_for, abort, flash, request
from flask_login import login_required, current_user

from app.forms.expense_forms import (
    ExpenseForm,
    EditExpenseForm,
    ExpenseDeleteForm
)

from app.services.expense_services import ExpenseServices
from app.security.cookie import check_cookie_token
from app.utils.i18n import _
from app.security.role_check import check_route_permission

from datetime import date


expense_bp = Blueprint("expenses", __name__, url_prefix="/expenses")


# --------------------------------------------------
# Middleware
# --------------------------------------------------
@expense_bp.before_request
def check_token():
    check_cookie_token(current_user)
    check_route_permission()


# --------------------------------------------------
# Expense List
# --------------------------------------------------
@expense_bp.route("/")
@login_required
def index():
    # Reads ?sort_by value from URL; defaults to 'date'
    sort_value = request.args.get("sort", "general")
    expenses = ExpenseServices.get_filter_expense(current_user, sort_value)
    return render_template("expenses/index.html", expenses=expenses, today=date.today())


# --------------------------------------------------
# Expense Detail
# --------------------------------------------------
@expense_bp.route("/<int:expense_id>")
@login_required
def detail(expense_id):
    expense = ExpenseServices.get_expense_id(expense_id, current_user.id)
    if expense is None:
        abort(404)
    return render_template("expenses/detail.html", expense=expense)


# --------------------------------------------------
# Create Expense
# --------------------------------------------------
@expense_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    form = ExpenseForm()
    if form.validate_on_submit():
        expense_type = request.form.get("expense_type", "onetime")

        data = {
            "amount": form.amount.data,
            "description": form.description.data,
            "category": form.category.data,
            "expense_date": form.expense_date.data,

            "expense_type": expense_type,

            "recurring_period": (
                form.recurring_period.data
                if expense_type == "recurring"
                else None
            ),

            "start_date": (
                form.start_date.data
                if expense_type == "recurring"
                else None
            ),

            "end_date": (
                form.end_date.data
                if expense_type == "recurring"
                else None
            ),
        }

        try:
            ExpenseServices.create_expense(data=data, user=current_user)
            flash("expense created successfully.", "success")
            return redirect(url_for("expenses.index"))

        except ValueError as e:
            flash(str(e), "danger")

    return render_template(
        "expenses/create.html",
        form=form,
        submit_label="Save expense"
    )




# --------------------------------------------------
# Edit expense
# --------------------------------------------------
@expense_bp.route("/<int:expense_id>/edit", methods=["GET", "POST"])
@login_required
def edit(expense_id):
    expense = ExpenseServices.get_expense_id(expense_id, current_user.id)

    if expense is None:
        abort(404)

    recurring = expense.recurring_transaction
    form = EditExpenseForm(original_expense=expense)

    # --------------------------------------------------
    # GET
    # Populate existing values
    # --------------------------------------------------
    if request.method == "GET":

        form.amount.data = expense.amount
        form.description.data = expense.description
        form.category.data = expense.category
        form.expense_date.data = expense.expense_date

        if recurring:
            form.recurring_period.data = recurring.recurring_period
            form.start_date.data = recurring.start_date
            form.end_date.data = recurring.end_date

    # --------------------------------------------------
    # POST
    # --------------------------------------------------
    if form.validate_on_submit():
        expense_type = request.form.get("expense_type", "onetime")

        data = {
            "amount": form.amount.data,
            "description": form.description.data,
            "category": form.category.data,
            "expense_date": form.expense_date.data,

            "expense_type": expense_type,

            "recurring_period": (
                form.recurring_period.data
                if expense_type == "recurring"
                else None
            ),

            "start_date": (
                form.start_date.data
                if expense_type == "recurring"
                else None
            ),

            "end_date": (
                form.end_date.data
                if expense_type == "recurring"
                else None
            ),
        }

        ExpenseServices.update_expense(expense, data)
        flash(f"expense of ${expense.amount:.2f} updated successfully.", "success")

        return redirect(url_for("expenses.index"))

    return render_template(
        "expenses/edit.html",
        form=form,
        expense=expense,
        expense_type="recurring" if recurring else "onetime"
    )


# --------------------------------------------------
# Delete Confirmation
# --------------------------------------------------
@expense_bp.route("/<int:expense_id>/delete", methods=["GET"])
@login_required
def delete_confirm(expense_id):
    expense = ExpenseServices.get_expense_id(expense_id, current_user.id)
    if expense is None:
        abort(404)

    form = ExpenseDeleteForm()
    return render_template("expenses/delete_confirm.html", expense=expense, form=form)


# --------------------------------------------------
# Delete Expense
# --------------------------------------------------
@expense_bp.route("/<int:expense_id>/delete", methods=["POST"])
@login_required
def delete(expense_id):
    expense = ExpenseServices.get_expense_id(expense_id, current_user.id)
    if expense is None:
        abort(404)

    form = ExpenseDeleteForm()
    if form.validate_on_submit():
        ExpenseServices.delete_expense(expense)
        flash(_("message.expense_deleted_success"), "success")
    return redirect(url_for("expenses.index"))