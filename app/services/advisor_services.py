from typing import Dict, Any, Optional
from flask import session, request
from flask_login import current_user

from app.models import Rule, Fact
from app.services.consultant_engine import ConsultantEngine, ConsultantAdviceResult


class EmptyAdvice:
    certainty = 0.0
    advice = "No advice available"
    conclusion = "No conclusion"


class AdvisorServices:

    @staticmethod
    def _get_current_language() -> str:
        """Helper to retrieve the user's active session or cookie language."""
        try:
            return session.get("lang") or request.cookies.get("lang") or "en"
        except Exception:
            return "en"

    # user financial profiles for chat bot 

    # @staticmethod
    # def get_user_financial_profile(user) -> Optional[Dict[str, Any]]:
    #     """
    #     Loads the authoritative financial profile for an authenticated user.

    #     Source of Truth Hierarchy (Option 1):
    #     1. Live Tracker Tables (IncomeServices, ExpenseServices, PlanServices):
    #        Queries real recorded transactions and plans for the user.
    #     2. Active In-Chat Session Cache (`session["advisor_profile"]`):
    #        Honors active conversational overrides (e.g., user says "My expense is now $70" in chat).
    #     3. Fallback: Legacy database `History` record explicitly scoped to `user.id`
    #        (strictly for backward compatibility when tracker tables are empty).
    #     """
    #     if not user or not getattr(user, "is_authenticated", False):
    #         return None

    #     from app.services.income_services import IncomeServices
    #     from app.services.expense_services import ExpenseServices
    #     from app.services.plan_services import PlanServices
    #     from app.models.plan import Plan
    #     from app.models.expense import Expense

    #     # 1. Check live tracker records
    #     income_count = IncomeServices.get_income_count(user)
    #     expense_count = ExpenseServices.get_expense_count(user)
    #     plan_count = PlanServices.get_user_all_plan_count(user)

    #     tracker_profile = None
    #     if income_count > 0 or expense_count > 0 or plan_count > 0:
    #         inc = float(IncomeServices.get_income_total(user)) if income_count > 0 else None
    #         exp = float(ExpenseServices.get_expense_total(user)) if expense_count > 0 else None
    #         goal = float(PlanServices.get_user_all_plan_total(user)) if plan_count > 0 else 0.0

    #         latest_plan = (
    #             Plan.query
    #             .filter(Plan.users.any(id=user.id))
    #             .order_by(Plan.created_at.desc(), Plan.id.desc())
    #             .first()
    #         )

    #         if latest_plan and latest_plan.marital_status:
    #             marital = str(latest_plan.marital_status).strip().capitalize()
    #         else:
    #             marital = "Single"

    #         if latest_plan and latest_plan.employment_status:
    #             emp = str(latest_plan.employment_status).strip().lower()
    #         elif inc is not None and inc > 0:
    #             emp = "employed"
    #         else:
    #             emp = "not employed"

    #         # Check debt status from expenses or plan
    #         has_debt_expense = Expense.query.filter(
    #             Expense.users.any(id=user.id),
    #             Expense.category.ilike("%debt%")
    #         ).first() is not None

    #         has_plan_debt = False
    #         if latest_plan:
    #             raw_debt = str(getattr(latest_plan, "debt_status", "") or "").lower()
    #             if "debt" in raw_debt and "no debt" not in raw_debt and "none" not in raw_debt:
    #                 has_plan_debt = True
    #             elif getattr(latest_plan, "debt_amount", None) and float(latest_plan.debt_amount or 0) > 0:
    #                 has_plan_debt = True

    #         debt = "debt" if (has_debt_expense or has_plan_debt) else "no debt"

    #         # Check spending habit
    #         if latest_plan and latest_plan.spending_habit:
    #             raw_habit = str(latest_plan.spending_habit).strip().lower()
    #             spending = "big spend" if ("big" in raw_habit or "high" in raw_habit) else "average spend"
    #         elif inc is not None and exp is not None and inc > 0 and (exp / inc) > 0.70:
    #             spending = "big spend"
    #         else:
    #             spending = "average spend"

    #         tracker_profile = {
    #             "monthly_income": inc,
    #             "monthly_expense": exp,
    #             "goal_cost": goal,
    #             "marital_status": marital,
    #             "employment_status": emp,
    #             "debt_status": debt,
    #             "spending_habit": spending,
    #             "_source": "tracker_tables",
    #         }

    #     # 2. Check session cache for active in-dialogue conversational overrides
    #     session_cache = None
    #     try:
    #         from flask import session as flask_session
    #         session_cache = flask_session.get("advisor_profile")
    #     except Exception:
    #         pass

    #     # If user has live tracker records, active conversational overrides in session take precedence
    #     # ONLY if they are active in-dialogue chat overrides (tagged with _is_conversational_override)
    #     if tracker_profile:
    #         if session_cache and isinstance(session_cache, dict):
    #             if session_cache.get("_user_id") == user.id and session_cache.get("_is_conversational_override"):
    #                 # Chatbot conversation update
    #                 return {k: v for k, v in session_cache.items() if not k.startswith("_")}
    #         return {k: v for k, v in tracker_profile.items() if not k.startswith("_")}


    #     db_profile = None
    #     if latest_history:
    #         inc = float(latest_history.income) if latest_history.income is not None else None
    #         exp = float(latest_history.expense) if latest_history.expense is not None else None
    #         goal = float(latest_history.goal_cost) if latest_history.goal_cost is not None else 0.0
    #         marital = latest_history.martial_status or "Single"
    #         emp = "employed" if latest_history.is_employed else "not employed"
    #         debt = "debt" if latest_history.is_debt else "no debt"
    #         spending = "big spend" if latest_history.is_spending else "average spend"

    #         db_profile = {
    #             "monthly_income": inc,
    #             "monthly_expense": exp,
    #             "goal_cost": goal,
    #             "marital_status": marital,
    #             "employment_status": emp,
    #             "debt_status": debt,
    #             "spending_habit": spending,
    #             "_source": "database_history",
    #             "_history_id": latest_history.id,
    #             "_created_at": latest_history.created_at.isoformat() if latest_history.created_at else None,
    #         }

    #     if session_cache and isinstance(session_cache, dict):
    #         # Strictly verify cache belongs to current user
    #         if session_cache.get("_user_id") == user.id:
    #             cached_hid = session_cache.get("_history_id")
    #             db_hid = db_profile.get("_history_id") if db_profile else None
    #             # Prevent stale session data from overriding newer database data
    #             if db_hid is not None and cached_hid is not None and db_hid > cached_hid:
    #                 return {k: v for k, v in db_profile.items() if not k.startswith("_")}
    #             # Return active session profile
    #             return {k: v for k, v in session_cache.items() if not k.startswith("_")}

    #     if db_profile:
    #         return {k: v for k, v in db_profile.items() if not k.startswith("_")}

    #     return None

    @staticmethod
    def _evaluate_condition(condition, facts):
        actual_value = facts.get(condition.fact)
        if actual_value is None:
            return False

        if condition.value_fact:
            expected_value = facts.get(condition.value_fact)
        else:
            expected_value = condition.value

        if expected_value is None:
            return False

        try:
            if condition.operator in ("greater_than", ">"):
                return actual_value > expected_value
            if condition.operator in ("greater_than_or_equal", ">="):
                return actual_value >= expected_value
            if condition.operator in ("less_than", "<"):
                return actual_value < expected_value
            if condition.operator in ("less_than_or_equal", "<="):
                return actual_value <= expected_value
            if condition.operator in ("equal", "equals", "=="):
                return actual_value == expected_value
            if condition.operator in ("not_equal", "!="):
                return actual_value != expected_value
            if condition.operator == "contains":
                return expected_value in actual_value
            if condition.operator == "in":
                return actual_value in expected_value
        except (TypeError, ValueError):
            return False

        return False

    @staticmethod
    def _rule_matches(rule, facts):
        # A rule without conditions is treated as a general rule.
        if not rule.conditions:
            return False


        # All conditions belonging to a rule must match.
        return all(
            AdvisorServices._evaluate_condition(condition, facts)
            for condition in rule.conditions
        )

    @staticmethod
    def persoal_analyse(data: dict):
        goal_cost = float(data.get("goal_cost", 0.0) or 0.0)
        income = float(data.get("income", 0.0) or 0.0)
        expense = float(data.get("expense", 0.0) or 0.0)
        marital_status = data.get("marital_status", "Single")

        if income <= 0:
            return {
                "income": income,
                "expense": expense,
                "goal_cost": goal_cost,
                "marital_status": marital_status,
                "monthly_surplus": 0.0,
                "remain_percentage": 0.0,
                "expense_percentage": 0.0,
                "target_certainty": 0.0,
                "get_advice": EmptyAdvice(),
                "matched_rules": [],
                "facts": {
                    "monthly_income": income,
                    "monthly_expense": expense,
                    "monthly_surplus": 0.0,
                    "savings_rate": 0.0,
                    "expense_rate": 0.0,
                    "marital_status": marital_status,
                    "goal_cost": goal_cost,
                },
            }

        monthly_surplus = income - expense
        remain_percentage = monthly_surplus / income
        expense_percentage = expense / income

        # Facts available to the rule engine.
        facts = {
            "monthly_income": income,
            "monthly_expense": expense,
            "monthly_surplus": monthly_surplus,
            "savings_rate": remain_percentage,
            "expense_rate": expense_percentage,
            "marital_status": marital_status,
            "goal_cost": goal_cost,
        }

        # Load all active rules from database.
        rules = Rule.query.order_by(Rule.id.asc()).all()

        # Evaluate every rule against the user's financial facts.
        matched_rules = [
            rule
            for rule in rules
            if AdvisorServices._rule_matches(rule, facts)
        ]

        # Highest certainty first.
        matched_rules.sort(
            key=lambda rule: getattr(rule, "certainty", 0.0) or 0.0,
            reverse=True
        )

        # Keep the highest-certainty recommendation for compatibility
        # with templates that expect advice["get_advice"].
        best_rule = (
            matched_rules[0]
            if matched_rules
            else EmptyAdvice()
        )

        return {
            "income": income,
            "expense": expense,
            "goal_cost": goal_cost,
            "marital_status": marital_status,
            "monthly_surplus": monthly_surplus,
            "remain_percentage": remain_percentage * 100,
            "expense_percentage": expense_percentage * 100,
            "target_certainty": getattr(best_rule, "certainty", 0.0),
            "get_advice": best_rule,
            "matched_rules": matched_rules,
            "facts": facts,
        }