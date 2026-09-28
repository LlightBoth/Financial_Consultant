from datetime import date
from flask import (Blueprint, jsonify, render_template, request, flash, redirect, url_for)
from flask_login import (current_user, login_required)

from app.services.budget_services import BudgetServices
from app.forms.budget_forms import BudgetGoalForm, EditBudgetGoalForm, BudgetGoalDeleteForm
from app.models.budget import BudgetGoal


budget_bp = Blueprint("budgets", __name__, url_prefix="/budget")


@budget_bp.route("/")
@login_required
def planner():
    # Instantiate the form so Jinja can render the CSRF token
    form = BudgetGoalForm()
    return render_template("budgets/planner.html", form=form)


@budget_bp.route("/api")
@login_required
def budget_api():
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)

    if month < 1 or month > 12:
        return jsonify({"error": "Invalid month"}), 400

    # Ensure this returns a dict with a list of categories under 'categories' or similar key
    data = BudgetServices.calculate_budget(current_user, year, month)

    return jsonify(data)

@budget_bp.route("/api/goals", methods=["POST"])
@login_required
def update_budget_goals():
    data = request.get_json() or {}
    success, message = BudgetServices.update_user_goals(current_user.id, data)
    
    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"message": message}), 200


@budget_bp.route("/add-goal", methods=["POST"])
@login_required
def add_budget_goal():
    category = request.form.get("category")
    percentage = request.form.get("percentage")
    amount = request.form.get("amount")

    if not category:
        flash("Please select a valid category.", "danger")
        return redirect(url_for("budgets.planner"))

    # save_category_goal handles upsert (create or update) logic internally
    success, message = BudgetServices.save_category_goal(
        user_id=current_user.id,
        category=category,
        percentage=percentage,
        amount=amount
    )

    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for("budgets.planner"))