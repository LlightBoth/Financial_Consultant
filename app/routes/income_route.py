from flask import Blueprint, render_template, redirect, url_for, abort, flash, request
from flask_login import login_required, current_user

from app.forms.income_forms import (IncomeForm, EditIncomeForm, IncomeDeleteForm)

from app.services.income_services import IncomeServices
from app.security.cookie import check_cookie_token
from app.utils.i18n import _
from app.security.role_check import check_route_permission

from datetime import date


income_bp = Blueprint("incomes", __name__, url_prefix="/incomes")


# Middleware
@income_bp.before_request
def check_token():
    check_cookie_token(current_user)
    check_route_permission()


# --------------------------------------------------
# Income List
# --------------------------------------------------
@income_bp.route("/")
@login_required
def index():
    # Reads ?sort_by value from URL; defaults to 'date'
    sort_value = request.args.get("sort", "general")
    incomes = IncomeServices.get_filter_income(current_user, sort_value)
    return render_template("incomes/index.html", incomes=incomes, today=date.today())


# --------------------------------------------------
# Income Detail
# --------------------------------------------------
@income_bp.route("/<int:income_id>")
@login_required
def detail(income_id):
    income = IncomeServices.get_income_id(income_id, current_user.id)
    if income is None:
        abort(404)
    return render_template("incomes/detail.html", income=income)


# --------------------------------------------------
# Create Income
# --------------------------------------------------
@income_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    form = IncomeForm()
    if form.validate_on_submit():
        income_type = request.form.get("income_type", "onetime")

        data = {
            "amount": form.amount.data,
            "description": form.description.data,
            "category": form.category.data,
            "income_date": form.income_date.data,

            "income_type": income_type,

            "recurring_period": (
                form.recurring_period.data
                if income_type == "recurring"
                else None
            ),

            "start_date": (
                form.start_date.data
                if income_type == "recurring"
                else None
            ),

            "end_date": (
                form.end_date.data
                if income_type == "recurring"
                else None
            ),
        }

        try:
            IncomeServices.create_income(data=data, user=current_user)
            flash("Income created successfully.", "success")
            return redirect(url_for("incomes.index"))

        except ValueError as e:
            flash(str(e), "danger")

    return render_template(
        "incomes/create.html",
        form=form,
        submit_label="Save Income"
    )




# --------------------------------------------------
# Edit Income
# --------------------------------------------------
@income_bp.route("/<int:income_id>/edit", methods=["GET", "POST"])
@login_required
def edit(income_id):
    income = IncomeServices.get_income_id(income_id, current_user.id)

    if income is None:
        abort(404)

    recurring = income.recurring_transaction
    form = EditIncomeForm(original_income=income)

    # --------------------------------------------------
    # GET
    # Populate existing values
    # --------------------------------------------------
    if request.method == "GET":

        form.amount.data = income.amount
        form.description.data = income.description
        form.category.data = income.category
        form.income_date.data = income.income_date

        if recurring:
            form.recurring_period.data = recurring.recurring_period
            form.start_date.data = recurring.start_date
            form.end_date.data = recurring.end_date

    # --------------------------------------------------
    # POST
    # --------------------------------------------------
    if form.validate_on_submit():
        income_type = request.form.get("income_type", "onetime")

        data = {
            "amount": form.amount.data,
            "description": form.description.data,
            "category": form.category.data,
            "income_date": form.income_date.data,

            "income_type": income_type,

            "recurring_period": (
                form.recurring_period.data
                if income_type == "recurring"
                else None
            ),

            "start_date": (
                form.start_date.data
                if income_type == "recurring"
                else None
            ),

            "end_date": (
                form.end_date.data
                if income_type == "recurring"
                else None
            ),
        }

        IncomeServices.update_income(income, data)
        flash(f"Income of ${income.amount:.2f} updated successfully.", "success")

        return redirect(url_for("incomes.index"))

    return render_template(
        "incomes/edit.html",
        form=form,
        income=income,
        income_type="recurring" if recurring else "onetime"
    )



# --------------------------------------------------
# Delete Confirmation
# --------------------------------------------------
@income_bp.route("/<int:income_id>/delete", methods=["GET"])
@login_required
def delete_confirm(income_id):
    income = IncomeServices.get_income_id(income_id, current_user.id)
    if income is None:
        abort(404)
    form = IncomeDeleteForm()

    return render_template(
        "incomes/delete_confirm.html",
        form=form,
        income=income
    )


# --------------------------------------------------
# Delete Income
# --------------------------------------------------
@income_bp.route("/<int:income_id>/delete", methods=["POST"])
@login_required
def delete(income_id):
    income = IncomeServices.get_income_id(income_id, current_user.id)
    if income is None:
        abort(404)
    
    form = IncomeDeleteForm()
    if form.validate_on_submit():
        IncomeServices.delete_income(income)
        flash(_("message.income_deleted_success"), "success")
    return redirect(url_for("incomes.index"))
