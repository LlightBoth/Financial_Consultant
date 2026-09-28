from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import func

from app.models.expense import Expense
from app.models.income import Income
from app.models.budget import BudgetGoal


def _month_start(year, month):
    return date(year, month, 1)


def _next_month(year, month):
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def _money(value):
    return Decimal(str(value or 0))


def _user_records(user, relationship_name, date_field, start, end):
    """Use the existing many-to-many User relationship, not a user_id column."""
    records = getattr(user, relationship_name)
    return [
        record for record in records
        if start <= getattr(record, date_field) < end
    ]


def _month_label(year, month):
    return date(year, month, 1).strftime("%b %Y")


def _build_months(end_year, end_month, count=12):
    months = []
    year, month = end_year, end_month
    for _ in range(count):
        months.append((year, month))
        if month == 1:
            year, month = year - 1, 12
        else:
            month -= 1
    return list(reversed(months))


def _aggregate_monthly(user, months, relationship, date_field):
    result = {}
    for year, month in months:
        start = _month_start(year, month)
        end = _next_month(year, month)
        records = _user_records(
            user, relationship, date_field, start, end
        )
        result[(year, month)] = sum(
            (_money(item.amount) for item in records),
            Decimal("0")
        )
    return result


def _aggregate_categories(user, months):
    result = {}
    for year, month in months:
        start = _month_start(year, month)
        end = _next_month(year, month)
        records = _user_records(
            user, "expenses", "expense_date", start, end
        )
        totals = defaultdict(lambda: Decimal("0"))
        for item in records:
            totals[item.category or "Other"] += _money(item.amount)
        result[(year, month)] = dict(totals)
    return result


def _detect_recurring_expenses(user, today):
    """Flag same-category, similar-amount expenses seen in >= 3 distinct months."""
    start_year, start_month = today.year, today.month
    months = _build_months(start_year, start_month, 6)
    start = _month_start(*months[0])
    end = _next_month(today.year, today.month)
    records = _user_records(
        user, "expenses", "expense_date", start, end
    )

    grouped = defaultdict(list)
    for item in records:
        grouped[item.category or "Other"].append(item)

    candidates = []
    for category, items in grouped.items():
        by_month = defaultdict(list)
        for item in items:
            key = (item.expense_date.year, item.expense_date.month)
            by_month[key].append(item)

        active_months = sorted(by_month)
        if len(active_months) < 3:
            continue

        # Estimate recurring amount as the median monthly category total.
        monthly_amounts = [
            sum((_money(x.amount) for x in by_month[key]), Decimal("0"))
            for key in active_months
        ]
        ordered = sorted(monthly_amounts)
        mid = len(ordered) // 2
        median = (
            ordered[mid] if len(ordered) % 2
            else (ordered[mid - 1] + ordered[mid]) / Decimal("2")
        )

        if median <= 0:
            continue

        # Broad category-level heuristic: recurring candidate, not certainty.
        recent = monthly_amounts[-3:]
        near_count = sum(
            1 for amount in recent
            if abs(amount - median) <= max(median * Decimal("0.25"), Decimal("5"))
        )
        if near_count >= 2:
            candidates.append({
                "category": category,
                "estimated_monthly": round(float(median), 2),
                "months_detected": len(active_months),
                "confidence": "Possible",
                "note": "Similar category spending appeared in multiple months."
            })

    candidates.sort(key=lambda x: x["estimated_monthly"], reverse=True)
    return candidates[:8]


def _detect_unusual_changes(months, monthly_expenses):
    """Compare latest month to the average of up to 3 previous available months."""
    if len(months) < 2:
        return []

    latest_key = months[-1]
    latest = monthly_expenses[latest_key]
    previous_keys = months[:-1][-3:]
    previous_values = [monthly_expenses[k] for k in previous_keys]
    if not previous_values:
        return []

    baseline = sum(previous_values, Decimal("0")) / Decimal(len(previous_values))
    delta = latest - baseline
    if baseline <= 0:
        if latest >= Decimal("50"):
            return [{
                "title": "Spending appeared this month",
                "message": f"Latest spending is ${float(latest):,.2f}; there was no meaningful prior baseline.",
                "severity": "info",
                "change_percent": None,
            }]
        return []

    pct = (delta / baseline) * Decimal("100")
    if abs(pct) < Decimal("30") or abs(delta) < Decimal("25"):
        return []

    direction = "increased" if delta > 0 else "decreased"
    return [{
        "title": f"Monthly spending {direction}",
        "message": (
            f"This month: ${float(latest):,.2f}. "
            f"Previous {len(previous_values)}-month average: "
            f"${float(baseline):,.2f}."
        ),
        "severity": "warning" if delta > 0 else "success",
        "change_percent": round(float(pct), 1),
    }]


