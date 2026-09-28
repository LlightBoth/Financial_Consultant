from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user

from app.services.advisor_services import AdvisorServices
from app.forms.advisor_forms import AdvisorForm
from app.services.plan_services import PlanServices
from app.security.limiter import limiter
from app.security.cookie import check_cookie_token
from extension import csrf

advisor_bp = Blueprint("advisors", __name__, url_prefix="/advisors")

# Middleware route
@advisor_bp.before_request
def check_token():
    # check_cookie_token(current_user)
    pass

def _format_matched_rules(advice_data):
    """Formats matched advice rules into the localized structure expected by analyse.html."""
    if not advice_data:
        return []

    from app.utils.rule_translations import localize_rule
    from app.utils.i18n import get_locale

    lang = get_locale()
    rules = advice_data.get("matched_rules")
    if not rules:
        best_advice = advice_data.get("get_advice")
        if best_advice and getattr(best_advice, "certainty", 0.0) > 0:
            rules = [best_advice]
        elif best_advice and isinstance(best_advice, dict) and best_advice.get("certainty", 0.0) > 0:
            rules = [best_advice]
        else:
            return []

    formatted = []
    for r in rules:
        if not r:
            continue
        # Avoid empty advice placeholders
        if getattr(r, "certainty", 0.0) == 0.0 and getattr(r, "conclusion", "") == "No recommendations are currently available.":
            continue
        formatted.append(localize_rule(r, lang))
    return formatted



@advisor_bp.route("/personal-analyse", methods=["GET", "POST"])
@login_required
@limiter.limit("15 per minute")
def personalAnalyse():
    form = AdvisorForm()
    if request.method == "GET" and "income" not in request.args and "expense" not in request.args:
        return redirect(url_for("advisors.analyseIndex"))

    income = request.values.get("income", 0.0, type=float) or 0.0
    expense = request.values.get("expense", 0.0, type=float) or 0.0
    data = {
        "income": income,
        "expense": expense,
        "marital_status": request.values.get("marital_status", "Single")
    }

    advice_result = AdvisorServices.persoal_analyse(data)
    matched_rules = _format_matched_rules(advice_result)

    total_plan = PlanServices.get_user_all_plan_total(current_user)
    sum_saving = income - expense
    sum_saving_rate = advice_result.get("remain_percentage", 0.0)
    user_plans = PlanServices.get_user_all_plan_total(current_user)

    return render_template(
        "advisors/analyse.html",
        form=form,
        income=income,
        expense=expense,
        sum_saving=sum_saving,
        sum_saving_rate=sum_saving_rate,
        user_plans=user_plans,
        total_plan=total_plan,
        advice=advice_result,
        matched_rules=matched_rules
    )