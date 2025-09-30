import calendar
import json
from datetime import date, datetime
from odoo import http
from odoo.http import request
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import jwt

SECRET_KEY = "Your-secret-key"


class BizdomQuadrant(http.Controller):

    # Overeview of a score for the past three months

    # First Quadrant
    @http.route('/api/score/overview', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_score_overview(self, **kwargs):
        global min_value, max_value
        if request.httprequest.method == 'OPTIONS':
            return request.make_response(
                "",
                headers=[
                    ('Access-Control-Allow-Origin', 'http://localhost:3000'),
                    ('Access-Control-Allow-Methods', 'POST, OPTIONS'),
                    ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
                ]
            )

        auth_header = request.httprequest.headers.get("Authorization")
        if not auth_header:
            return json.dumps({"statusCode": 401, "message": "Token missing"})

        token = auth_header.split(" ")[1] if auth_header.startswith("Bearer ") else auth_header

        try:
            body = json.loads(request.httprequest.data.decode("utf-8"))
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            uid = payload.get("uid")
            if isinstance(uid, dict):
                uid = uid.get("uid")
        except jwt.ExpiredSignatureError:
            return json.dumps({"statusCode": 401, "message": "Token expired"})
        except jwt.InvalidTokenError:
            return json.dumps({"statusCode": 401, "message": "Invalid token"})

        score_id = int(body.get("scoreId"))
        print(score_id)
        if not score_id:
            return json.dumps({"statusCode": 400, "message": "scoreId is required"})

        uid = payload.get("uid")
        if isinstance(uid, dict):
            uid = uid.get("uid")

        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists() or len(user) != 1:
            return json.dumps({"statusCode": 404, "message": "User not found or multiple users"})

        # Now safe to use user.name
        print("Logged in user:", user.name)

        start_date_str = body.get("startDate")
        end_date_str = body.get("endDate")
        filter_type = body.get("filterType")

        today = date.today()
        overview_list = []
        score_record = request.env['bizdom.score'].sudo().browse(score_id)
        if score_record.score_name == "Labour":
            if filter_type == "Custom" and start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
                    end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()

                    if start_date > end_date:
                        return json.dumps({"statusCode": 400, "message": "Start date should be less than end date"})

                    delta = relativedelta(end_date, start_date)
                    print(delta)
                    total_months = delta.years * 12 + delta.months

                    if total_months > 3:
                        # For date ranges > 3 months, show yearly segments
                        current_year = start_date.year
                        end_year = end_date.year

                        for year in range(3):  # Last 3 years
                            year_start = date(current_year - year, start_date.month, start_date.day)
                            year_end = date(end_year - year, end_date.month, end_date.day)

                            records = request.env['labour.billing'].sudo().search([
                                ('date', '>=', year_start),
                                ('date', '<=', year_end)
                            ])

                            actual_value = round(sum(records.mapped('charge_amount') or [0]), 2)
                            overview_list.append({
                                "start_date": year_start.strftime('%d-%m-%Y'),
                                "end_date": year_end.strftime('%d-%m-%Y'),
                                "actual_value": actual_value
                            })
                    else:
                        # For date ranges ≤ 3 months, show 3 periods going backwards
                        duration = end_date - start_date
                        for i in range(3):
                            period_end = end_date - (duration * i)
                            period_start = period_end - duration

                            # For the last period, don't go before the start date
                            period_start = max(period_start, date(2000, 1, 1))  # Arbitrary early date

                            records = request.env['labour.billing'].sudo().search([
                                ('date', '>=', period_start),
                                ('date', '<=', period_end)
                            ])

                            actual_value = sum(records.mapped('charge_amount') or [0], 2)
                            overview_list.append({
                                "start_date": period_start.strftime('%d-%m-%Y'),
                                "end_date": period_end.strftime('%d-%m-%Y'),
                                "actual_value": actual_value
                            })

                except ValueError:
                    return json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"})
            elif filter_type == "WTD":
                current_week_start = today - timedelta(days=today.weekday())
                current_week_end = today

                # Past 2 weeks (capped to weekday like current week)
                for i in range(2, 0, -1):
                    month_start = (today.replace(day=1) - relativedelta(months=i))
                    year = month_start.year
                    month = month_start.month
                    days_in_month = calendar.monthrange(year, month)[1]
                    week_start = current_week_start - timedelta(weeks=i)
                    week_end = week_start + timedelta(days=today.weekday())  # cap to same weekday

                    records = request.env['labour.billing'].sudo().search([
                        ('date', '>=', week_start),
                        ('date', '<=', week_end)
                    ])

                    actual_value = sum(records.mapped('charge_amount') or [0])
                    min_value, max_value = 0, 0

                    # If score type defined, calculate min/max per day
                    if score_record.type == "percentage":
                        min_value = score_record.min_score_percentage / days_in_month
                        max_value = score_record.max_score_percentage / days_in_month
                    elif score_record.type == "value":
                        min_value = score_record.min_score_number / days_in_month
                        max_value = score_record.max_score_number / days_in_month

                    overview_list.append({
                        "period": f"{week_start.strftime('%d-%m-%Y')} to {week_end.strftime('%d-%m-%Y')}",
                        "actual_value": actual_value,
                        "min_value": round(min_value * (today.weekday() + 1), 2),
                        "max_value": round(max_value * (today.weekday() + 1), 2),
                    })
                    print("qweekklkj", today.weekday() + 1)

                    # --- Department wise grouping ---
                    dept_grouped = []
                    overview_dept = []
                    departments = records.mapped('department_id')
                    for dept in departments:
                        dept_records = records.filtered(lambda r: r.department_id == dept)
                        dept_actual_value = sum(dept_records.mapped('charge_amount') or [0])

                        score_line = score_record.score_line_ids.filtered(lambda l: l.department_id.id == dept.id)
                        min_dep_value = score_line.min_dep_score / days_in_month if score_line else 0
                        max_dep_value = score_line.max_dep_score / days_in_month if score_line else 0
                        print("min_dep_score", score_line.min_dep_score)

                        dept_grouped.append({
                            "department_id": dept.id,
                            "department_name": dept.name,
                            "actual_value": dept_actual_value,
                            "min_value": round(min_dep_value * (today.weekday() + 1), 2),
                            "max_value": round(max_dep_value * (today.weekday() + 1), 2),
                        })

                    overview_dept.append({
                        "period": f"{week_start.strftime('%d-%m-%Y')} to {week_end.strftime('%d-%m-%Y')}",
                        "department": dept_grouped
                    })

                # --- Current week till today ---
                records = request.env['labour.billing'].sudo().search([
                    ('date', '>=', current_week_start),
                    ('date', '<=', current_week_end)
                ])
                actual_value = sum(records.mapped('charge_amount') or [0])
                min_value, max_value = 0, 0

                if score_record.type == "percentage":
                    min_value = score_record.min_score_percentage / days_in_month
                    max_value = score_record.max_score_percentage / days_in_month
                elif score_record.type == "value":
                    min_value = score_record.min_score_number / days_in_month
                    max_value = score_record.max_score_number / days_in_month

                overview_list.append({
                    "start_date": f"{current_week_start.strftime('%d-%m-%Y')}",
                    "end_date": f"{current_week_end.strftime('%d-%m-%Y')}",
                    "min_value": round(min_value * (today.weekday() + 1), 2),
                    "max_value": round(max_value * (today.weekday() + 1), 2),
                    "actual_value": actual_value
                })

                # --- Department wise grouping (current week) ---
                dept_grouped = []
                overview_dept = []
                departments = records.mapped('department_id')
                for dept in departments:
                    dept_records = records.filtered(lambda r: r.department_id == dept)
                    dept_actual_value = sum(dept_records.mapped('charge_amount') or [0])

                    score_line = score_record.score_line_ids.filtered(lambda l: l.department_id.id == dept.id)
                    min_dep_value = score_line.min_dep_score / days_in_month if score_line else 0
                    max_dep_value = score_line.max_dep_score / days_in_month if score_line else 0
                    print("dsafasd", min_dep_value, max_dep_value)

                    dept_grouped.append({
                        "department_id": dept.id,
                        "department_name": dept.name,
                        "actual_value": dept_actual_value,
                        "min_value": round(min_dep_value * (today.weekday() + 1), 2),
                        "max_value": round(max_dep_value * (today.weekday() + 1), 2),
                    })

                overview_dept.append({
                    "period": f"{current_week_start.strftime('%d-%m-%Y')} to {current_week_end.strftime('%d-%m-%Y')}",
                    "department": dept_grouped
                })

            elif filter_type == "MTD" or not filter_type:
                for i in range(2, -1, -1):  # 2 months ago, 1 month ago, current month
                    month_start = (today.replace(day=1) - relativedelta(months=i))
                    year = month_start.year
                    month = month_start.month
                    days_in_month = calendar.monthrange(year, month)[1]
                    month_end_day = min(today.day, (month_start + relativedelta(months=1) - timedelta(days=1)).day)
                    print("last day", month_end_day)
                    month_end = month_start.replace(day=month_end_day)

                    # Fetch scores fully contained inside the month
                    records = request.env['labour.billing'].sudo().search([
                        ('date', '>=', month_start),
                        ('date', '<=', month_end)
                    ])
                    print("month start", month_start)
                    print("month end", month_end)

                    actual_value = sum(records.mapped('charge_amount') or [0])
                    min_value, max_value = 0, 0
                    # Prepare adaptive response
                    if score_record.type == "percentage":
                        min_value = (score_record.min_score_percentage) / days_in_month
                        max_value = (score_record.max_score_percentage) / days_in_month
                    elif score_record.type == "value":
                        min_value = (score_record.min_score_number) / days_in_month
                        max_value = (score_record.max_score_number) / days_in_month

                    overview_list.append({
                        "month": month_start.strftime("%B %Y"),
                        "start_date": f"{month_start.strftime('%d-%m-%Y')}",
                        "end_date": f"{month_end.strftime('%d-%m-%Y')}",
                        "max_value": round(max_value * month_end_day, 2),
                        "min_value": round(min_value * month_end_day, 2),
                        "actual_value": actual_value
                    })


            elif filter_type == "YTD":
                for year_diff in range(0, 3):
                    start_date = date(today.year - year_diff, 1, 1)
                    end_date = date(today.year - year_diff, today.month, today.day)

                    records = request.env['labour.billing'].sudo().search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date)
                    ])
                    actual_value = sum(records.mapped('charge_amount') or [0])

                    # total days elapsed in year up to end_date:
                    # sum days of months 1..(end_month-1) + current day
                    total_days_elapsed = sum(
                        calendar.monthrange(end_date.year, m)[1] for m in range(1, end_date.month)
                    ) + end_date.day

                    # scale factor: how many 30-day periods have elapsed
                    days_multiplier = total_days_elapsed / 30.0

                    # monthly base values depending on score type
                    monthly_min_base = 0
                    monthly_max_base = 0
                    if score_record.type == "percentage":
                        monthly_min_base = score_record.min_score_percentage or 0
                        monthly_max_base = score_record.max_score_percentage or 0
                    elif score_record.type == "value":
                        monthly_min_base = score_record.min_score_number or 0
                        monthly_max_base = score_record.max_score_number or 0

                    min_value = round(monthly_min_base * days_multiplier, 2)
                    max_value = round(monthly_max_base * days_multiplier, 2)

                    overview_list.append({
                        "year": f"{start_date.year}",
                        "start_date": f"{start_date.strftime('%d-%m-%Y')}",
                        "end_date": f"{end_date.strftime('%d-%m-%Y')}",
                        "min_value": min_value,
                        "max_value": max_value,
                        "actual_value": actual_value
                    })

        response = {
            "statusCode": 200,
            "message": "Score Overview",
            "score_id": score_id,
            "score_name": score_record.score_name,
            "overview": overview_list
        }
        print("response", response)

        return request.make_response(
            json.dumps(response),
            headers=[
                ('Content-Type', 'application/json'),
                ('Access-Control-Allow-Origin', 'http://localhost:3000'),
                ('Access-Control-Allow-Methods', 'POST, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
            ]
        )

    # Second Quadrant
    @http.route('/api/score/overview/department', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def get_score_department_overview(self, **kwargs):
        auth_header = request.httprequest.headers.get("Authorization")
        if not auth_header:
            return request.make_response(
                json.dumps({"statusCode": 401, "message": "Token missing"}),
                headers=[('Content-Type', 'application/json')]
            )

        token = auth_header.split(" ")[1] if auth_header.startswith("Bearer ") else auth_header

        try:
            body = json.loads(request.httprequest.data.decode("utf-8"))
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            uid = payload.get("uid")
            if isinstance(uid, dict):
                uid = uid.get("uid")
        except jwt.ExpiredSignatureError:
            return request.make_response(
                json.dumps({"statusCode": 401, "message": "Token expired"})
            )
        except jwt.InvalidTokenError:
            return request.make_response(
                json.dumps({"statusCode": 401, "message": "Invalid token"})
            )
        score_id = int(body.get("scoreId"))
        if not score_id:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": "scoreId is required"}),
            )
        score_id = int(score_id)
        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists() or len(user) != 1:
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "User not found or multiple users"})

            )

        print("Logged in user:", user.name)

        start_date_str = body.get("startDate")
        end_date_str = body.get("endDate")
        filter_type = body.get("filterType")

        score_record = request.env['bizdom.score'].sudo().browse(score_id)

        if not score_record.exists():
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "Score record not found"}),
            )

        overview_dept = []
        today = datetime.today()
        score_record = request.env['bizdom.score'].sudo().browse(score_id)
        if score_record.score_name == "Labour":
            if filter_type == "Custom" and start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
                    end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()

                    if start_date > end_date:
                        return json.dumps({"statusCode": 400, "message": "Start date should be less than end date"})

                    delta = relativedelta(end_date, start_date)
                    total_months = delta.years * 12 + delta.months

                    # helper to safely build a date (clamp day to valid days in month
                    if total_months > 3:
                        start_year = start_date.year
                        end_year = end_date.year

                        for year in range(3):
                            year_start = date(start_year - year, start_date.month, start_date.day)
                            year_end = date(end_year - year, end_date.month, end_date.day)

                            records = request.env['labour.billing'].sudo().search([('date', '>=', year_start),
                                                                                   ('date', '<=', year_end)])
                            dept_grouped = []
                            departments = records.mapped('department_id')
                            for dept in departments:
                                dept_records = records.filtered(lambda r: r.department_id == dept)
                                dept_actual_value = sum(dept_records.mapped('charge_amount') or [0])
                                score_line = score_record.score_line_ids.filtered(
                                    lambda l: l.department_id.id == dept.id)
                                min_dep_value = (score_line.min_dep_score) / 30 if score_line else 0
                                max_dep_value = (score_line.max_dep_score) / 30 if score_line else 0
                                dept_score_value = (dept_actual_value / max_dep_value) * 100 if max_dep_value > 0 else 0
                                dept_grouped.append({
                                    'department_id': dept.id,
                                    'department_name': dept.name,
                                    'max_value': round(max_dep_value, 2),
                                    'min_value': round(min_dep_value, 2),
                                    'actual_value': dept_actual_value})
                            overview_dept.append({
                                "start_date": year_start.strftime("%d-%m-%Y"),
                                "end_date": year_end.strftime("%d-%m-%Y"),
                                "total_actual_value": round(sum(d['actual_value'] for d in dept_grouped), 2),
                                "department": dept_grouped

                            })




                    else:
                        duration = end_date - start_date

                        for i in range(3):
                            period_end = end_date - (duration * i)
                            period_start = period_end - duration

                            # For the last period, don't go before the start date
                            period_start = max(period_start, date(2000, 1, 1))  # Arbitrary early date

                            records = request.env['labour.billing'].sudo().search([
                                ('date', '>=', period_start),
                                ('date', '<=', period_end)
                            ])

                            dept_grouped = []
                            departments = records.mapped('department_id')
                            for dept in departments:
                                dept_records = records.filtered(lambda r: r.department_id == dept)
                                dept_actual_value = sum(dept_records.mapped('charge_amount') or [0])
                                score_line = score_record.score_line_ids.filtered(
                                    lambda l: l.department_id.id == dept.id)
                                min_dep_value = (score_line.min_dep_score) / 30 if score_line else 0
                                max_dep_value = (score_line.max_dep_score) / 30 if score_line else 0
                                dept_score_value = (dept_actual_value / max_dep_value) * 100 if max_dep_value > 0 else 0
                                dept_grouped.append({
                                    'department_id': dept.id,
                                    'department_name': dept.name,
                                    'max_value': round(max_dep_value, 2),
                                    'min_value': round(min_dep_value, 2),
                                    'actual_value': dept_actual_value,
                                })
                            overview_dept.append({
                                "start_date": period_start.strftime("%d-%m-%Y"),
                                "end_date": period_end.strftime("%d-%m-%Y"),
                                "total_actual_value": round(sum(d['actual_value'] for d in dept_grouped), 2),
                                "department": dept_grouped

                            })
                except ValueError:
                    return request.make_response(
                        json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"}),
                        headers=[('Content-Type', 'application/json')]
                    )

            elif filter_type == "MTD" or not filter_type:
                for i in range(2, -1, -1):
                    month_start = (today.replace(day=1) - relativedelta(months=i))
                    year = month_start.year
                    month = month_start.month
                    days_in_month = calendar.monthrange(year, month)[1]
                    month_end_day = min(today.day, (month_start + relativedelta(months=1) - timedelta(days=1)).day)
                    month_end = month_start.replace(day=month_end_day)

                    records = request.env['labour.billing'].sudo().search([
                        ('date', '>=', month_start),
                        ('date', '<=', month_end)
                    ])

                    dept_grouped = []
                    departments = records.mapped('department_id')

                    for dept in departments:
                        dept_records = records.filtered(lambda r: r.department_id == dept)
                        dept_actual_value = sum(dept_records.mapped('charge_amount') or [0])

                        score_line = score_record.score_line_ids.filtered(lambda l: l.department_id.id == dept.id)
                        min_dep_value = (score_line.min_dep_score) / days_in_month if score_line else 0
                        max_dep_value = (score_line.max_dep_score) / days_in_month if score_line else 0

                        dept_grouped.append({
                            "department_id": dept.id,
                            "department_name": dept.name,
                            "max_value": round(max_dep_value * month_end_day, 2),
                            "min_value": round(min_dep_value * month_end_day, 2),
                            "actual_value": dept_actual_value
                        })
                    overview_dept.append({
                        "month": month_start.strftime("%B %Y"),
                        "start_date": month_start.strftime("%d-%m-%Y"),
                        "end_date": month_end.strftime("%d-%m-%Y"),
                        "total_actual_value": sum(d['actual_value'] for d in dept_grouped),
                        "department": dept_grouped
                    })

            elif filter_type == "WTD":
                # Current week
                current_week_start = today - timedelta(days=today.weekday())
                current_week_end = today

                # Past 2 weeks + current week
                for i in range(2, 0, -1):
                    week_start = current_week_start - timedelta(weeks=i)
                    week_end = week_start + timedelta(days=today.weekday())  # cap to same weekday
                    records = request.env['labour.billing'].sudo().search([
                        ('date', '>=', week_start),
                        ('date', '<=', week_end)
                    ])

                    dept_grouped = []
                    departments = records.mapped('department_id')
                    # Use month of the week_start to get days_in_month for per-day base scaling
                    wk_year = week_start.year
                    wk_month = week_start.month
                    days_in_month = calendar.monthrange(wk_year, wk_month)[1]
                    days_count = (week_end - week_start).days + 1

                    for dept in departments:
                        dept_records = records.filtered(lambda r: r.department_id == dept)
                        dept_actual_value = sum(dept_records.mapped('charge_amount') or [0])

                        score_line = score_record.score_line_ids.filtered(lambda l: l.department_id.id == dept.id)
                        min_dep_per_day = (score_line.min_dep_score) / days_in_month if score_line else 0
                        max_dep_per_day = (score_line.max_dep_score) / days_in_month if score_line else 0

                        dept_grouped.append({
                            "department_id": dept.id,
                            "department_name": dept.name,
                            "min_value": round(min_dep_per_day * days_count, 2),
                            "max_value": round(max_dep_per_day * days_count, 2),
                            "actual_value": dept_actual_value
                        })

                    overview_dept.append({
                        "start_date": f"{week_start.strftime('%d-%m-%Y')}",
                        "end_date": f"{week_end.strftime('%d-%m-%Y')}",
                        "department": dept_grouped
                    })

                # Current week till today
                records = request.env['labour.billing'].sudo().search([
                    ('date', '>=', current_week_start),
                    ('date', '<=', current_week_end)
                ])
                dept_grouped = []
                departments = records.mapped('department_id')
                # Use month of current_week_start to get days_in_month
                cw_year = current_week_start.year
                cw_month = current_week_start.month
                days_in_month = calendar.monthrange(cw_year, cw_month)[1]
                days_count = (current_week_end - current_week_start).days + 1

                for dept in departments:
                    dept_records = records.filtered(lambda r: r.department_id == dept)
                    dept_actual_value = sum(dept_records.mapped('charge_amount') or [0])

                    score_line = score_record.score_line_ids.filtered(lambda l: l.department_id.id == dept.id)
                    min_dep_per_day = (score_line.min_dep_score) / days_in_month if score_line else 0
                    max_dep_per_day = (score_line.max_dep_score) / days_in_month if score_line else 0

                    dept_grouped.append({
                        "department_id": dept.id,
                        "department_name": dept.name,
                        "actual_value": dept_actual_value,
                        "min_value": round(min_dep_per_day * days_count, 2),
                        "max_value": round(max_dep_per_day * days_count, 2),
                    })

                overview_dept.append({
                    "period": f"{current_week_start.strftime('%d-%m-%Y')} to {current_week_end.strftime('%d-%m-%Y')}",
                    "department": dept_grouped
                })

            elif filter_type == "YTD":
                for year_diff in range(0, 3):
                    start_date = date(today.year - year_diff, 1, 1)
                    end_date = date(today.year - year_diff, today.month, today.day)

                    records = request.env['labour.billing'].sudo().search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date)
                    ])

                    # total days elapsed in year up to end_date
                    total_days_elapsed = sum(
                        calendar.monthrange(end_date.year, m)[1] for m in range(1, end_date.month)
                    ) + end_date.day
                    days_multiplier = total_days_elapsed / 30.0

                    dept_grouped = []
                    departments = records.mapped('department_id')
                    for dept in departments:
                        dept_records = records.filtered(lambda r: r.department_id == dept)
                        dept_actual_value = sum(dept_records.mapped('charge_amount') or [0])

                        score_line = score_record.score_line_ids.filtered(lambda l: l.department_id.id == dept.id)
                        monthly_min_base = score_line.min_dep_score or 0 if score_line else 0
                        monthly_max_base = score_line.max_dep_score or 0 if score_line else 0

                        dept_grouped.append({
                            "department_id": dept.id,
                            "department_name": dept.name,
                            "actual_value": dept_actual_value,
                            "min_value": round(monthly_min_base * days_multiplier, 2),
                            "max_value": round(monthly_max_base * days_multiplier, 2),
                        })

                    overview_dept.append({
                        "year": f"{start_date.year}",
                        "start_date": f"{start_date.strftime('%d-%m-%Y')}",
                        "end_date": f"{end_date.strftime('%d-%m-%Y')}",
                        "total_actual_value": sum(d['actual_value'] for d in dept_grouped),
                        "department": dept_grouped
                    })

        # ----------------------------
        # Step 5: Response
        # ----------------------------
        response = {
            "statusCode": 200,
            "message": "Score Department Overview",
            "score_id": score_id,
            "score_name": score_record.score_name,
            "overview_department": overview_dept
        }

        return request.make_response(
            json.dumps(response),
            headers=[('Content-Type', 'application/json')]
        )

    # Third Quadrant
    @http.route('/api/score/overview/employee', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def get_score_employee_overview(self, **kwargs):
        auth_header = request.httprequest.headers.get("Authorization")
        if not auth_header:
            return request.make_response(
                json.dumps({"statusCode": 401, "message": "Token missing"}),
                headers=[('Content-Type', 'application/json')]
            )

        token = auth_header.split(" ")[1] if auth_header.startswith("Bearer ") else auth_header

        try:
            body = json.loads(request.httprequest.data.decode("utf-8"))
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            uid = payload.get("uid")
            if isinstance(uid, dict):
                uid = uid.get("uid")
        except jwt.ExpiredSignatureError:
            return request.make_response(
                json.dumps({"statusCode": 401, "message": "Token expired"})
            )
        except jwt.InvalidTokenError:
            return request.make_response(
                json.dumps({"statusCode": 401, "message": "Invalid token"})
            )

        score_id = int(body.get("scoreId"))
        dept_id = int(body.get("departmentId"))
        filter_type = body.get("filterType")
        start_date_str = body.get("startDate")
        end_date_str = body.get("endDate")

        if not score_id or not dept_id:
            return request.make_response(
                json.dumps({"statusCode": 400, "message": "scoreId and departmentId are required"}),
            )

        user = request.env['res.users'].sudo().browse(uid)

        if not user.exists() or len(user) != 1:
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "User not found or multiple users"})
            )

        score_record = request.env['bizdom.score'].sudo().browse(score_id)
        if not score_record.exists():
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "Score record not found"}),
            )

        dept = request.env['hr.department'].sudo().browse(dept_id)
        if not dept.exists():
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "Department not found"}),
            )

        today = datetime.today()
        overview_employee = []

        if score_record.score_name == "Labour":
            # Custom range (unchanged)
            if filter_type == "Custom" and start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
                    end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()

                    if start_date > end_date:
                        return json.dumps({"statusCode": 400, "message": "Start date should be less than end date"})

                    delta = relativedelta(end_date, start_date)
                    total_months = delta.years * 12 + delta.months
                    if total_months > 3:
                        start_year = start_date.year
                        end_year = end_date.year
                        for year in range(3):
                            year_start = date(start_year - year, start_date.month, start_date.day)
                            year_end = date(end_year - year, end_date.month, end_date.day)
                            records = request.env['labour.billing'].sudo().search([
                                ('date', '>=', year_start),
                                ('date', '<=', year_end),
                                ('department_id', '=', dept.id)
                            ])
                            emp_grouped = []
                            employees = records.mapped('employee_id')
                            for emp in employees:
                                emp_records = records.filtered(lambda r: r.employee_id == emp)
                                emp_actual_value = sum(emp_records.mapped('charge_amount') or [0])
                                request.env.cr.execute("SELECT name FROM hr_employee WHERE id=%s", (emp.id,))
                                emp_name = request.env.cr.fetchone()
                                emp_name = emp_name[0] if emp_name else "N/A"
                                emp_grouped.append({
                                    "employee_id": emp.id,
                                    "employee_name": emp_name,
                                    "actual_value": emp_actual_value
                                })
                            overview_employee.append({
                                "start_date": year_start.strftime("%d-%m-%Y"),
                                "end_date": year_end.strftime("%d-%m-%Y"),
                                "total_actual_value": sum(e['actual_value'] for e in emp_grouped),
                                "employees": emp_grouped
                            })



                    else:
                        duration = end_date-start_date
                        for i in range(3):
                            period_end=end_date-(duration*i)
                            period_start = period_end - duration

                            records=request.env['labour.billing'].sudo().search([
                                ('date','>=',period_start),
                                ('date','<=',period_end),
                                ('department_id','=',dept.id)
                            ])
                            emp_grouped = []
                            employees=records.mapped('employee_id')
                            for emp in employees:
                                emp_records=records.filtered(lambda r: r.employee_id==emp)
                                emp_actual_value=sum(emp_records.mapped('charge_amount') or [0])
                                request.env.cr.execute("SELECT name FROM hr_employee WHERE id=%s", (emp.id,))
                                emp_name=request.env.cr.fetchone()
                                emp_name=emp_name[0] if emp_name else "N/A"
                                emp_grouped.append({
                                    "employee_id":emp.id,
                                    "employee_name":emp_name,
                                    "actual_value":emp_actual_value })
                            overview_employee.append({
                                "start_date": period_start.strftime("%d-%m-%Y"),
                                "end_date": period_end.strftime("%d-%m-%Y"),
                                "total_actual_value": sum(e['actual_value'] for e in emp_grouped),
                                "employees": emp_grouped
                            })

                except ValueError:
                    return request.make_response(
                        json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"}),
                    )


            elif filter_type == "WTD":
                # Current week start
                current_week_start = today - timedelta(days=today.weekday())
                current_week_end = today

                # Past 2 full weeks (capped to same weekday)
                for i in range(2, 0, -1):
                    week_start = current_week_start - timedelta(weeks=i)
                    week_end = week_start + timedelta(days=today.weekday())
                    records = request.env['labour.billing'].sudo().search([
                        ('date', '>=', week_start.date() if isinstance(week_start, datetime) else week_start),
                        ('date', '<=', week_end.date() if isinstance(week_end, datetime) else week_end),
                        ('department_id', '=', dept.id)
                    ])

                    emp_grouped = []
                    employees = records.mapped('employee_id')
                    for emp in employees:
                        emp_records = records.filtered(lambda r: r.employee_id == emp)
                        emp_actual_value = sum(emp_records.mapped('charge_amount') or [0])
                        request.env.cr.execute("SELECT name FROM hr_employee WHERE id=%s", (emp.id,))
                        emp_name = request.env.cr.fetchone()
                        emp_name = emp_name[0] if emp_name else "N/A"
                        emp_grouped.append({
                            "employee_id": emp.id,
                            "employee_name": emp_name,
                            "actual_value": emp_actual_value
                        })

                    overview_employee.append({
                        "start_date": f"{week_start.strftime('%d-%m-%Y')}",
                        "end_date": f"{week_end.strftime('%d-%m-%Y')}",
                        "total_actual_value": sum(e['actual_value'] for e in emp_grouped),
                        "employees": emp_grouped
                    })

                # Current week till today
                records = request.env['labour.billing'].sudo().search([
                    ('date', '>=',
                     current_week_start.date() if isinstance(current_week_start, datetime) else current_week_start),
                    ('date', '<=',
                     current_week_end.date() if isinstance(current_week_end, datetime) else current_week_end),
                    ('department_id', '=', dept.id)
                ])

                emp_grouped = []
                employees = records.mapped('employee_id')
                for emp in employees:
                    emp_records = records.filtered(lambda r: r.employee_id == emp)
                    emp_actual_value = sum(emp_records.mapped('charge_amount') or [0])
                    request.env.cr.execute("SELECT name FROM hr_employee WHERE id=%s", (emp.id,))
                    emp_name = request.env.cr.fetchone()
                    emp_name = emp_name[0] if emp_name else "N/A"
                    emp_grouped.append({
                        "employee_id": emp.id,
                        "employee_name": emp_name,
                        "actual_value": emp_actual_value
                    })

                overview_employee.append({
                    "start_date": f"{current_week_start.strftime('%d-%m-%Y')}",
                    "end_date": f"{current_week_end.strftime('%d-%m-%Y')}",
                    "total_actual_value": sum(e['actual_value'] for e in emp_grouped),
                    "employees": emp_grouped
                })

            elif filter_type == "MTD" or not filter_type:
                for i in range(2, -1, -1):
                    month_start = (today.replace(day=1) - relativedelta(months=i))
                    year = month_start.year
                    month = month_start.month
                    days_in_month = calendar.monthrange(year, month)[1]
                    month_end_day = min(today.day, (month_start + relativedelta(months=1) - timedelta(days=1)).day)
                    month_end = month_start.replace(day=month_end_day)

                    records = request.env['labour.billing'].sudo().search([
                        ('date', '>=', month_start),
                        ('date', '<=', month_end),
                        ('department_id', '=', dept.id)
                    ])

                    emp_grouped = []
                    employees = records.mapped('employee_id')
                    for emp in employees:
                        emp_records = records.filtered(lambda r: r.employee_id == emp)
                        emp_actual_value = sum(emp_records.mapped('charge_amount') or [0])
                        request.env.cr.execute("SELECT name FROM hr_employee WHERE id=%s", (emp.id,))
                        emp_name = request.env.cr.fetchone()
                        emp_name = emp_name[0] if emp_name else "N/A"
                        emp_grouped.append({
                            "employee_id": emp.id,
                            "employee_name": emp_name,
                            "actual_value": emp_actual_value
                        })

                    overview_employee.append({
                        "month": month_start.strftime("%B %Y"),
                        "start_date": month_start.strftime("%d-%m-%Y"),
                        "end_date": month_end.strftime("%d-%m-%Y"),
                        "total_actual_value": sum(e['actual_value'] for e in emp_grouped),
                        "employees": emp_grouped
                    })

            elif filter_type == "YTD":
                for year_diff in range(0, 3):
                    start_date = date(today.year - year_diff, 1, 1)
                    end_date = date(today.year - year_diff, today.month, today.day)

                    records = request.env['labour.billing'].sudo().search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date),
                        ('department_id', '=', dept.id)
                    ])

                    emp_grouped = []
                    employees = records.mapped('employee_id')
                    for emp in employees:
                        emp_records = records.filtered(lambda r: r.employee_id == emp)
                        emp_actual_value = sum(emp_records.mapped('charge_amount') or [0])
                        request.env.cr.execute("SELECT name FROM hr_employee WHERE id=%s", (emp.id,))
                        emp_name = request.env.cr.fetchone()
                        emp_name = emp_name[0] if emp_name else "N/A"
                        emp_grouped.append({
                            "employee_id": emp.id,
                            "employee_name": emp_name,
                            "actual_value": emp_actual_value
                        })

                    overview_employee.append({
                        "year": f"{start_date.year}",
                        "start_date": f"{start_date.strftime('%d-%m-%Y')}",
                        "end_date": f"{end_date.strftime('%d-%m-%Y')}",
                        "total_actual_value": sum(e['actual_value'] for e in emp_grouped),
                        "employees": emp_grouped
                    })

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
