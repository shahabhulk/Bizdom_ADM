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


class BizdomQuadrant(http.Controller):

    # Overeview of a score for the past three months

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
            token = auth_header.split(" ")[1] if auth_header.startswith("Bearer ") else auth_header
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                uid = payload.get("uid")
                if isinstance(uid, dict):
                    uid = uid.get("uid")
            except jwt.ExpiredSignatureError:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Token expired"}),
                    headers=[('Content-Type', 'application/json')]
                )
            except jwt.InvalidTokenError:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Invalid token"}),
                    headers=[('Content-Type', 'application/json')]
                )
        else:
            # Fallback to session-based auth for internal dashboard
            uid = request.session.uid
        
        if not uid:
            return request.make_response(
                json.dumps({"statusCode": 401, "message": "Token missing"}),
                headers=[('Content-Type', 'application/json')]
            )

        # Extract parameters
        score_id = int(kwargs.get('scoreId', 0))
        if not score_id:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": "scoreId is required"}),
                headers=[('Content-Type', 'application/json')]
            )

        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists() or len(user) != 1:
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "User not found or multiple users"}),
                headers=[('Content-Type', 'application/json')]
            )

        score_record = request.env['bizdom.score'].sudo().browse(score_id)
        if not score_record.exists():
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "Score record not found"}),
                headers=[('Content-Type', 'application/json')]
            )

        filter_type = kwargs.get('filterType')
        start_date_str = kwargs.get('startDate')
        end_date_str = kwargs.get('endDate')

        # Get date ranges using utility
        try:
            date_ranges = Q1Helpers.get_date_ranges(filter_type, start_date_str, end_date_str)
        except ValueError as e:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": str(e)}),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"}),
                headers=[('Content-Type', 'application/json')]
            )

        # Calculate min/max values (for Labour scores with WTD/MTD/YTD)
        min_value, max_value = Q1Helpers.calculate_min_max(
            score_record, filter_type,
            date_ranges[0][0] if date_ranges else date.today(),
            date_ranges[0][1] if date_ranges else date.today()
        )

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

            # Add min/max for Labour scores with WTD/MTD/YTD
            if min_value is not None and max_value is not None:
                if score_record.score_name == "Labour":
                    period_data["min_value"] = min_value
                    period_data["max_value"] = max_value

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
                
                period_data["quality_lead"] = quality_lead_count if quality_lead_count else ("0" if score_record.score_name == "Leads" else 0)
                period_data["min_value"] = "0" if score_record.score_name == "Leads" else ""
                period_data["max_value"] = "0" if score_record.score_name == "Leads" else ""

            overview_list.append(period_data)

        # If no results, try fallback
        if not overview_list:
            try:
                score_data = request.env['bizdom.score'].sudo().get_score_dashboard_data(
                    score_id,
                    filter_type or 'MTD',
                    start_date_str if filter_type == 'Custom' else None,
                    end_date_str if filter_type == 'Custom' else None
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
            headers=[
                ('Content-Type', 'application/json'),
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
            ]
        )

    # Second Quadrant
    @http.route('/api/score/overview/department', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def get_score_department_overview(self, **kwargs):
        # Auth check - support both JWT token and session-based auth
        auth_header = request.httprequest.headers.get("Authorization")
        uid = False
        if auth_header:
            token = auth_header.split(" ")[1] if auth_header.startswith("Bearer ") else auth_header
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                uid = payload.get("uid")
                if isinstance(uid, dict):
                    uid = uid.get("uid")
            except jwt.ExpiredSignatureError:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Token expired"}),
                    headers=[('Content-Type', 'application/json')]
                )
            except jwt.InvalidTokenError:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Invalid token"}),
                    headers=[('Content-Type', 'application/json')]
                )
        else:
            # Fallback to session-based auth for internal dashboard
            uid = request.session.uid
        
        if not uid:
            return request.make_response(
                json.dumps({"statusCode": 401, "message": "Token missing"}),
                headers=[('Content-Type', 'application/json')]
            )

        # Extract parameters
        score_id = int(kwargs.get('scoreId', 0))
        if not score_id:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": "scoreId is required"}),
                headers=[('Content-Type', 'application/json')]
            )

        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists() or len(user) != 1:
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "User not found or multiple users"}),
                headers=[('Content-Type', 'application/json')]
            )

        score_record = request.env['bizdom.score'].sudo().browse(score_id)
        if not score_record.exists():
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "Score record not found"}),
                headers=[('Content-Type', 'application/json')]
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
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"}),
                headers=[('Content-Type', 'application/json')]
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
            headers=[
                ('Content-Type', 'application/json'),
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
            ]
        )

    # Third Quadrant
    @http.route('/api/score/overview/employee', type='http', auth='user', methods=['GET'], csrf=False, cors='*')
    def get_score_employee_overview(self, **kwargs):
        # Auth check - support both JWT token and session-based auth
        auth_header = request.httprequest.headers.get("Authorization")
        uid = False
        if auth_header:
            token = auth_header.split(" ")[1] if auth_header.startswith("Bearer ") else auth_header
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                uid = payload.get("uid")
                if isinstance(uid, dict):
                    uid = uid.get("uid")
            except jwt.ExpiredSignatureError:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Token expired"}),
                    headers=[('Content-Type', 'application/json')]
                )
            except jwt.InvalidTokenError:
                return request.make_response(
                    json.dumps({"statusCode": 401, "message": "Invalid token"}),
                    headers=[('Content-Type', 'application/json')]
                )
        else:
            # Fallback to session-based auth for internal dashboard
            uid = request.session.uid if hasattr(request, 'session') and request.session.uid else None
        
        if not uid:
            return request.make_response(
                json.dumps({"statusCode": 401, "message": "Authentication required"}),
                headers=[('Content-Type', 'application/json')]
            )

        # Extract parameters
        score_id = int(kwargs.get('scoreId', 0))
        dept_id = int(kwargs.get('departmentId', 0))
        
        if not score_id or not dept_id:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": "scoreId and departmentId are required"}),
                headers=[('Content-Type', 'application/json')]
            )

        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists() or len(user) != 1:
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "User not found or multiple users"}),
                headers=[('Content-Type', 'application/json')]
            )

        score_record = request.env['bizdom.score'].sudo().browse(score_id)
        if not score_record.exists():
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "Score record not found"}),
                headers=[('Content-Type', 'application/json')]
            )

        filter_type = kwargs.get('filterType')
        start_date_str = kwargs.get('startDate')
        end_date_str = kwargs.get('endDate')

        # Get date ranges using Q1Helpers (reuse from Q1)
        try:
            date_ranges = Q1Helpers.get_date_ranges(filter_type, start_date_str, end_date_str)
        except ValueError as e:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": str(e)}),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"}),
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
                headers=[('Content-Type', 'application/json')]
            )

        # Build overview list using batch computation
        overview_employee = []
        for start_date, end_date, period_label in date_ranges:
            # Compute scores for all employees/sources in this date range
            emp_grouped = Q3Helpers.compute_employee_scores(
                category_lvl2_records, start_date, end_date, score_record, user, dept_id, filter_type
            )
            
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
            else:
                period_data = {
                    "start_date": start_date.strftime('%d-%m-%Y'),
                    "end_date": end_date.strftime('%d-%m-%Y'),
                    "max_value": "",
                    "min_value": "",
                    "total_actual_value": total_actual_value,
                    "employees": emp_grouped
                }
            
            overview_employee.append(period_data)
        
        # Determine response field name based on score type
        if score_record.score_name in ["Leads", "Conversion"]:
            response_field = "overview_source"
            response_message = "Source Overview"
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
            headers=[
                ('Content-Type', 'application/json'),
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
            ]
        )