def get_financial_activity_dashboard(user, year=None, month=None):
    today = date.today()
    year = year or today.year
    month = month or today.month
    months = _build_months(year, month, 12)

    monthly_income = _aggregate_monthly(
        user, months, "incomes", "income_date"
    )
    monthly_expenses = _aggregate_monthly(
        user, months, "expenses", "expense_date"
    )
    category_monthly = _aggregate_categories(user, months)

    labels = [_month_label(y, m) for y, m in months]
    income_values = [round(float(monthly_income[k]), 2) for k in months]
    expense_values = [round(float(monthly_expenses[k]), 2) for k in months]
    cashflow_values = [
        round(float(monthly_income[k] - monthly_expenses[k]), 2)
        for k in months
    ]

    current_key = (year, month)
    prev_key = months[-2] if len(months) >= 2 else current_key
    current_expense = monthly_expenses[current_key]
    previous_expense = monthly_expenses[prev_key]
    month_change = current_expense - previous_expense
    month_change_pct = (
        float(month_change / previous_expense * Decimal("100"))
        if previous_expense > 0 else None
    )

    all_categories = sorted({
        category
        for month_data in category_monthly.values()
        for category in month_data
    })
    category_series = []
    for category in all_categories:
        category_series.append({
            "category": category,
            "values": [
                round(float(category_monthly[k].get(category, Decimal("0"))), 2)
                for k in months
            ],
            "current": round(float(
                category_monthly[current_key].get(category, Decimal("0"))
            ), 2),
        })

    category_series.sort(key=lambda x: x["current"], reverse=True)

    category_changes = []
    for item in category_series:
        current = Decimal(str(item["current"]))
        prior = Decimal(str(
            category_monthly[prev_key].get(item["category"], Decimal("0"))
        ))
        delta = current - prior
        if abs(delta) >= Decimal("20"):
            category_changes.append({
                "category": item["category"],
                "current": float(current),
                "previous": float(prior),
                "change": float(delta),
                "direction": "up" if delta > 0 else "down",
            })
    category_changes.sort(key=lambda x: abs(x["change"]), reverse=True)

    goals = BudgetGoal.query.filter_by(user_id=user.id).all()
    goal_map = {g.category: g for g in goals}
    budget_categories = []
    for item in category_series:
        goal = goal_map.get(item["category"])
        spent = Decimal(str(item["current"]))
        if not goal:
            limit = None
        elif goal.amount is not None:
            limit = _money(goal.amount)
        elif goal.percentage is not None:
            # Percentage budget is calculated from this month's income.
            limit = monthly_income[current_key] * _money(goal.percentage) / Decimal("100")
        else:
            limit = None

        if limit is None:
            status = "unbudgeted"
            usage = None
            remaining = None
        else:
            usage = float(spent / limit * Decimal("100")) if limit > 0 else (
                100.0 if spent > 0 else 0.0
            )
            remaining = float(limit - spent)
            status = "over" if spent > limit else (
                "warning" if usage >= 80 else "on_track"
            )

        budget_categories.append({
            "category": item["category"],
            "spent": float(spent),
            "limit": float(limit) if limit is not None else None,
            "remaining": remaining,
            "usage": round(usage, 1) if usage is not None else None,
            "status": status,
        })

    return {
        "selected_year": year,
        "selected_month": month,
        "labels": labels,
        "income": income_values,
        "expenses": expense_values,
        "cashflow": cashflow_values,
        "monthly": [
            {
                "label": labels[i],
                "income": income_values[i],
                "expense": expense_values[i],
                "cashflow": cashflow_values[i],
            }
            for i in range(len(months))
        ],
        "current_income": float(monthly_income[current_key]),
        "current_expense": float(current_expense),
        "previous_expense": float(previous_expense),
        "month_change": float(month_change),
        "month_change_percent": round(month_change_pct, 1) if month_change_pct is not None else None,
        "category_series": category_series,
        "category_changes": category_changes[:6],
        "budget_categories": budget_categories,
        "recurring": _detect_recurring_expenses(user, today),
        "unusual_changes": _detect_unusual_changes(months, monthly_expenses),
    }
