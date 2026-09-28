from collections import defaultdict
from decimal import Decimal
from datetime import date
from flask import Blueprint, render_template, jsonify, request, abort
from flask_login import login_required, current_user

from app.services.dashboard_services import DashboardServices
from app.services.income_services import IncomeServices
from app.services.expense_services import ExpenseServices
from app.services.audit_log_services import AuditLogService
from app.security.role_check import role_admin_only
from app.security.cookie import check_cookie_token
from app.utils.i18n import _
from app.services.financial_activity_service import get_financial_activity_dashboard


dashboard_bp = Blueprint("dashboards", __name__, url_prefix="/dashboards")


from flask import render_template, abort
from flask_login import current_user, login_required
from app.services.dashboard_services import DashboardServices
from app.services.income_services import IncomeServices
from app.services.expense_services import ExpenseServices

@dashboard_bp.route("/", methods=["GET"])
@login_required
def userIndex():
    # Role / Permission Guard
    if not (
        current_user.has_role("admin") 
        or current_user.has_role("user")
        or current_user.is_authenticated
    ):
        abort(403)

    # Financial Summaries
    total_income = IncomeServices.get_income_total(current_user) or 0
    total_expense = ExpenseServices.get_expense_total(current_user) or 0

    if total_income > 0:
        sum_saving = total_income - total_expense
        sum_saving_rate = (sum_saving * 100) / total_income
    else:
        sum_saving = -total_expense
        sum_saving_rate = -100.0 if total_expense > 0 else 0.0

    # Chart Data & Active User Plans
    # weekly_saving = DashboardServices.user_weekly_saving(current_user.id) or {
    #     "Mon": 0, "Tue": 0, "Wed": 0, "Thu": 0, "Fri": 0, "Sat": 0, "Sun": 0
    # }
    monthly_cashflow = DashboardServices.user_monthly_cashflow(current_user.id)
    user_plans = DashboardServices.user_all_saving_plan(current_user.id)    
    # Inside userIndex(), before render_template:
    activity = get_financial_activity_dashboard(current_user)

    # Budget summary: fixed monthly budgets + percentage goals calculated from this month's income.
    budget_goals = current_user.budget_goals
    budget_total = Decimal("0")
    for goal in budget_goals:
        if goal.amount is not None:
            budget_total += Decimal(str(goal.amount))
        elif goal.percentage is not None:
            budget_total += Decimal(str(activity["current_income"])) * Decimal(str(goal.percentage)) / Decimal("100")

    # Largest expenses in the selected month (top 5 by amount).
    selected = date.today()
    month_expenses = [
        e for e in current_user.expenses
        if e.expense_date.year == selected.year and e.expense_date.month == selected.month
    ]
    largest_expenses = sorted(month_expenses, key=lambda e: e.amount, reverse=True)[:5]

    # Income source totals for the selected month.
    income_totals = defaultdict(lambda: Decimal("0"))
    for inc in current_user.incomes:
        if inc.income_date.year == selected.year and inc.income_date.month == selected.month:
            income_totals[inc.category] += Decimal(str(inc.amount))
    income_sources = [
        {"category": category, "total": float(total)}
        for category, total in sorted(income_totals.items(), key=lambda x: x[1], reverse=True)
    ]

    return render_template(
        "dashboards/index.html",
        sum_saving=sum_saving,
        sum_saving_rate=round(sum_saving_rate, 2),
        total_income=total_income,
        total_expense=total_expense,
        monthly_cashflow=monthly_cashflow,
        user_plans=user_plans,
        activity=activity,
        budget_total=float(budget_total),
        largest_expenses=largest_expenses,
        income_sources=income_sources,
    )


# Employee / Admin Dashboard Route
@dashboard_bp.route("/emp", methods=["GET"])
@login_required
def empIndex():
    if not current_user.has_role("admin") and not current_user.has_permission("dashboard.admin.view") and not current_user.has_permission("dashboard.emp.view"):
        abort(403)
    total_users = DashboardServices.emp_get_all_users()
    total_plans = DashboardServices.emp_get_all_plans()
    total_incomes = DashboardServices.emp_get_all_incomes()
    total_expenses = DashboardServices.emp_get_all_expenses()
    # total_anayses = DashboardServices.emp_get_all_analyse_advisor()
    total_active_users = DashboardServices.emp_get_all_active_users()
    monthly_users_registered = DashboardServices.emp_get_all_users_registered()

    # Fetch top 3 recent audit logs
    recent_logs = AuditLogService.get_top_3_audit_logs()

    return render_template(
        "dashboards/empIndex.html",
        total_users = total_users,
        total_plans = total_plans,
        total_incomes = total_incomes,
        total_expenses = total_expenses,
        # total_anayses = total_anayses,
        total_active_users=total_active_users,
        monthly_users_registered = monthly_users_registered,
        audit_logs= recent_logs,
        )


