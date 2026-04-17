import calendar
import json
from datetime import date, datetime
from odoo import http
from odoo.http import request
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import jwt
from reportlab.lib.pagesizes import elevenSeventeen
from ..utils.q1_helpers import Q1Helpers
from ..utils.q2_helpers import Q2Helpers
from ..utils.q3_helpers import Q3Helpers

SECRET_KEY = "Your-secret-key"


def _cors_headers():
    return [
        ('Access-Control-Allow-Origin', '*'),
        ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
        ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
    ]


def _json_headers():
    # Odoo automatically adds CORS headers when cors='*' is set in route decorator
    # So we only need Content-Type here
    return [('Content-Type', 'application/json')]


class BizdomQuadrant(http.Controller):

    # Overeview of a score for the past three months

    def _get_pillar_domain(self, company_id, is_owner, allowed_pillar_ids):
        domain = [('company_id', '=', company_id)]
        if not is_owner:
            domain.append(('id', 'in', allowed_pillar_ids))
        return domain

    @staticmethod
    def get_days_in_month_excluding_sundays(year, month):
        """Calculate the number of days in a month excluding Sundays."""
        total_days = calendar.monthrange(year, month)[1]
        # Count Sundays in the month
        sunday_count = 0
        for day in range(1, total_days + 1):
            current_date = date(year, month, day)
            if current_date.weekday() == 6:  # Sunday is 6 in Python's weekday()
                sunday_count += 1
        return total_days - sunday_count

    @staticmethod
    def get_days_up_to_date_excluding_sundays(year, month, end_day):
        """Calculate the number of days from the start of the month up to end_day, excluding Sundays."""
        days_count = 0
        for day in range(1, end_day + 1):
            current_date = date(year, month, day)
            if current_date.weekday() != 6:  # Exclude Sundays
                days_count += 1
        return days_count

    @staticmethod
    def get_days_in_range_excluding_sundays(start_date, end_date):
        """Calculate the number of days in a date range excluding Sundays."""
        days_count = 0
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() != 6:  # Exclude Sundays
                days_count += 1
            current_date += timedelta(days=1)
        return days_count

    # First Quadrant
    @http.route('/api/score/overview', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_score_overview(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return request.make_response(
                "",
                headers=[
                    ('Access-Control-Allow-Origin', '*'),
                    ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                    ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
                ]
            )

        # Auth check - support both JWT token and session-based auth
        auth_header = request.httprequest.headers.get("Authorization")
        uid = False
        if auth_header:
            # External API call - require JWT token only (no session fallback)
            token = auth_header.split(" ")[1] if auth_header.startswith("Bearer ") else auth_header
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                uid = payload.get("uid")
                if isinstance(uid, dict):
                    uid = uid.get("uid")
            except jwt.ExpiredSignatureError:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Token expired"}),
                    headers=_json_headers()
                )
            except jwt.InvalidTokenError:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Invalid token"}),
                    headers=_json_headers()
                )
        else:
            # Internal dashboard call - allow session-based auth if same-origin
            # BUT exclude Swagger UI requests (which should use JWT)
            referer = request.httprequest.headers.get('Referer', '')
            origin = request.httprequest.headers.get('Origin', '')
            host = request.httprequest.headers.get('Host', '')

            # Check if request is from Swagger UI - if so, require JWT token
            is_from_swagger = False
            if referer and '/bizdom-api' in referer:
                is_from_swagger = True

            # If from Swagger, don't allow session fallback - require JWT
            if is_from_swagger:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Token missing"}),
                    headers=_json_headers()
                )

            # Check if request is from same origin (internal Odoo dashboard, not Swagger)
            is_same_origin = False
            if host:
                if referer and host in referer:
                    is_same_origin = True
                elif origin and (host in origin or origin.replace('http://', '').replace('https://', '') == host):
                    is_same_origin = True
                elif not referer and not origin:
                    # Same-origin requests might not send these headers
                    # Check if we have a valid session as additional validation
                    is_same_origin = True

            # Allow session auth only for same-origin requests (not from Swagger)
            if is_same_origin and request.session.uid:
                uid = request.session.uid
            else:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Token missing"}),
                    headers=_json_headers()
                )

        if not uid:
            return request.make_response(
                json.dumps({"statusCode": 401, "message": "Token missing"}),
                headers=_json_headers()
            )

        # Extract parameters
        score_id = int(kwargs.get('scoreId', 0))
        if not score_id:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": "scoreId is required"}),
                headers=_json_headers()
            )

        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists() or len(user) != 1:
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "User not found or multiple users"}),
                headers=_json_headers()
            )

        score_record = request.env['bizdom.score'].sudo().browse(score_id)
        if not score_record.exists():
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "Score record not found"}),
                headers=_json_headers()
            )

        filter_type = kwargs.get('filterType')
        start_date_str = kwargs.get('startDate')
        end_date_str = kwargs.get('endDate')
    

        company = user.company_id
        is_owner = user.has_group('bizdom.group_bizdom_owner')
        allowed_pillar_ids = user.bizdom_allowed_pillar_ids.ids
        pillar_domain = self._get_pillar_domain(company.id, is_owner, allowed_pillar_ids)


        if not is_owner and score_record.pillar_id.id not in allowed_pillar_ids:
            return request.make_response(
                json.dumps({"statusCode": 403, "message": "score_id not allowed "}),
                headers=_json_headers()
            )



        # Get date ranges using utility
        try:
            date_ranges = Q1Helpers.get_date_ranges(filter_type, start_date_str, end_date_str)
        except ValueError as e:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": str(e)}),
                headers=_json_headers()
            )
        except Exception as e:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"}),
                headers=_json_headers()
            )

        # Calculate min/max values (for Labour scores with WTD/MTD/YTD)
        # min_value, max_value = Q1Helpers.calculate_min_max(
        #     score_record, filter_type,
        #     date_ranges[0][0] if date_ranges else date.today(),
        #     date_ranges[0][1] if date_ranges else date.today()
        # )

        # Build overview list using computed method
        overview_list = []
        for start_date, end_date, period_label in date_ranges:
            # Use the existing computed method for ALL scores
            score_with_context = score_record.with_context(
                force_date_start=start_date,
                force_date_end=end_date
            )
            score_with_context._compute_context_total_score()
            actual_value = score_with_context.context_total_score

            # Round if it's a numeric value
            if isinstance(actual_value, (int, float)):
                actual_value = round(actual_value, 2)

            period_data = {
                "period": period_label,
                "start_date": start_date.strftime('%d-%m-%Y'),
                "end_date": end_date.strftime('%d-%m-%Y'),
                "actual_value": actual_value
            }

            if score_record.score_name == "Cashflow":
                breakdown = score_record.sudo().get_cashflow_breakdown(start_date, end_date)
                period_data["operating_cash"] = breakdown['operating_cash']
                period_data["financing_cash"] = breakdown['financing_cash']
                period_data["investment_cash"] = breakdown['investment_cash']

            # Add min/max for Labour scores with WTD/MTD/YTD
            # if min_value is not None and max_value is not None:
            if score_record.score_name == "Labour":
                if score_record.type == "percentage":
                    period_data["min_value"] = score_record.min_score_percentage or 0
                    period_data["max_value"] = score_record.max_score_percentage or 0
                else:
                    period_data["min_value"] = score_record.min_score_number or 0
                    period_data["max_value"] = score_record.max_score_number or 0

                    # period_data["min_value"] = min_value
                    # period_data["max_value"] = max_value


            if score_record.score_name == "TAT":
                if score_record.type == "percentage":
                    period_data["min_value"] = score_record.min_score_percentage
                    period_data["max_value"] = score_record.max_score_percentage
                else:
                    period_data["min_value"] = score_record.min_score_number
                    period_data["max_value"] = score_record.max_score_number

            # Special handling for Leads/Conversion - add quality_lead
            if score_record.score_name in ["Leads", "Conversion"]:
                lead_model = request.env['crm.lead'].sudo()
                # Leads: stage_id.sequence = 1, Conversion: stage_id.sequence = [1, 2]
                stage_sequence = 1 if score_record.score_name == "Leads" else [1, 2]

                quality_lead_count = lead_model.search_count([
                    ('lead_date', '>=', start_date),
                    ('lead_date', '<=', end_date),
                    ('stage_id.sequence', '=', stage_sequence),
                    ('company_id', '=', user.company_id.id)
                ])

                period_data["quality_lead"] = quality_lead_count if quality_lead_count else (
                    "0" if score_record.score_name == "Leads" else 0)
                period_data["min_value"] = "0" if score_record.score_name == "Leads" else ""
                period_data["max_value"] = "0" if score_record.score_name == "Leads" else ""

            if score_record.score_name == "Customer Retention":
                if score_record.type == "percentage":
                    period_data["min_value"] = score_record.min_score_percentage
                    period_data["max_value"] = score_record.max_score_percentage
                else:
                    period_data["min_value"] = score_record.min_score_number
                    period_data["max_value"] = score_record.max_score_number

            if score_record.score_name == "AOV":
                if score_record.type == "percentage":
                    period_data["min_value"] = score_record.min_score_percentage
                    period_data["max_value"] = score_record.max_score_percentage
                else:
                    period_data["min_value"] = score_record.min_score_number
                    period_data["max_value"] = score_record.max_score_number

            if score_record.score_name == "Income":
                if score_record.type == "percentage":
                    period_data["min_value"] = score_record.min_score_percentage
                    period_data["max_value"] = score_record.max_score_percentage
                else:
                    period_data["min_value"] = score_record.min_score_number
                    period_data["max_value"] = score_record.max_score_number

            overview_list.append(period_data)

        # If no results, try fallback
        if not overview_list:
            try:
                # Normalize filter_type for case-insensitive comparison
                normalized_filter_type = filter_type.upper() if filter_type else None
                score_data = request.env['bizdom.score'].sudo().get_score_dashboard_data(
                    score_id,
                    filter_type or 'MTD',
                    start_date_str if normalized_filter_type == 'CUSTOM' else None,
                    end_date_str if normalized_filter_type == 'CUSTOM' else None
                )
                if score_data and score_data.get('overview'):
                    overview_list = score_data['overview']
            except Exception as e:
                print(f"Error getting generic score data: {e}")

        response = {
            "statusCode": 200,
            "message": "Score Overview",
            "score_type": score_record.type or 'value',
            "score_id": score_id,
            "score_name": score_record.score_name,
            "overview": overview_list
        }

        return request.make_response(
            json.dumps(response),
            headers=_json_headers()
        )

    # Second Quadrant
    @http.route('/api/score/overview/department', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False,
                cors='*')
    def get_score_department_overview(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return request.make_response("", headers=_cors_headers())
        # Auth check - support both JWT token and session-based auth
        auth_header = request.httprequest.headers.get("Authorization")
        uid = False
        if auth_header:
            # External API call - require JWT token only (no session fallback)
            token = auth_header.split(" ")[1] if auth_header.startswith("Bearer ") else auth_header
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                uid = payload.get("uid")
                if isinstance(uid, dict):
                    uid = uid.get("uid")
            except jwt.ExpiredSignatureError:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Token expired"}),
                    headers=_json_headers()
                )
            except jwt.InvalidTokenError:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Invalid token"}),
                    headers=_json_headers()
                )
        else:
            # Internal dashboard call - allow session-based auth if same-origin
            # BUT exclude Swagger UI requests (which should use JWT)
            referer = request.httprequest.headers.get('Referer', '')
            origin = request.httprequest.headers.get('Origin', '')
            host = request.httprequest.headers.get('Host', '')

            # Check if request is from Swagger UI - if so, require JWT token
            is_from_swagger = False
            if referer and '/bizdom-api' in referer:
                is_from_swagger = True

            # If from Swagger, don't allow session fallback - require JWT
            if is_from_swagger:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Token missing"}),
                    headers=_json_headers()
                )

            # Check if request is from same origin (internal Odoo dashboard, not Swagger)
            is_same_origin = False
            if host:
                if referer and host in referer:
                    is_same_origin = True
                elif origin and (host in origin or origin.replace('http://', '').replace('https://', '') == host):
                    is_same_origin = True
                elif not referer and not origin:
                    # Same-origin requests might not send these headers
                    # Check if we have a valid session as additional validation
                    is_same_origin = True

            # Allow session auth only for same-origin requests (not from Swagger)
            if is_same_origin and request.session.uid:
                uid = request.session.uid
            else:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Token missing"}),
                    headers=_json_headers()
                )

        if not uid:
            return request.make_response(
                json.dumps({"statusCode": 401, "message": "Token missing"}),
                headers=_json_headers()
            )

        # Extract parameters
        score_id = int(kwargs.get('scoreId', 0))
        if not score_id:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": "scoreId is required"}),
                headers=_json_headers()
            )

        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists() or len(user) != 1:
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "User not found or multiple users"}),
                headers=_json_headers()
            )

        score_record = request.env['bizdom.score'].sudo().browse(score_id)
        if not score_record.exists():
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "Score record not found"}),
                headers=_json_headers()
            )

        # company = user.company_id
        is_owner = user.has_group('bizdom.group_bizdom_owner')
        allowed_pillar_ids = user.bizdom_allowed_pillar_ids.ids

        if not is_owner and score_record.pillar_id.id not in allowed_pillar_ids:
            return request.make_response(
                json.dumps({"statusCode": 403, "message": "score_id not allowed "}),
                headers=_json_headers()
            )


        filter_type = kwargs.get('filterType')
        start_date_str = kwargs.get('startDate')
        end_date_str = kwargs.get('endDate')

        # For Customer Retention score, always use MTD (monthly periods)
        # This matches the expected behavior for department-level Customer Retention

        # Get date ranges using Q1Helpers (reuse from Q1)
        try:
            date_ranges = Q1Helpers.get_date_ranges(filter_type, start_date_str, end_date_str)
        except ValueError as e:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": str(e)}),
                headers=_json_headers()
            )
        except Exception as e:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"}),
                headers=_json_headers()
            )

        # Get category records ONCE (fixes N+1 query problem)
        category_records = request.env['bizdom.category_lvl1'].sudo().search([
            ('score_id', '=', score_id),
            ('category_lvl1_selection', '!=', False)
        ])

        # Build overview list using batch computation
        overview_dept = []
        for start_date, end_date, period_label in date_ranges:
            # Compute scores for all departments in this date range
            dept_grouped = Q2Helpers.compute_department_scores(
                category_records, start_date, end_date, score_record, user, filter_type
            )

            # Calculate total actual value
            total_actual_value = round(sum(d.get('actual_value', 0) for d in dept_grouped), 2)

            period_data = {
                "start_date": start_date.strftime('%d-%m-%Y'),
                "end_date": end_date.strftime('%d-%m-%Y'),
                "max_value": "",
                "min_value": "",
                "total_actual_value": total_actual_value,
                "department": dept_grouped
            }

            overview_dept.append(period_data)

        response = {
            "statusCode": 200,
            "message": "Score Department Overview",
            "score_id": score_id,
            "score_name": score_record.score_name,
            "overview_department": overview_dept
        }

        return request.make_response(
            json.dumps(response),
            headers=_json_headers()
        )

    # Third Quadrant
    @http.route('/api/score/overview/employee', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False,
                cors='*')
    def get_score_employee_overview(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return request.make_response("", headers=_cors_headers())
        # Auth check - support both JWT token and session-based auth
        auth_header = request.httprequest.headers.get("Authorization")
        uid = False
        if auth_header:
            # External API call - require JWT token only (no session fallback)
            token = auth_header.split(" ")[1] if auth_header.startswith("Bearer ") else auth_header
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                uid = payload.get("uid")
                if isinstance(uid, dict):
                    uid = uid.get("uid")
            except jwt.ExpiredSignatureError:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Token expired"}),
                    headers=_cors_headers()
                )
            except jwt.InvalidTokenError:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Invalid token"}),
                    headers=_cors_headers()
                )
        else:
            # Internal dashboard call - allow session-based auth if same-origin
            # BUT exclude Swagger UI requests (which should use JWT)
            referer = request.httprequest.headers.get('Referer', '')
            origin = request.httprequest.headers.get('Origin', '')
            host = request.httprequest.headers.get('Host', '')

            # Check if request is from Swagger UI - if so, require JWT token
            is_from_swagger = False
            if referer and '/bizdom-api' in referer:
                is_from_swagger = True

            # If from Swagger, don't allow session fallback - require JWT
            if is_from_swagger:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Token missing"}),
                    headers=_cors_headers()
                )

            # Check if request is from same origin (internal Odoo dashboard, not Swagger)
            is_same_origin = False
            if host:
                if referer and host in referer:
                    is_same_origin = True
                elif origin and (host in origin or origin.replace('http://', '').replace('https://', '') == host):
                    is_same_origin = True
                elif not referer and not origin:
                    # Same-origin requests might not send these headers
                    # Check if we have a valid session as additional validation
                    is_same_origin = True

            # Allow session auth only for same-origin requests (not from Swagger)
            # With auth='none', request.session.uid should still be available if session cookie exists
            if is_same_origin and request.session.uid:
                uid = request.session.uid
            else:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Token missing"}),
                    headers=_cors_headers()
                )
        if not uid:
            return request.make_response(
                json.dumps({"statusCode": 401, "message": "Authentication required"}),
                headers=_cors_headers()
            )

        # With auth='none', we need to explicitly set the user on the environment
        # This ensures request.env.user is available for access rights checks
        request.update_env(user=uid)

        # Extract parameters
        score_id = int(kwargs.get('scoreId', 0))
        dept_id = int(kwargs.get('departmentId', 0))

        if not score_id or not dept_id:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": "scoreId and departmentId are required"}),
                headers=_cors_headers()
            )

        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists() or len(user) != 1:
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "User not found or multiple users"}),
                headers=_cors_headers()
            )

        score_record = request.env['bizdom.score'].sudo().browse(score_id)
        if not score_record.exists():
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "Score record not found"}),
                headers=_cors_headers()
            )

        filter_type = kwargs.get('filterType')
        start_date_str = kwargs.get('startDate')
        end_date_str = kwargs.get('endDate')

        is_owner = user.has_group('bizdom.group_bizdom_owner')
        allowed_pillar_ids = user.bizdom_allowed_pillar_ids.ids

        if not is_owner and score_record.pillar_id.id not in allowed_pillar_ids:
            return request.make_response(
                json.dumps({"statusCode": 403, "message": "score_id not allowed "}),
                headers=_json_headers()
            )

        # Get date ranges using Q1Helpers (reuse from Q1)
        try:
            date_ranges = Q1Helpers.get_date_ranges(filter_type, start_date_str, end_date_str)
        except ValueError as e:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": str(e)}),
                headers=_cors_headers()
            )
        except Exception as e:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"}),
                headers=_cors_headers()
            )

        # Get department name for response
        dept = request.env['hr.department'].sudo().browse(dept_id)
        if not dept.exists():
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "Department not found"}),
                headers=_cors_headers()
            )

        # Special handling for Customer Retention score
        if score_record.score_name == "Customer Retention":
            overview_employee = []

            # Get all questions for this department from category_lvl2 records
            category_lvl2_records = request.env['bizdom.category_lvl2'].sudo().search([
                ('score_id', '=', score_id),
                ('category_lvl2_selection', '!=', False),
                ('department_id', '=', dept_id)
            ])

            # Extract unique questions
            questions_map = {}
            for cat_rec in category_lvl2_records:
                if cat_rec.category_lvl2_selection and cat_rec.category_lvl2_selection._name == 'fleet.feedback.question':
                    question = cat_rec.category_lvl2_selection
                    if question.id not in questions_map:
                        questions_map[question.id] = {
                            'question_id': question.id,
                            'question': question.name or ''
                        }

            # Convert to list sorted by question_id
            all_questions = sorted(questions_map.values(), key=lambda x: x['question_id'])

            # Process each period
            for start_date, end_date, period_label in date_ranges:
                questions_data = []
                total_actual_value = 0

                for question_info in all_questions:
                    question_id = question_info['question_id']

                    # Get feedback lines for this question in this period
                    feedback_lines = request.env['fleet.feedback.line'].sudo().search([
                        ('feedback_date', '>=', start_date),
                        ('feedback_date', '<=', end_date),
                        ('question_id', '=', question_id),
                        ('rating', '!=', False),
                        ('feedback_id.department_ids', 'in', [dept_id])
                    ])

                    # Calculate average rating for this question
                    if feedback_lines:
                        ratings = [int(r.rating) for r in feedback_lines if r.rating]
                        if ratings:
                            avg_rating = sum(ratings) / len(ratings)
                            actual_value = round(avg_rating, 3)
                            total_actual_value += actual_value
                        else:
                            actual_value = ""
                    else:
                        actual_value = ""

                    questions_data.append({
                        'question_id': question_id,
                        'question': question_info['question'],
                        'actual_value': actual_value,
                        'min_value': "",
                        'max_value': ""
                    })

                period_data = {
                    "start_date": start_date.strftime('%d-%m-%Y'),
                    "end_date": end_date.strftime('%d-%m-%Y'),
                    "max_value": "",
                    "min_value": "",
                    "total_actual_value": round(total_actual_value, 2) if total_actual_value > 0 else 0,
                    "questions": questions_data
                }

                overview_employee.append(period_data)

            response = {
                "statusCode": 200,
                "message": "Employee Overview",
                "score_id": score_id,
                "score_name": score_record.score_name,
                "department_id": dept.id,
                "department_name": dept.name,
                "overview_employee": overview_employee
            }

            return request.make_response(
                json.dumps(response),
                headers=[('Content-Type', 'application/json')]
            )

        # Get category_lvl2 records ONCE (fixes N+1 query problem)
        category_lvl2_records = request.env['bizdom.category_lvl2'].sudo().search([
            ('score_id', '=', score_id),
            ('category_lvl2_selection', '!=', False)
        ])

        # Get department/medium name for response
        if score_record.score_name in ["Leads", "Conversion"]:
            dept = request.env['utm.medium'].sudo().browse(dept_id)
        else:
            dept = request.env['hr.department'].sudo().browse(dept_id)

        if not dept.exists():
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "Department/Medium not found"}),
                headers=_cors_headers()
            )

        # Build overview list using batch computation
        overview_employee = []
        for start_date, end_date, period_label in date_ranges:
            # Compute scores for all employees/sources in this date range
            emp_grouped = Q3Helpers.compute_employee_scores(
                category_lvl2_records, start_date, end_date, score_record, user, dept_id, filter_type
            )
            period_min_value = ""
            period_max_value = ""
            if score_record.score_name == "Labour" and filter_type in ["WTD", "MTD", "YTD", "CUSTOM"]:
                min_value, max_value = Q1Helpers.calculate_min_max(
                    score_record, filter_type, start_date, end_date
                )
                period_min_value = min_value if min_value is not None else ""
                period_max_value = max_value if max_value is not None else ""

            # Calculate total actual value
            total_actual_value = round(sum(e.get('actual_value', 0) for e in emp_grouped), 2)

            # For TAT score, use the score record's context_total_score instead
            if score_record.score_name == "TAT":
                tat_score = score_record.with_context(
                    force_date_start=start_date,
                    force_date_end=end_date
                )
                tat_score._compute_context_total_score()
                total_actual_value = round(tat_score.context_total_score, 2)

            # For Leads/Conversion, calculate quality_lead and total_lead
            if score_record.score_name == "Leads":
                # For Leads, calculate totals from emp_grouped (which contains sources)
                total_lead = sum(e.get('actual_value', 0) for e in emp_grouped)
                total_quality_lead = sum(e.get('quality_lead_value', 0) for e in emp_grouped)

                period_data = {
                    "start_date": start_date.strftime('%d-%m-%Y'),
                    "end_date": end_date.strftime('%d-%m-%Y'),
                    "max_value": "",
                    "min_value": "",
                    "total_quality_lead_value": total_quality_lead,
                    "total_lead_value": total_lead,
                    "sources": emp_grouped
                }
            elif score_record.score_name == "Conversion":
                # For Conversion, calculate totals from emp_grouped (which contains salespersons)
                total_converted = sum(e.get('converted_value', 0) for e in emp_grouped)
                total_quality_lead = sum(e.get('quality_lead_value', 0) for e in emp_grouped)

                period_data = {
                    "start_date": start_date.strftime('%d-%m-%Y'),
                    "end_date": end_date.strftime('%d-%m-%Y'),
                    "max_value": "",
                    "min_value": "",
                    "total_quality_lead_value": total_quality_lead,
                    "total_actual_value": total_converted,
                    "sources": emp_grouped
                }
            elif score_record.score_name == "Income":
                period_data = {
                    "start_date": start_date.strftime('%d-%m-%Y'),
                    "end_date": end_date.strftime('%d-%m-%Y'),
                    "max_value": "",
                    "min_value": "",
                    "total_actual_value": total_actual_value,
                    "categories": emp_grouped
                }
            elif score_record.score_name == "Expense":
                period_data = {
                    "start_date": start_date.strftime('%d-%m-%Y'),
                    "end_date": end_date.strftime('%d-%m-%Y'),
                    "max_value": "",
                    "min_value": "",
                    "total_actual_value": total_actual_value,
                    "categories": emp_grouped
                }

            else:
                period_data = {
                    "start_date": start_date.strftime('%d-%m-%Y'),
                    "end_date": end_date.strftime('%d-%m-%Y'),
                    "max_value": period_max_value,
                    "min_value": period_min_value,
                    "total_actual_value": total_actual_value,
                    "employees": emp_grouped
                }

            overview_employee.append(period_data)

        # Determine response field name based on score type
        if score_record.score_name in ["Leads", "Conversion"]:
            response_field = "overview_source"
            response_message = "Source Overview"

        elif score_record.score_name == "Income":
            response_field = "overview_category"
            response_message = "Category Overview"

        elif score_record.score_name == "Expense":
            response_field = "overview_category"
            response_message = "Category Overview"

        else:
            response_field = "overview_employee"
            response_message = "Employee Overview"

        response = {
            "statusCode": 200,
            "message": response_message,
            "score_id": score_id,
            "score_name": score_record.score_name,
            "department_id": dept.id,
            "department_name": dept.name,
        }
        response[response_field] = overview_employee

        return request.make_response(
            json.dumps(response),
            headers=[('Content-Type', 'application/json')]
        )