# Dashboard API
@dashboard_bp.route("/api", methods=["GET"])
@login_required
def budget_api():
    # Role / Permission Guard
    if not (
        current_user.has_role("admin") 
        or current_user.has_role("user")
        or current_user.is_authenticated
    ):
        return jsonify({"error": "Unauthorized"}), 403

    # Parse year and month query parameters
    today = date.today()
    try:
        year = request.args.get("year", today.year, type=int)
        month = request.args.get("month", today.month, type=int)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid date parameters"}), 400

    if month < 1 or month > 12:
        return jsonify({"error": "Invalid month"}), 400

    # 1. Period Income & Expense Totals
    # Note: Pass (current_user, year, month) to your services if supported, or calculate from models:
    month_incomes = [
        inc for inc in current_user.incomes
        if inc.income_date.year == year and inc.income_date.month == month
    ]
    month_expenses = [
        exp for exp in current_user.expenses
        if exp.expense_date.year == year and exp.expense_date.month == month
    ]

    total_income = sum(float(inc.amount) for inc in month_incomes)
    total_expense = sum(float(exp.amount) for exp in month_expenses)

    # 2. Savings & Savings Rate Calculation
    if total_income > 0:
        sum_saving = total_income - total_expense
        sum_saving_rate = (sum_saving * 100) / total_income
    else:
        sum_saving = -total_expense
        sum_saving_rate = -100.0 if total_expense > 0 else 0.0

    # 3. Financial Activity Dashboard Structure
    # Assuming get_financial_activity_dashboard supports year/month filtering:
    activity = get_financial_activity_dashboard(current_user, year=year, month=month) if callable(get_financial_activity_dashboard) else {
        "current_income": total_income,
        "current_expense": total_expense,
        "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "income": [0] * 12,
        "expenses": [0] * 12,
        "cashflow": [0] * 12,
        "category_series": [],
        "budget_categories": []
    }

    # 4. Monthly Budget Totals Calculation
    budget_goals = current_user.budget_goals
    budget_total = Decimal("0")
    current_inc_dec = Decimal(str(activity.get("current_income", total_income)))

    for goal in budget_goals:
        if goal.amount is not None:
            budget_total += Decimal(str(goal.amount))
        elif goal.percentage is not None:
            budget_total += current_inc_dec * Decimal(str(goal.percentage)) / Decimal("100")

    # 5. Top 5 Largest Expenses for Selected Period
    largest_expenses_data = []
    sorted_expenses = sorted(month_expenses, key=lambda e: e.amount, reverse=True)[:5]
    for e in sorted_expenses:
        largest_expenses_data.append({
            "id": e.id,
            "category": getattr(e, "category", "General"),
            "description": getattr(e, "description", "Expense Item"),
            "amount": float(e.amount),
            "expense_date": e.expense_date.strftime("%Y-%m-%d") if e.expense_date else ""
        })

    # 6. Income Sources Summary
    income_totals = defaultdict(lambda: Decimal("0"))
    for inc in month_incomes:
        income_totals[inc.category] += Decimal(str(inc.amount))

    income_sources = [
        {"category": category, "total": float(total)}
        for category, total in sorted(income_totals.items(), key=lambda x: x[1], reverse=True)
    ]

    # Return unified JSON payload
    return jsonify({
        "status": "success",
        "selected_period": {"year": year, "month": month},
        "sum_saving": float(sum_saving),
        "sum_saving_rate": round(sum_saving_rate, 2),
        "total_income": float(total_income),
        "total_expense": float(total_expense),
        "budget_total": float(budget_total),
        "activity": activity,
        "largest_expenses": largest_expenses_data,
        "income_sources": income_sources
    })