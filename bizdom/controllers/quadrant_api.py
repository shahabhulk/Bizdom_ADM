import calendar
import json
from datetime import date, datetime
from odoo import http
from odoo.http import request
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import jwt
from reportlab.lib.pagesizes import elevenSeventeen

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

        # auth check
        auth_header = request.httprequest.headers.get("Authorization")
        if not auth_header:
            return json.dumps({"statusCode": 401, "message": "Token missing"})

        token = auth_header.split(" ")[1] if auth_header.startswith("Bearer ") else auth_header

        try:
            body = {
                'scoreId': int(kwargs.get('scoreId')),
                'filterType': kwargs.get('filterType')
            }
            if 'startDate' in kwargs:
                body['startDate'] = kwargs['startDate']
            if 'endDate' in kwargs:
                body['endDate'] = kwargs['endDate']

            # body = json.loads(request.httprequest.data.decode("utf-8"))
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

        if not score_record.exists():
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "Score record not found"}),
            )
        # PILLAR OPERATIONS
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


        elif score_record.score_name == "Customer Satisfaction":
            if filter_type == "Custom" and start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
                    end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()

                    if start_date > end_date:
                        return json.dumps({"statusCode": 400, "message": "Start date should be less than end date"})

                    delta = relativedelta(end_date, start_date)
                    total_months = delta.years * 12 + delta.months

                    if total_months > 3:
                        # For date ranges > 3 months, show yearly segments
                        current_year = start_date.year
                        end_year = end_date.year

                        for year in range(3):  # Last 3 years
                            year_start = date(current_year - year, start_date.month, start_date.day)
                            year_end = date(end_year - year, end_date.month, end_date.day)

                            records = request.env['feedback.data'].sudo().search([
                                ('feedback_date', '>=', year_start),
                                ('feedback_date', '<=', year_end)
                            ])

                            ratings = [int(rating) for rating in records.mapped('rating') if rating]
                            list_of_jc = list(set(records.mapped('job_card_name')))
                            average_total_rating = sum(ratings) / len(list_of_jc) if len(list_of_jc) > 0 else 0.0
                            average_total_rating_percentage = average_total_rating / 5 * 100

                            overview_list.append({
                                "start_date": year_start.strftime('%d-%m-%Y'),
                                "end_date": year_end.strftime('%d-%m-%Y'),
                                "actual_value": average_total_rating_percentage
                            })
                    else:
                        # For date ranges ≤ 3 months, show 3 periods going backwards
                        duration = end_date - start_date
                        for i in range(3):
                            period_end = end_date - (duration * i)
                            period_start = period_end - duration

                            # For the last period, don't go before the start date
                            monthly_score = score_record.with_context(
                                force_date_start=period_start,
                                force_date_end=period_end
                            )

                            monthly_score._compute_context_total_score()
                            satisfaction_percentage = monthly_score.context_total_score * 100

                            overview_list.append({
                                "start_date": period_start.strftime('%d-%m-%Y'),
                                "end_date": period_end.strftime('%d-%m-%Y'),
                                "actual_value": round(satisfaction_percentage, 2)
                            })

                except ValueError:
                    return json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"})
            elif filter_type == "WTD":
                current_week_start = today - timedelta(days=today.weekday())
                current_week_end = today

                # For current week and previous 2 weeks
                for i in range(3):
                    week_start = current_week_start - timedelta(weeks=i)
                    week_end = current_week_end - timedelta(weeks=i) if i > 0 else current_week_end

                    # Calculate job card ratings
                    weekly_score = score_record.with_context(
                        force_date_start=week_start,
                        force_date_end=week_end
                    )

                    weekly_score._compute_context_total_score()
                    satisfaction_percentage = weekly_score.context_total_score * 100

                    overview_list.append({
                        "period": f"Week {3 - i}",
                        "start_date": week_start.strftime('%d-%m-%Y'),
                        "end_date": week_end.strftime('%d-%m-%Y'),
                        "actual_value": round(satisfaction_percentage, 2)
                    })

            elif filter_type == "MTD" or not filter_type:
                current_month_start = today.replace(day=1)  # First day of current month
                current_day = today.day  # Get the current day of month

                for i in range(3):  # Current month and previous 2 months
                    # Calculate month start
                    month_start = (current_month_start - relativedelta(months=i))
                    # Calculate month end
                    if i == 0:  # Current month
                        month_end = today
                    else:  # Previous months
                        # Try to set to the same day of month, but don't exceed the last day of that month
                        last_day_of_month = (month_start + relativedelta(day=31)).day
                        month_end = month_start.replace(day=min(current_day, last_day_of_month))

                    monthly_score = score_record.with_context(
                        force_date_start=month_start,
                        force_date_end=month_end
                    )

                    monthly_score._compute_context_total_score()
                    satisfaction_percentage = monthly_score.context_total_score * 100

                    overview_list.append({
                        "month": month_start.strftime("%B %Y"),
                        "start_date": month_start.strftime('%d-%m-%Y'),
                        "end_date": month_end.strftime('%d-%m-%Y'),
                        "actual_value": round(satisfaction_percentage, 2)
                    })
            elif filter_type == "YTD":
                current_year = today.year
                current_month = today.month
                current_day = today.day

                for i in range(3):  # Current year and previous 2 years
                    year = current_year - i

                    # Start of the year
                    year_start = date(year, 1, 1)

                    # End date is either today (for current year) or same date in previous years
                    if i == 0:  # Current year
                        year_end = today
                    else:  # Previous years
                        # Handle February 29th for leap years
                        try:
                            year_end = date(year, current_month, current_day)
                        except ValueError:
                            # If the date doesn't exist (e.g., Feb 29 in non-leap year), use Feb 28
                            year_end = date(year, current_month, current_day - 1)

                    # Calculate job card ratings
                    yearly_score = score_record.with_context(
                        force_date_start=year_start,
                        force_date_end=year_end
                    )

                    yearly_score._compute_context_total_score()
                    satisfaction_percentage = yearly_score.context_total_score * 100

                    overview_list.append({
                        "year": str(year),
                        "start_date": year_start.strftime('%d-%m-%Y'),
                        "end_date": year_end.strftime('%d-%m-%Y'),
                        "actual_value": round(satisfaction_percentage, 2)
                    })

        elif score_record.score_name == "TAT":
            if filter_type == "Custom" and start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
                    end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()

                    if start_date > end_date:
                        return json.dumps({"statusCode": 400, "message": "Start date should be less than end date"})

                    delta = relativedelta(end_date, start_date)
                    total_months = delta.years * 12 + delta.months

                    if total_months > 3:
                        # For date ranges > 3 months, show yearly segments for last 3 years
                        current_year = start_date.year
                        end_year = end_date.year

                        for year in range(3):  # Last 3 years
                            year_start = date(current_year - year, start_date.month,
                                              start_date.day)  # Start of the year
                            year_end = date(end_year - year, end_date.month, end_date.day)  # End of the year

                            # Set context for the score computation for this year
                            year_score = score_record.with_context(
                                force_date_start=year_start,
                                force_date_end=year_end
                            )

                            # Calculate the TAT for this year
                            year_score._compute_context_total_score()
                            tat_value = year_score.context_total_score

                            overview_list.append({
                                "start_date": year_start.strftime('%d-%m-%Y'),
                                "end_date": year_end.strftime('%d-%m-%Y'),
                                "actual_value": round(tat_value, 2) if tat_value else 0.0
                            })

                        # Sort by date (oldest first)
                        # overview_list.sort(key=lambda x: datetime.strptime(x['start_date'], '%d-%m-%Y').date())
                    else:
                        # For date ranges ≤ 3 months, show the single period
                        duration = end_date - start_date
                        for i in range(3):
                            period_end = end_date - (duration * i)
                            period_start = period_end - duration

                            period_start = max(period_start, date(2000, 1, 1))

                            monthly_score = score_record.with_context(
                                force_date_start=period_start,
                                force_date_end=period_end
                            )

                            monthly_score._compute_context_total_score()
                            tat_value = monthly_score.context_total_score

                            overview_list.append({
                                "start_date": period_start.strftime('%d-%m-%Y'),
                                "end_date": period_end.strftime('%d-%m-%Y'),
                                "actual_value": round(tat_value, 2) if tat_value else 0.0
                            })


                except ValueError:
                    return json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"})
            elif filter_type == "WTD":
                current_week_start = today - timedelta(days=today.weekday())
                current_week_end = today

                for i in range(3):
                    week_start = current_week_start - timedelta(weeks=i)
                    week_end = current_week_end - timedelta(weeks=i) if i > 0 else current_week_end

                    weekly_record = score_record.with_context(
                        force_date_start=week_start,
                        force_date_end=week_end
                    )

                    weekly_record._compute_context_total_score()
                    tat_value = weekly_record.context_total_score

                    overview_list.append({
                        "start_date": week_start.strftime('%d-%m-%Y'),
                        "end_date": week_end.strftime('%d-%m-%Y'),
                        "actual_value": round(tat_value, 2) if tat_value else 0.0
                    })
            elif filter_type == "MTD" or not filter_type:
                current_month_start = today.replace(day=1)
                current_day = today.day

                for i in range(3):
                    month_start = current_month_start - relativedelta(months=i)
                    if i == 0:
                        month_end = today
                    else:
                        last_day_of_month = (month_start + relativedelta(day=31)).day
                        month_end = month_start.replace(day=min(current_day, last_day_of_month))

                    monthly_score = score_record.with_context(
                        force_date_start=month_start,
                        force_date_end=month_end
                    )

                    monthly_score._compute_context_total_score()
                    tat_value = monthly_score.context_total_score

                    overview_list.append({
                        "start_date": month_start.strftime('%d-%m-%Y'),
                        "end_date": month_end.strftime('%d-%m-%Y'),
                        "actual_value": round(tat_value, 2) if tat_value else 0.0
                    })

            elif filter_type == "YTD":
                current_year = today.year
                current_month = today.month
                current_day = today.day

                for i in range(3):
                    year = current_year - i

                    year_start = date(year, 1, 1)
                    if i == 0:
                        year_end = today
                    else:
                        try:
                            year_end = date(year, current_month, current_day)
                        except ValueError:
                            # If the date doesn't exist (e.g., Feb 29 in non-leap year), use Feb 28
                            year_end = date(year, current_month, current_day - 1)

                    yearly_score = score_record.with_context(
                        force_date_start=year_start,
                        force_date_end=year_end
                    )
                    yearly_score._compute_context_total_score()
                    tat_value = yearly_score.context_total_score

                    overview_list.append({
                        "start_date": year_start.strftime('%d-%m-%Y'),
                        "end_date": year_end.strftime('%d-%m-%Y'),
                        "actual_value": round(tat_value, 2) if tat_value else 0.0
                    })

        # PILLAR SALES AND MARKETING

        elif score_record.score_name == "Leads":
            lead_model = request.env['crm.lead'].sudo()
            if filter_type == "Custom" and start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
                    end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()

                    if start_date > end_date:
                        return json.dumps({"statusCode": 400, "message": "Start date should be less than end date"})
                    delta = relativedelta(end_date, start_date)
                    total_months = delta.years * 12 + delta.months
                    if total_months > 3:
                        current_year = start_date.year
                        end_year = end_date.year

                        for year in range(3):
                            year_start = date(current_year - year, start_date.month,
                                              start_date.day)  # Start of the year
                            year_end = date(end_year - year, end_date.month, end_date.day)  # End of the year

                            year_score = score_record.with_context(
                                force_date_start=year_start,
                                force_date_end=year_end
                            )
                            year_score._compute_context_total_score()
                            lead_value = year_score.context_total_score

                            conversion_count = lead_model.search_count([
                                ('create_date', '>=', year_start),
                                ('create_date', '<=', year_end),
                                ('stage_id', '=', 2),
                                ('company_id', '=', user.company_id.id)

                            ])

                            overview_list.append({
                                "start_date": year_start.strftime('%d-%m-%Y'),
                                "end_date": year_end.strftime('%d-%m-%Y'),
                                "min_value": "0",
                                "max_value": "0",
                                "conversion_value": conversion_count if conversion_count else "0",
                                "actual_value": round(lead_value, 2) if lead_value else 0.0
                            })


                    else:
                        duration = end_date - start_date
                        for i in range(3):
                            period_end = end_date - (duration * i)
                            period_start = period_end - duration

                            period_start = max(period_start, date(2000, 1, 1))

                            monthly_score = score_record.with_context(
                                force_date_start=period_start,
                                force_date_end=period_end
                            )

                            conversion_count = lead_model.search_count([
                                ('create_date', '>=', period_start),
                                ('create_date', '<=', period_end),
                                ('stage_id', '=', 2),
                                ('company_id', '=', user.company_id.id)

                            ])

                            monthly_score._compute_context_total_score()
                            lead_value = monthly_score.context_total_score

                            overview_list.append({
                                "start_date": period_start.strftime('%d-%m-%Y'),
                                "end_date": period_end.strftime('%d-%m-%Y'),
                                "min_value": "0",
                                "max_value": "0",
                                "conversion_count": conversion_count if conversion_count else "0",
                                "actual_value": round(lead_value, 2) if lead_value else 0.0
                            })


                except Exception as e:
                    return json.dumps({
                        "statusCode": 500,
                        "message": "Internal Server Error"
                    })
            elif filter_type == "WTD":
                current_week_start = today - timedelta(days=today.weekday())
                current_week_end = today

                for i in range(3):
                    week_start = current_week_start - timedelta(weeks=i)
                    week_end = current_week_end - timedelta(weeks=i) if i > 0 else current_week_end

                    # Calculate job card ratings
                    weekly_score = score_record.with_context(
                        force_date_start=week_start,
                        force_date_end=week_end
                    )

                    weekly_score._compute_context_total_score()
                    lead_value = weekly_score.context_total_score

                    conversion_count = lead_model.search_count([
                        ('create_date', '>=', week_start),
                        ('create_date', '<=', week_end),
                        ('stage_id', '=', 2),
                        ('company_id', '=', user.company_id.id)

                    ])

                    overview_list.append({
                        "period": f"Week {3 - i}",
                        "start_date": week_start.strftime('%d-%m-%Y'),
                        "end_date": week_end.strftime('%d-%m-%Y'),
                        "min_value": "",
                        "max_value": "",
                        "conversion_value": conversion_count if conversion_count else "0",
                        "actual_value": lead_value
                    })

            elif filter_type == "MTD" or not filter_type:
                current_month_start = today.replace(day=1)
                current_day = today.day

                for i in range(3):  # Current month and previous 2 months
                    # Calculate month start
                    month_start = (current_month_start - relativedelta(months=i))
                    # Calculate month end
                    if i == 0:  # Current month
                        month_end = today
                    else:  # Previous months
                        # Try to set to the same day of month, but don't exceed the last day of that month
                        last_day_of_month = (month_start + relativedelta(day=31)).day
                        month_end = month_start.replace(day=min(current_day, last_day_of_month))

                    monthly_score = score_record.with_context(
                        force_date_start=month_start,
                        force_date_end=month_end
                    )

                    monthly_score._compute_context_total_score()
                    lead_value = monthly_score.context_total_score

                    conversion_count = lead_model.search_count([
                        ('create_date', '>=', month_start),
                        ('create_date', '<=', month_end),
                        ('stage_id', '=', 2),
                        ('company_id', '=', user.company_id.id)

                    ])

                    overview_list.append({
                        "month": month_start.strftime("%B %Y"),
                        "start_date": month_start.strftime('%d-%m-%Y'),
                        "end_date": month_end.strftime('%d-%m-%Y'),
                        "min_value": "0",
                        "max_value": "0",
                        "conversion_value": conversion_count if conversion_count else "0",
                        "actual_value": lead_value if lead_value else 0.0
                    })
            elif filter_type == "YTD":
                current_year = today.year
                current_month = today.month
                current_day = today.day

                for i in range(3):  # Current year and previous 2 years
                    year = current_year - i

                    # Start of the year
                    year_start = date(year, 1, 1)

                    # End date is either today (for current year) or same date in previous years
                    if i == 0:  # Current year
                        year_end = today
                    else:  # Previous years
                        # Handle February 29th for leap years
                        try:
                            year_end = date(year, current_month, current_day)
                        except ValueError:
                            # If the date doesn't exist (e.g., Feb 29 in non-leap year), use Feb 28
                            year_end = date(year, current_month, current_day - 1)

                    # Calculate job card ratings
                    yearly_score = score_record.with_context(
                        force_date_start=year_start,
                        force_date_end=year_end
                    )

                    yearly_score._compute_context_total_score()
                    lead_value = yearly_score.context_total_score

                    conversion_count = lead_model.search_count([
                        ('create_date', '>=', year_start),
                        ('create_date', '<=', year_end),
                        ('stage_id', '=', 2),
                        ('company_id', '=', user.company_id.id)

                    ])

                    overview_list.append({
                        "year": str(year),
                        "start_date": year_start.strftime('%d-%m-%Y'),
                        "end_date": year_end.strftime('%d-%m-%Y'),
                        "min_value": "",
                        "max_value": "",
                        "conversion_value": conversion_count if conversion_count else 0,
                        "actual_value": round(lead_value)
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
            # body = json.loads(request.httprequest.data.decode("utf-8"))
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
        score_id = int(kwargs.get("scoreId"))
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

        start_date_str = kwargs.get("startDate")
        end_date_str =  kwargs.get("endDate")
        filter_type =  kwargs.get("filterType")

        score_record = request.env['bizdom.score'].sudo().browse(score_id)

        if not score_record.exists():
            return request.make_response(
                json.dumps({"statusCode": 404, "message": "Score record not found"}),
            )

        overview_dept = []
        today = datetime.today()
        score_record = request.env['bizdom.score'].sudo().browse(score_id)
        # PILLAR OPERATIONS
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
        elif score_record.score_name == "Customer Satisfaction":
            print(score_record.score_name)
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

                            # Create a new recordset for this period
                            records = request.env['feedback.data'].sudo().search([
                                ('feedback_date', '>=', year_start),
                                ('feedback_date', '<=', year_end)
                            ])

                            dept_grouped = []
                            departments = records.mapped('department_id')
                            for dept in departments:
                                dept_records = records.filtered(lambda r: r.department_id == dept)
                                job_cards = list(set(dept_records.mapped('job_card_name')))
                                ratings = [int(rating) for rating in dept_records.mapped('rating') if rating]
                                avg_score_value = sum(ratings) / len(job_cards)
                                print("len", len(dept_records))
                                print("avg", avg_score_value)
                                score_value_percentage = (avg_score_value / 5) * 100
                                dept_grouped.append({
                                    "department_id": dept.id,
                                    "department_name": dept.name,
                                    "min_value": 0,
                                    "max_value": 0,
                                    "actual_value": round(score_value_percentage, 2),
                                })

                            year_score = score_record.with_context(
                                force_date_start=year_start,
                                force_date_end=year_end
                            )

                            year_score._compute_context_total_score()
                            total_satisfaction = year_score.context_total_score * 100

                            overview_dept.append({
                                "start_date": year_start.strftime("%d-%m-%Y"),
                                "end_date": year_end.strftime("%d-%m-%Y"),
                                "total_actual_value": round(total_satisfaction, 2),
                                "department": dept_grouped
                            })
                    else:
                        duration = end_date - start_date
                        for i in range(3):
                            period_end = end_date - (duration * i)
                            period_start = period_end - duration
                            period_start = max(period_start, date(2000, 1, 1))  # Prevent going too far back

                            # Get the score records with the date context
                            records = request.env['feedback.data'].sudo().search([
                                ('feedback_date', '>=', period_start),
                                ('feedback_date', '<=', period_end)
                            ])

                            dept_grouped = []
                            departments = records.mapped('department_id')
                            for dept in departments:
                                dept_records = records.filtered(lambda r: r.department_id == dept)
                                job_cards = list(set(dept_records.mapped('job_card_name')))
                                ratings = [int(rating) for rating in dept_records.mapped('rating') if rating]
                                avg_score_value = sum(ratings) / len(job_cards)
                                print("len", len(dept_records))
                                print("avg", avg_score_value)
                                score_value_percentage = (avg_score_value / 5) * 100
                                dept_grouped.append({
                                    "department_id": dept.id,
                                    "department_name": dept.name,
                                    "min_value": 0,
                                    "max_value": 0,
                                    "actual_value": round(score_value_percentage, 2),
                                })

                            year_score = score_record.with_context(
                                force_date_start=period_start,
                                force_date_end=period_end
                            )

                            year_score._compute_context_total_score()
                            total_satisfaction = year_score.context_total_score * 100

                            overview_dept.append({
                                "start_date": period_start.strftime("%d-%m-%Y"),
                                "end_date": period_end.strftime("%d-%m-%Y"),
                                "total_actual_value": round(total_satisfaction, 2),
                                "department": dept_grouped
                            })
                except ValueError:
                    return request.make_response(
                        json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"}),
                        headers=[('Content-Type', 'application/json')]
                    )


            elif filter_type == "WTD":
                current_week_start = today - timedelta(days=today.weekday())
                current_week_end = today

                for i in range(2, -1, -1):
                    # Changed from range(2, 0, -1) to include current week (i=0)
                    week_start = current_week_start - timedelta(weeks=i)
                    week_end = week_start + timedelta(days=min(today.weekday(), 6))  # Cap to current day or Saturday
                    records = request.env['feedback.data'].sudo().search([
                        ('feedback_date', '>=', week_start),
                        ('feedback_date', '<=', week_end)
                    ])
                    dept_grouped = []
                    departments = records.mapped('department_id')
                    for dept in departments:
                        dept_records = records.filtered(lambda r: r.department_id == dept)
                        job_cards = list(set(dept_records.mapped('job_card_name')))
                        if not job_cards:
                            continue

                        ratings = [int(rating) for rating in dept_records.mapped('rating') if rating]

                        print("ratings", ratings)
                        if not ratings:
                            continue

                        avg_score_value = sum(ratings) / len(job_cards)
                        satisfaction_value = (avg_score_value / 5) * 100
                        # print("asdfasfd",avg_score_value)
                        dept_grouped.append({
                            'department_id': dept.id,
                            'department_name': dept.name,
                            'max_value': "",
                            'min_value': "",
                            'actual_value': round(satisfaction_value, 2),
                        })

                    week_score = score_record.with_context(
                        force_date_start=week_start,
                        force_date_end=week_end
                    )

                    week_score._compute_context_total_score()
                    total_satisfaction = week_score.context_total_score * 100
                    overview_dept.append({
                        "start_date": week_start.strftime("%d-%m-%Y"),
                        "end_date": week_end.strftime("%d-%m-%Y"),
                        "total_actual_value": total_satisfaction,
                        "department": dept_grouped

                    })


            elif filter_type == "MTD" or not filter_type:

                for i in range(2, -1, -1):
                    month_start = (today.replace(day=1) - relativedelta(months=i))
                    print("today", today)
                    print("dd", month_start)
                    year = month_start.year
                    month = month_start.month
                    days_in_month = calendar.monthrange(year, month)[1]
                    month_end_day = min(today.day, (month_start + relativedelta(months=1) - timedelta(days=1)).day)
                    month_end = month_start.replace(day=month_end_day)
                    print("eeee", month_end)

                    records = request.env['feedback.data'].sudo().search([
                        ('feedback_date', '>=', month_start),
                        ('feedback_date', '<=', month_end)
                    ])
                    dept_grouped = []
                    departments = records.mapped('department_id')
                    for dept in departments:
                        dept_records = records.filtered(lambda r: r.department_id == dept)
                        job_cards = list(set(dept_records.mapped('job_card_name')))
                        if not job_cards:  # Skip if no job cards
                            continue

                        ratings = [int(rating) for rating in dept_records.mapped('rating') if rating]

                        if not ratings:
                            continue

                        avg_score_value = sum(ratings) / len(job_cards)
                        satisfaction_value = (avg_score_value / 5) * 100
                        dept_grouped.append({
                            'department_id': dept.id,
                            'department_name': dept.name,
                            'max_value': "",
                            'min_value': "",
                            'actual_value': round(satisfaction_value, 2)
                        })

                    month_score = score_record.with_context(
                        force_date_start=month_start,
                        force_date_end=month_end
                    )
                    month_score._compute_context_total_score()
                    total_satisfaction = month_score.context_total_score * 100
                    overview_dept.append({
                        "start_date": month_start.strftime("%d-%m-%Y"),
                        "end_date": month_end.strftime("%d-%m-%Y"),
                        "total_actual_value": round(total_satisfaction, 2),
                        "department": dept_grouped
                    })


            elif filter_type == "YTD":
                for year_diff in range(0, 3):
                    start_date = date(today.year - year_diff, 1, 1)
                    end_date = date(today.year - year_diff, today.month, today.day)

                    records = request.env['feedback.data'].sudo().search([
                        ('feedback_date', '>=', start_date),
                        ('feedback_date', '<=', end_date)
                    ])
                    total_days_elapsed = sum(
                        calendar.monthrange(end_date.year, m)[1] for m in range(1, end_date.month)
                    ) + end_date.day
                    days_multiplier = total_days_elapsed / 30.0
                    dept_grouped = []
                    departments = records.mapped('department_id')
                    for dept in departments:
                        dept_records = records.filtered(lambda r: r.department_id == dept)
                        job_cards = list(set(dept_records.mapped('job_card_name')))
                        if not job_cards:
                            continue

                        ratings = [int(rating) for rating in dept_records.mapped('rating') if rating]
                        if not ratings:
                            continue

                        avg_score_value = sum(ratings) / len(job_cards)
                        satisfaction_value = (avg_score_value / 5) * 100

                        dept_grouped.append({
                            'department_id': dept.id,
                            'department_name': dept.name,
                            'max_value': '',
                            'min_value': '',
                            'actual_value': round(satisfaction_value, 2)
                        })

                    year_score = score_record.with_context(
                        force_date_start=start_date,
                        force_date_end=end_date
                    )
                    year_score._compute_context_total_score()
                    total_satisfaction = year_score.context_total_score * 100

                    overview_dept.append({
                        "year": f"{start_date.year}",
                        "start_date": start_date.strftime("%d-%m-%Y"),
                        "end_date": end_date.strftime("%d-%m-%Y"),
                        "total_actual_value": total_satisfaction,
                        "department": dept_grouped
                    })
        elif score_record.score_name == "TAT":
            if filter_type == "Custom" and start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
                    end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()
                    if start_date > end_date:
                        return json.dumps({
                            "statusCode": 400,
                            "message": "Start date should be less than end date"
                        })
                    delta = relativedelta(end_date, start_date)
                    total_months = delta.years * 12 + delta.months

                    if total_months > 3:
                        start_year = start_date.year
                        end_year = end_date.year

                        for year in range(3):
                            year_start = date(start_year - year, start_date.month, start_date.day)
                            year_end = date(end_year - year, end_date.month, end_date.day)

                            records = request.env['fleet.repair.work.line'].sudo().search([
                                ('repair_id.invoice_order_id', '!=', False),
                                ('repair_id.invoice_order_id.invoice_date', '!=', False),
                                ('repair_id.invoice_order_id.invoice_date', '>=', year_start),
                                ('repair_id.invoice_order_id.invoice_date', '<=', year_end)
                            ])
                            # for i in records:
                            #     print(i.repair_id.job_card_display)

                            dept_grouped = []

                            department = records.mapped('department_type_id')
                            total_bodyshop_time = 0
                            total_workshop_time = 0
                            for dept in department:
                                dept_records = records.filtered(lambda r: r.department_type_id == dept)
                                job_cards = list(set(dept_records.mapped('repair_id.job_card_display')))
                                for rec in dept_records:
                                    if rec.department_type_id and rec.department_type_id.name:
                                        dept_name = rec.department_type_id.name.lower()
                                        if "bodyshop" in dept_name:
                                            total_bodyshop_time += rec.time_diff
                                        elif "workshop" in dept_name:
                                            total_workshop_time += rec.time_diff
                                if dept:
                                    dept_name = dept.name.lower()
                                    if "bodyshop" in dept_name:
                                        dept_grouped.append({
                                            'department_id': dept.id,
                                            'department_name': dept.name,
                                            'max_value': '',
                                            'min_value': '',
                                            'actual_value': round(total_bodyshop_time / (24 * len(job_cards)), 2)
                                        })
                                    elif "workshop" in dept_name:
                                        dept_grouped.append({
                                            'department_id': dept.id,
                                            'department_name': dept.name,
                                            'max_value': '',
                                            'min_value': '',
                                            'actual_value': round(total_workshop_time / (24 * len(job_cards)), 2)
                                        })

                                    # print(rec.department_type_id.name,rec.repair_id.job_card_display)

                            year_score = score_record.with_context(
                                force_date_start=year_start,
                                force_date_end=year_end
                            )
                            year_score._compute_context_total_score()
                            tat_dep_time = year_score.context_total_score

                            overview_dept.append({
                                'start_date': year_start.strftime("%d-%m-%Y"),
                                'end_date': year_end.strftime("%d-%m-%Y"),
                                'max_value': '',
                                'min_value': '',
                                'total_actual_value': round(tat_dep_time, 2),
                                "department": dept_grouped
                            })

                    else:
                        duration = end_date - start_date
                        for i in range(3):
                            period_end = end_date - (duration * i)
                            period_start = period_end - duration

                            records = request.env['fleet.repair.work.line'].sudo().search([
                                ('repair_id.invoice_order_id', '!=', False),
                                ('repair_id.invoice_order_id.invoice_date', '!=', False),
                                ('repair_id.invoice_order_id.invoice_date', '>=', period_start),
                                ('repair_id.invoice_order_id.invoice_date', '<=', period_end)
                            ])

                            dept_grouped = []
                            departments = records.mapped('department_type_id')
                            total_bodyshop_time = 0
                            total_workshop_time = 0
                            for dept in departments:
                                dept_records = records.filtered(lambda r: r.department_type_id == dept)
                                job_cards = list(set(dept_records.mapped('repair_id.job_card_display')))
                                for rec in dept_records:
                                    if rec.department_type_id and rec.department_type_id.name:
                                        dept_name = rec.department_type_id.name.lower()
                                        if "bodyshop" in dept_name:
                                            total_bodyshop_time += rec.time_diff
                                        elif "workshop" in dept_name:
                                            total_workshop_time += rec.time_diff
                                if dept:
                                    dept_name = dept.name.lower()
                                    if "bodyshop" in dept_name:
                                        dept_grouped.append({
                                            'department_id': dept.id,
                                            'department_name': dept.name,
                                            'max_value': '',
                                            'min_value': '',
                                            'actual_value': round(total_bodyshop_time / (24 * len(job_cards)), 2)
                                        })
                                    elif "workshop" in dept_name:
                                        dept_grouped.append({
                                            'department_id': dept.id,
                                            'department_name': dept.name,
                                            'max_value': '',
                                            'min_value': '',
                                            'actual_value': round(total_workshop_time / (24 * len(job_cards)), 2)
                                        })

                            year_score = score_record.with_context(
                                force_date_start=period_start,
                                force_date_end=period_end
                            )
                            year_score._compute_context_total_score()
                            tat_dep_time = year_score.context_total_score

                            overview_dept.append({
                                'start_date': period_start.strftime("%d-%m-%Y"),
                                'end_date': period_end.strftime("%d-%m-%Y"),
                                'max_value': '',
                                'min_value': '',
                                'total_actual_value': tat_dep_time,
                                "department": dept_grouped
                            })


                except ValueError:
                    return request.make_response(
                        json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"}),
                        headers=[('Content-Type', 'application/json')]
                    )



            elif filter_type == "WTD":
                current_week_start = today - timedelta(days=today.weekday())
                current_week_end = today

                for i in range(2, -1, -1):
                    week_start = current_week_start - timedelta(weeks=i)
                    week_end = week_start + timedelta(days=min(today.weekday(), 6))  # Cap to current day or Saturday

                    records = request.env['fleet.repair.work.line'].sudo().search([
                        ('repair_id.invoice_order_id', '!=', False),
                        ('repair_id.invoice_order_id.invoice_date', '!=', False),
                        ('repair_id.invoice_order_id.invoice_date', '>=', week_start),
                        ('repair_id.invoice_order_id.invoice_date', '<=', week_end)
                    ])
                    dept_grouped = []
                    department = records.mapped('department_type_id')
                    total_bodyshop_time = 0
                    total_workshop_time = 0
                    for dept in department:
                        dept_records = records.filtered(lambda r: r.department_type_id == dept)
                        job_cards = list(set(dept_records.mapped('repair_id.job_card_display')))
                        for rec in dept_records:
                            if rec.department_type_id and rec.department_type_id.name:
                                dept_name = rec.department_type_id.name.lower()
                                if "bodyshop" in dept_name:
                                    total_bodyshop_time += rec.time_diff
                                elif "workshop" in dept_name:
                                    total_workshop_time += rec.time_diff
                        dept_name = dept.name.lower()
                        if "bodyshop" in dept_name:
                            dept_grouped.append({
                                'department_id': dept.id,
                                'department_name': dept.name,
                                'max_value': '',
                                'min_value': '',
                                'actual_value': round(total_bodyshop_time / (24 * len(job_cards)), 2) if len(
                                    job_cards) > 0 else 0
                            })
                        elif "workshop" in dept_name:
                            dept_grouped.append({
                                'department_id': dept.id,
                                'department_name': dept.name,
                                'max_value': '',
                                'min_value': '',
                                'actual_value': round(total_workshop_time / (24 * len(job_cards)), 2) if len(
                                    job_cards) > 0 else 0
                            })

                    week_score = score_record.with_context(
                        force_date_start=week_start,
                        force_date_end=week_end
                    )
                    week_score._compute_context_total_score()
                    tat_dep_time = week_score.context_total_score

                    overview_dept.append({
                        'start_date': week_start.strftime("%d-%m-%Y"),
                        'end_date': week_end.strftime("%d-%m-%Y"),
                        'max_value': '',
                        'min_value': '',
                        'total_actual_value': round(tat_dep_time, 2),
                        "department": dept_grouped
                    })





            elif filter_type == "MTD" or not filter_type:
                for i in range(2, -1, -1):
                    month_start = (today.replace(day=1) - relativedelta(months=i))
                    year = month_start.year
                    month = month_start.month
                    days_in_month = calendar.monthrange(year, month)[1]
                    month_end_day = min(today.day, (month_start + relativedelta(months=1) - timedelta(days=1)).day)
                    month_end = month_start.replace(day=month_end_day)
                    print("eeee", month_end)
                    records = request.env['fleet.repair.work.line'].sudo().search([
                        ('repair_id.invoice_order_id', '!=', False),
                        ('repair_id.invoice_order_id.invoice_date', '!=', False),
                        ('repair_id.invoice_order_id.invoice_date', '>=', month_start),
                        ('repair_id.invoice_order_id.invoice_date', '<=', month_end)
                    ])
                    dept_grouped = []
                    department = records.mapped('department_type_id')
                    total_bodyshop_time = 0
                    total_workshop_time = 0
                    for dept in department:
                        dept_records = records.filtered(lambda r: r.department_type_id == dept)
                        job_cards = list(set(dept_records.mapped('repair_id.job_card_display')))
                        for rec in dept_records:
                            if rec.department_type_id and rec.department_type_id.name:
                                dept_name = rec.department_type_id.name.lower()
                                if "bodyshop" in dept_name:
                                    total_bodyshop_time += rec.time_diff
                                elif "workshop" in dept_name:
                                    total_workshop_time += rec.time_diff
                        if dept:
                            dept_name = dept.name.lower()
                            if "bodyshop" in dept_name:
                                dept_grouped.append({
                                    'department_id': dept.id,
                                    'department_name': dept.name,
                                    'max_value': '',
                                    'min_value': '',
                                    'actual_value': round(total_bodyshop_time / (24 * len(job_cards)), 2)
                                })
                            elif "workshop" in dept_name:
                                dept_grouped.append({
                                    'department_id': dept.id,
                                    'department_name': dept.name,
                                    'max_value': '',
                                    'min_value': '',
                                    'actual_value': round(total_workshop_time / (24 * len(job_cards)), 2)
                                })

                    month_score = score_record.with_context(
                        force_date_start=month_start,
                        force_date_end=month_end
                    )
                    month_score._compute_context_total_score()
                    tat_dep_time = month_score.context_total_score

                    overview_dept.append({
                        'start_date': month_start.strftime("%d-%m-%Y"),
                        'end_date': month_end.strftime("%d-%m-%Y"),
                        'max_value': '',
                        'min_value': '',
                        'total_actual_value': round(tat_dep_time, 2),
                        "department": dept_grouped
                    })

            elif filter_type == "YTD":
                for year_diff in range(0, 3):
                    start_date = date(today.year - year_diff, 1, 1)
                    end_date = date(today.year - year_diff, today.month, today.day)

                    records = request.env['fleet.repair.work.line'].sudo().search([
                        ('repair_id.invoice_order_id', '!=', False),
                        ('repair_id.invoice_order_id.invoice_date', '!=', False),
                        ('repair_id.invoice_order_id.invoice_date', '>=', start_date),
                        ('repair_id.invoice_order_id.invoice_date', '<=', end_date)
                    ])
                    dept_grouped = []
                    department = records.mapped('department_type_id')
                    total_bodyshop_time = 0
                    total_workshop_time = 0
                    for dept in department:
                        dept_records = records.filtered(lambda r: r.department_type_id == dept)
                        job_cards = list(set(dept_records.mapped('repair_id.job_card_display')))
                        for rec in dept_records:
                            if rec.department_type_id and rec.department_type_id.name:
                                dept_name = rec.department_type_id.name.lower()
                                if "bodyshop" in dept_name:
                                    total_bodyshop_time += rec.time_diff
                                elif "workshop" in dept_name:
                                    total_workshop_time += rec.time_diff
                        dept_name = dept.name.lower()
                        if "bodyshop" in dept_name:
                            dept_grouped.append({
                                'department_id': dept.id,
                                'department_name': dept.name,
                                'max_value': '',
                                'min_value': '',
                                'actual_value': round(total_bodyshop_time / (24 * len(job_cards)), 2) if len(
                                    job_cards) > 0 else 0
                            })
                        elif "workshop" in dept_name:
                            dept_grouped.append({
                                'department_id': dept.id,
                                'department_name': dept.name,
                                'max_value': '',
                                'min_value': '',
                                'actual_value': round(total_workshop_time / (24 * len(job_cards)), 2) if len(
                                    job_cards) > 0 else 0
                            })

                    month_score = score_record.with_context(
                        force_date_start=start_date,
                        force_date_end=end_date
                    )
                    month_score._compute_context_total_score()
                    tat_dep_time = month_score.context_total_score

                    overview_dept.append({
                        "year": f"{start_date.year}",
                        "start_date": start_date.strftime("%d-%m-%Y"),
                        "end_date": end_date.strftime("%d-%m-%Y"),
                        'max_value': '',
                        'min_value': '',
                        'total_actual_value': round(tat_dep_time, 2),
                        "department": dept_grouped
                    })

        # PILLAR SALES AND MARKETING
        elif score_record.score_name == "Leads":
            if filter_type == 'Custom' and start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, "%d-%m-%Y")
                    end_date = datetime.strptime(end_date_str, "%d-%m-%Y")
                    if start_date > end_date:
                        return json.dumps({
                            "statusCode": 400,
                            "message": "Start date should be less than end date"
                        })
                    delta = relativedelta(end_date, start_date)
                    total_months = delta.years * 12 + delta.months
                    if total_months > 3:
                        start_year = start_date.year
                        end_year = end_date.year

                        for year in range(3):
                            year_start = date(start_year - year, start_date.month, start_date.day)
                            year_end = date(end_year - year, end_date.month, end_date.day)

                            records = request.env['crm.lead'].sudo().search([
                                ('create_date', '>=', year_start),
                                ('create_date', '<=', year_end),
                                ('stage_id', 'in', [1, 2]),
                                ('company_id', '=', user.company_id.id)
                            ])

                            dept_grouped = []
                            department = records.mapped('medium_id')
                            total_online_leads = 0
                            total_offline_leads = 0
                            total_online_conversions = 0
                            total_offline_conversions = 0
                            for dept in department:
                                dept_records = records.filtered(lambda r: r.medium_id == dept)
                                for rec in dept_records:
                                    if rec.medium_id and rec.medium_id.name:
                                        dept_name = rec.medium_id.name.lower()
                                        if "online" in dept_name:
                                            total_online_leads += 1
                                            total_online_conversions += 1 if rec.stage_id.id == 2 else 0
                                        elif "offline" in dept_name:
                                            total_offline_leads += 1
                                            total_offline_conversions += 1 if rec.stage_id.id == 2 else 0
                                if total_online_leads >= 0 and dept.name.lower() == 'online':
                                    dept_grouped.append({
                                        'department_id': dept.id,
                                        'department_name': dept.name,
                                        'max_value': '',
                                        'min_value': '',
                                        'conversion_value': total_online_conversions,
                                        'actual_value': total_online_leads
                                    })

                                elif total_offline_leads >= 0 and dept.name.lower() == 'offline':
                                    dept_grouped.append({
                                        'department_id': dept.id,
                                        'department_name': dept.name,
                                        'max_value': '',
                                        'min_value': '',
                                        'conversion_value': total_offline_conversions,
                                        'actual_value': total_offline_leads
                                    })

                            year_score = score_record.with_context(
                                force_date_start=year_start,
                                force_date_end=year_end
                            )
                            year_score._compute_context_total_score()
                            lead_dep_time = year_score.context_total_score

                            overview_dept.append({
                                'start_date': year_start.strftime("%d-%m-%Y"),
                                'end_date': year_end.strftime("%d-%m-%Y"),
                                'max_value': '',
                                'min_value': '',
                                'total_actual_value': lead_dep_time,
                                "department": dept_grouped
                            })




                    else:
                        duration = end_date - start_date
                        for i in range(3):
                            period_end = end_date - (duration * i)
                            period_start = period_end - duration

                            records = request.env['crm.lead'].sudo().search([
                                ('create_date', '>=', period_start),
                                ('create_date', '<=', period_end),
                                ('stage_id', 'in', [1, 2]),
                                ('company_id', '=', user.company_id.id)
                            ])

                            dept_grouped = []
                            department = records.mapped('medium_id')
                            total_online_leads = 0
                            total_offline_leads = 0
                            total_online_conversions = 0
                            total_offline_conversions = 0
                            for dept in department:
                                dept_records = records.filtered(lambda r: r.medium_id == dept)
                                for rec in dept_records:
                                    print(rec)
                                    if rec.medium_id and rec.medium_id.name:
                                        dept_name = rec.medium_id.name.lower()
                                        if "online" in dept_name:
                                            total_online_leads += 1
                                            total_online_conversions += 1 if rec.stage_id.id == 2 else 0
                                        elif "offline" in dept_name:
                                            total_offline_leads += 1
                                            total_offline_conversions += 1 if rec.stage_id.id == 2 else 0
                                if total_online_leads >= 0 and dept.name.lower() == 'online':
                                    dept_grouped.append({
                                        'department_id': dept.id,
                                        'department_name': dept.name,
                                        'max_value': '',
                                        'min_value': '',
                                        'conversion_value': total_online_conversions,
                                        'actual_value': total_online_leads
                                    })

                                elif total_offline_leads >= 0 and dept.name.lower() == 'offline':
                                    dept_grouped.append({
                                        'department_id': dept.id,
                                        'department_name': dept.name,
                                        'max_value': '',
                                        'min_value': '',
                                        'conversion_value': total_offline_conversions,
                                        'actual_value': total_offline_leads
                                    })

                            month_score = score_record.with_context(
                                force_date_start=period_start,
                                force_date_end=period_end
                            )
                            month_score._compute_context_total_score()
                            lead_dep_time = month_score.context_total_score

                            overview_dept.append({
                                'start_date': period_start.strftime("%d-%m-%Y"),
                                'end_date': period_end.strftime("%d-%m-%Y"),
                                'max_value': '',
                                'min_value': '',
                                'total_actual_value': lead_dep_time,
                                "department": dept_grouped
                            })




                except Exception as e:
                    return json.dumps({
                        "statusCode": 500,
                        "message": "Internal Server Error"
                    })

            elif filter_type == 'WTD':
                current_week_start = today - timedelta(days=today.weekday())
                current_week_end = today

                for i in range(2, -1, -1):
                    week_start = current_week_start - timedelta(weeks=i)
                    week_end = week_start + timedelta(days=min(today.weekday(), 6))
                    print(f"Week {i}: {week_start} to {week_end}")

                    records = request.env['crm.lead'].sudo().search([
                        ('create_date', '>=', week_start.date()),
                        ('create_date', '<=', week_end.date()),
                        ('stage_id', 'in', [1, 2]),
                        ('company_id', '=', user.company_id.id)
                    ])
                    if records:
                        for i in records:
                            print(i.display_name)
                    dept_grouped = []
                    department = records.mapped('medium_id')
                    total_online_leads = 0
                    total_offline_leads = 0
                    total_online_conversions = 0
                    total_offline_conversions = 0
                    for dept in department:
                        dept_records = records.filtered(lambda r: r.medium_id == dept)
                        for rec in dept_records:
                            print(rec)
                            if rec.medium_id and rec.medium_id.name:
                                dept_name = rec.medium_id.name.lower()
                                if "online" in dept_name:
                                    total_online_leads += 1
                                    total_online_conversions += 1 if rec.stage_id.id == 2 else 0
                                elif "offline" in dept_name:
                                    total_offline_leads += 1
                                    total_offline_conversions += 1 if rec.stage_id.id == 2 else 0
                        if total_online_leads >= 0 and dept.name.lower() == 'online':
                            dept_grouped.append({
                                'department_id': dept.id,
                                'department_name': dept.name,
                                'max_value': '',
                                'min_value': '',
                                'conversion_value': total_online_conversions,
                                'actual_value': total_online_leads
                            })

                        elif total_offline_leads >= 0 and dept.name.lower() == 'offline':
                            dept_grouped.append({
                                'department_id': dept.id,
                                'department_name': dept.name,
                                'max_value': '',
                                'min_value': '',
                                'conversion_value': total_offline_conversions,
                                'actual_value': total_offline_leads
                            })

                    weekly_score = score_record.with_context(
                        force_date_start=week_start.date(),
                        force_date_end=week_end.date()
                    )
                    weekly_score._compute_context_total_score()
                    lead_dep_time = weekly_score.context_total_score

                    overview_dept.append({
                        'start_date': week_start.strftime("%d-%m-%Y"),
                        'end_date': week_end.strftime("%d-%m-%Y"),
                        'max_value': '',
                        'min_value': '',
                        'total_actual_value': lead_dep_time,
                        "department": dept_grouped
                    })


            elif filter_type == 'MTD':
                for i in range(2, -1, -1):
                    month_start = (today.replace(day=1) - relativedelta(months=i))
                    year = month_start.year
                    month = month_start.month
                    days_in_month = calendar.monthrange(year, month)[1]
                    month_end_day = min(today.day, (month_start + relativedelta(months=1) - timedelta(days=1)).day)
                    month_end = month_start.replace(day=month_end_day)
                    records = request.env['crm.lead'].sudo().search([
                        ('create_date', '>=', month_start.date()),
                        ('create_date', '<=', month_end.date()),
                        ('stage_id', 'in', [1, 2]),
                        ('company_id', '=', user.company_id.id)
                    ])
                    dept_grouped = []
                    department = records.mapped('medium_id')
                    total_online_leads = 0
                    total_offline_leads = 0
                    total_online_conversions = 0
                    total_offline_conversions = 0
                    for dept in department:
                        dept_records = records.filtered(lambda r: r.medium_id == dept)
                        for rec in dept_records:
                            print(rec)
                            if rec.medium_id and rec.medium_id.name:
                                dept_name = rec.medium_id.name.lower()
                                if "online" in dept_name:
                                    total_online_leads += 1
                                    total_online_conversions += 1 if rec.stage_id.id == 2 else 0
                                elif "offline" in dept_name:
                                    total_offline_leads += 1
                                    total_offline_conversions += 1 if rec.stage_id.id == 2 else 0
                        if total_online_leads >= 0 and dept.name.lower() == 'online':
                            dept_grouped.append({
                                'department_id': dept.id,
                                'department_name': dept.name,
                                'max_value': '',
                                'min_value': '',
                                'conversion_value': total_online_conversions,
                                'actual_value': total_online_leads
                            })

                        elif total_offline_leads >= 0 and dept.name.lower() == 'offline':
                            dept_grouped.append({
                                'department_id': dept.id,
                                'department_name': dept.name,
                                'max_value': '',
                                'min_value': '',
                                'conversion_value': total_offline_conversions,
                                'actual_value': total_offline_leads
                            })
                    monthly_score = score_record.with_context(
                        force_date_start=month_start.date(),
                        force_date_end=month_end.date()
                    )
                    monthly_score._compute_context_total_score()
                    lead_dep_time = monthly_score.context_total_score

                    overview_dept.append({
                        'start_date': month_start.strftime("%d-%m-%Y"),
                        'end_date': month_end.strftime("%d-%m-%Y"),
                        'max_value': '',
                        'min_value': '',
                        'total_actual_value': lead_dep_time,
                        "department": dept_grouped
                    })
            elif filter_type == 'YTD':
                for year_diff in range(0, 3):
                    start_date = date(today.year - year_diff, 1, 1)
                    end_date = date(today.year - year_diff, today.month, today.day)

                    records = request.env['crm.lead'].sudo().search([
                        ('create_date', '>=', start_date),
                        ('create_date', '<=', end_date),
                        ('stage_id', 'in', [1, 2]),
                        ('company_id', '=', user.company_id.id)
                    ])
                    dept_grouped = []
                    department = records.mapped('medium_id')
                    total_online_leads = 0
                    total_offline_leads = 0
                    total_online_conversions = 0
                    total_offline_conversions = 0
                    for dept in department:
                        dept_records = records.filtered(lambda r: r.medium_id == dept)
                        for rec in dept_records:
                            print(rec)
                            if rec.medium_id and rec.medium_id.name:
                                dept_name = rec.medium_id.name.lower()
                                if "online" in dept_name:
                                    total_online_leads += 1
                                    total_online_conversions += 1 if rec.stage_id.id == 2 else 0
                                elif "offline" in dept_name:
                                    total_offline_leads += 1
                                    total_offline_conversions += 1 if rec.stage_id.id == 2 else 0
                        if total_online_leads >= 0 and dept.name.lower() == 'online':
                            dept_grouped.append({
                                'department_id': dept.id,
                                'department_name': dept.name,
                                'max_value': '',
                                'min_value': '',
                                'conversion_value': total_online_conversions,
                                'actual_value': total_online_leads
                            })

                        elif total_offline_leads >= 0 and dept.name.lower() == 'offline':
                            dept_grouped.append({
                                'department_id': dept.id,
                                'department_name': dept.name,
                                'max_value': '',
                                'min_value': '',
                                'conversion_value': total_offline_conversions,
                                'actual_value': total_offline_leads
                            })
                    yearly_score = score_record.with_context(
                        force_date_start=start_date,
                        force_date_end=end_date
                    )
                    yearly_score._compute_context_total_score()
                    lead_dep_time = yearly_score.context_total_score

                    overview_dept.append({
                        'start_date': start_date.strftime("%d-%m-%Y"),
                        'end_date': end_date.strftime("%d-%m-%Y"),
                        'max_value': '',
                        'min_value': '',
                        'total_actual_value': lead_dep_time,
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
            # body = json.loads(request.httprequest.data.decode("utf-8"))
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

        score_id = int(kwargs.get("scoreId"))
        dept_id = int(kwargs.get("departmentId"))
        filter_type = kwargs.get("filterType")
        start_date_str = kwargs.get("startDate")
        end_date_str =kwargs.get("endDate")

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

        response = {
            "statusCode": 400,
            "message": "No valid operation performed"
        }

        # dept = request.env['hr.department'].sudo().browse(dept_id)
        # if not dept.exists():
        #     return request.make_response(
        #         json.dumps({"statusCode": 404, "message": "Department not found"}),
        #     )

        today = datetime.today()
        overview_employee = []

        if score_record.score_name == "Labour":
            # Custom range (unchanged)
            dept = request.env['hr.department'].sudo().browse(dept_id)

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
                        duration = end_date - start_date
                        for i in range(3):
                            period_end = end_date - (duration * i)
                            period_start = period_end - duration

                            records = request.env['labour.billing'].sudo().search([
                                ('date', '>=', period_start),
                                ('date', '<=', period_end),
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
                                    "actual_value": emp_actual_value})
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


        elif score_record.score_name == "Customer Satisfaction":
            pass

        elif score_record.score_name == "TAT":
            dept = request.env['hr.department'].sudo().browse(dept_id)

            if filter_type == "Custom" and start_date_str and end_date_str:
                try:

                    start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
                    end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()
                    print("lkjsfd")
                    #
                    if start_date > end_date:
                        return json.dumps({"statusCode": 400, "message": "Start date should be less than end date"})
                    #
                    delta = relativedelta(end_date, start_date)
                    total_months = delta.years * 12 + delta.months
                    if total_months > 3:
                        start_year = start_date.year
                        end_year = end_date.year
                        print(start_year, end_year)
                        for year in range(3):
                            year_start = date(start_year - year, start_date.month, start_date.day)
                            year_end = date(end_year - year, end_date.month, end_date.day)

                            print(year_start, year_end)

                            records = request.env['fleet.repair.work.line'].sudo().search([
                                ('repair_id.invoice_order_id', '!=', False),
                                ('repair_id.invoice_order_id.invoice_date', '!=', False),
                                ('repair_id.invoice_order_id.invoice_date', '>=', year_start),
                                ('repair_id.invoice_order_id.invoice_date', '<=', year_end),
                                ('department_type_id', '=', dept.id)
                            ])

                            emp_grouped = []
                            employees = records.mapped('employee_id')
                            for emp in employees:
                                emp_records = records.filtered(lambda r: r.employee_id == emp)
                                # print(emp_records)
                                emp_value = sum(emp_records.mapped('time_diff') or [0])
                                # print(emp_actual_value)
                                emp_job_card = list(set((emp_records.mapped('repair_id.job_card_display'))))
                                emp_actual_value = emp_value / (24 * len(emp_job_card))
                                request.env.cr.execute("SELECT name FROM hr_employee WHERE id=%s", (emp.id,))
                                emp_name = request.env.cr.fetchone()
                                emp_name = emp_name[0] if emp_name else "N/A"
                                emp_grouped.append({
                                    "employee_id": emp.id,
                                    "employee_name": emp_name,
                                    "actual_value": round(emp_actual_value, 2)
                                })
                                # print(emp_grouped)

                            year_score = score_record.with_context(
                                force_date_start=year_start,
                                force_date_end=year_end
                            )

                            year_score._compute_context_total_score()
                            tat_emp_time = year_score.context_total_score

                            overview_employee.append({
                                "year": f"{year_start.year}",
                                "start_date": f"{year_start.strftime('%d-%m-%Y')}",
                                "end_date": f"{year_end.strftime('%d-%m-%Y')}",
                                "total_actual_value": round(tat_emp_time, 2),
                                "employees": emp_grouped
                            })

                    else:
                        duration = end_date - start_date
                        for i in range(3):
                            period_end = end_date - (duration * i)
                            period_start = period_end - duration

                            records = request.env['fleet.repair.work.line'].sudo().search([
                                ('repair_id.invoice_order_id', '!=', False),
                                ('repair_id.invoice_order_id.invoice_date', '!=', False),
                                ('repair_id.invoice_order_id.invoice_date', '>=', period_start),
                                ('repair_id.invoice_order_id.invoice_date', '<=', period_end),
                                ('department_type_id', '=', dept.id)
                            ])
                            emp_grouped = []
                            employees = records.mapped('employee_id')
                            for emp in employees:
                                emp_records = records.filtered(lambda r: r.employee_id == emp)
                                emp_value = sum(emp_records.mapped('time_diff') or [0])
                                emp_job_card = list(set((emp_records.mapped('repair_id.job_card_display'))))
                                emp_actual_value = emp_value / (24 * len(emp_job_card))
                                request.env.cr.execute("SELECT name FROM hr_employee WHERE id=%s", (emp.id,))
                                emp_name = request.env.cr.fetchone()
                                emp_name = emp_name[0] if emp_name else "N/A"
                                emp_grouped.append({
                                    "employee_id": emp.id,
                                    "employee_name": emp_name,
                                    "actual_value": round(emp_actual_value, 2)
                                })

                            year_score = score_record.with_context(
                                force_date_start=period_start,
                                force_date_end=period_end
                            )
                            year_score._compute_context_total_score()
                            tat_emp_time = year_score.context_total_score
                            overview_employee.append({
                                "start_date": f"{period_start.strftime('%d-%m-%Y')}",
                                "end_date": f"{period_end.strftime('%d-%m-%Y')}",
                                "total_actual_value": round(tat_emp_time, 2),
                                "employees": emp_grouped
                            })



                except Exception as e:
                    return json.dumps({
                        "statusCode": 500,
                        "message": "Internal Server Error"
                    })
            elif filter_type == "WTD":
                current_week_start = today - timedelta(days=today.weekday())
                current_week_end = today

                for i in range(2, -1, -1):
                    week_start = current_week_start - timedelta(weeks=i)
                    week_end = week_start + timedelta(days=min(today.weekday(), 6))

                    records = request.env['fleet.repair.work.line'].sudo().search([
                        ('repair_id.invoice_order_id', '!=', False),
                        ('repair_id.invoice_order_id.invoice_date', '!=', False),
                        ('repair_id.invoice_order_id.invoice_date', '>=', week_start),
                        ('repair_id.invoice_order_id.invoice_date', '<=', week_end),
                        ('department_type_id', '=', dept.id)
                    ])

                    emp_grouped = []
                    employees = records.mapped('employee_id')
                    for emp in employees:
                        emp_records = records.filtered(lambda r: r.employee_id == emp)
                        emp_value = sum(emp_records.mapped('time_diff') or [0])
                        emp_job_card = list(set((emp_records.mapped('repair_id.job_card_display'))))
                        emp_actual_value = emp_value / (24 * len(emp_job_card))
                        request.env.cr.execute("SELECT name FROM hr_employee WHERE id=%s", (emp.id,))
                        emp_name = request.env.cr.fetchone()
                        emp_name = emp_name[0] if emp_name else "N/A"
                        emp_grouped.append({
                            "employee_id": emp.id,
                            "employee_name": emp_name,
                            "actual_value": round(emp_actual_value, 2)
                        })

                    week_score = score_record.with_context(
                        force_date_start=week_start,
                        force_date_end=week_end
                    )

                    week_score._compute_context_total_score()
                    tat_emp_time = week_score.context_total_score

                    overview_employee.append({
                        "start_date": f"{week_start.strftime('%d-%m-%Y')}",
                        "end_date": f"{week_end.strftime('%d-%m-%Y')}",
                        "max_value": "",
                        "min_value": "",
                        "total_actual_value": round(tat_emp_time, 2),
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

                    records = request.env['fleet.repair.work.line'].sudo().search([
                        ('repair_id.invoice_order_id', '!=', False),
                        ('repair_id.invoice_order_id.invoice_date', '!=', False),
                        ('repair_id.invoice_order_id.invoice_date', '>=', month_start),
                        ('repair_id.invoice_order_id.invoice_date', '<=', month_end),
                        ('department_type_id', '=', dept.id)
                    ])

                    emp_grouped = []
                    employees = records.mapped('employee_id')
                    for emp in employees:
                        emp_records = records.filtered(lambda r: r.employee_id == emp)
                        emp_value = sum(emp_records.mapped('time_diff') or [0])
                        emp_job_card = list(set((emp_records.mapped('repair_id.job_card_display'))))
                        emp_actual_value = emp_value / (24 * len(emp_job_card))
                        request.env.cr.execute("SELECT name FROM hr_employee WHERE id=%s", (emp.id,))
                        emp_name = request.env.cr.fetchone()
                        emp_name = emp_name[0] if emp_name else "N/A"
                        emp_grouped.append({
                            "employee_id": emp.id,
                            "employee_name": emp_name,
                            "actual_value": round(emp_actual_value, 2)
                        })

                    month_score = score_record.with_context(
                        force_date_start=month_start,
                        force_date_end=month_end
                    )

                    month_score._compute_context_total_score()
                    tat_emp_time = month_score.context_total_score

                    overview_employee.append({
                        "start_date": f"{month_start.strftime('%d-%m-%Y')}",
                        "end_date": f"{month_end.strftime('%d-%m-%Y')}",
                        "max_value": "",
                        "min_value": "",
                        "total_actual_value": round(tat_emp_time, 2),
                        "employees": emp_grouped
                    })



            elif filter_type == "YTD":
                for year_diff in range(0, 3):
                    start_date = date(today.year - year_diff, 1, 1)
                    end_date = date(today.year - year_diff, today.month, today.day)

                    records = request.env['fleet.repair.work.line'].sudo().search([
                        ('repair_id.invoice_order_id', '!=', False),
                        ('repair_id.invoice_order_id.invoice_date', '!=', False),
                        ('repair_id.invoice_order_id.invoice_date', '>=', start_date),
                        ('repair_id.invoice_order_id.invoice_date', '<=', end_date),
                        ('department_type_id', '=', dept.id)
                    ])
                    emp_grouped = []
                    employees = records.mapped('employee_id')
                    for emp in employees:
                        emp_records = records.filtered(lambda r: r.employee_id == emp)
                        emp_value = sum(emp_records.mapped('time_diff') or [0])
                        emp_job_card = list(set((emp_records.mapped('repair_id.job_card_display'))))
                        emp_actual_value = emp_value / (24 * len(emp_job_card))
                        request.env.cr.execute("SELECT name FROM hr_employee WHERE id=%s", (emp.id,))
                        emp_name = request.env.cr.fetchone()
                        emp_name = emp_name[0] if emp_name else "N/A"
                        emp_grouped.append({
                            "employee_id": emp.id,
                            "employee_name": emp_name,
                            "actual_value": round(emp_actual_value, 2)
                        })

                    overview_employee.append({
                        "year": f"{start_date.year}",
                        "start_date": f"{start_date.strftime('%d-%m-%Y')}",
                        "end_date": f"{end_date.strftime('%d-%m-%Y')}",
                        "max_value": "",
                        "min_value": "",
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




        elif score_record.score_name == "Leads":
            medium = request.env['utm.medium'].sudo().browse(dept_id)
            # source_grouped = []
            medium_grouped=[]
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
                            total_lead=0
                            total_converted_value=0
                            source_grouped = []
                            year_start = date(start_year - year, start_date.month, start_date.day)
                            year_end = date(end_year - year, end_date.month, end_date.day)
                            records = request.env['crm.lead'].sudo().search([
                                ('create_date', '>=', year_start),
                                ('create_date', '<=', year_end),
                                ('stage_id', 'in', [1, 2]),
                                ('medium_id', '=', medium.id)

                            ])

                            # source_grouped = []
                            sources = records.mapped('source_id')
                            for s in sources:
                                print(s.name)
                                source_records = records.filtered(lambda r: r.source_id == s)
                                source_value = len(source_records)
                                converted_source_value=len(source_records.filtered(lambda r: r.stage_id.id == 2))
                                total_converted_value += converted_source_value
                                source_grouped.append({
                                    "source_id":s.id,
                                    "source_name":s.name,
                                    "max_value":"",
                                    "min_value":"",
                                    "conversion_value":converted_source_value,
                                    "lead_value": source_value
                                })
                                total_lead+=source_value



                            medium_grouped.append({
                                "start_date": f"{year_start.strftime('%d-%m-%Y')}",
                                "end_date": f"{year_end.strftime('%d-%m-%Y')}",
                                "max_value":"",
                                "min_value":"",
                                "total_conversion_value":total_converted_value,
                                "total_lead_value":total_lead,
                                "sources":source_grouped
                            })




                    else:
                        duration = end_date - start_date
                        for i in range(3):
                            total_lead = 0
                            total_converted_value=0
                            source_grouped = []
                            period_end = end_date - (duration * i)
                            period_start = period_end - duration
                            records = request.env['crm.lead'].sudo().search([
                                ('create_date', '>=', period_start),
                                ('create_date', '<=', period_end),
                                ('stage_id', 'in', [1, 2]),
                                ('medium_id', '=', medium.id)
                            ])
                            sources=records.mapped('source_id')
                            for s in sources:
                                source_records = records.filtered(lambda r: r.source_id == s)
                                source_value = len(source_records)
                                converted_source_value=len(source_records.filtered(lambda r: r.stage_id.id == 2))
                                total_converted_value += converted_source_value
                                source_grouped.append({
                                    "source_id":s.id,
                                    "source_name":s.name,
                                    "max_value":"",
                                    "min_value":"",
                                    "conversion_value":converted_source_value,
                                    "lead_value": source_value
                                })
                                total_lead+=source_value
                            medium_grouped.append({
                                "start_date": f"{period_start.strftime('%d-%m-%Y')}",
                                "end_date": f"{period_end.strftime('%d-%m-%Y')}",
                                "max_value":"",
                                "min_value":"",
                                "total_converted_value":total_converted_value,
                                "total_lead_value":total_lead,
                                "sources":source_grouped
                            })



                except Exception as e:
                    return json.dumps({
                        "statusCode": 500,
                        "message": "Internal Server Error"
                    })

            elif filter_type == "WTD":
                current_week_start = today - timedelta(days=today.weekday())
                current_week_end = today
                medium_grouped=[]
                for i in range(2,-1,-1):
                    total_lead = 0
                    total_converted_value=0
                    source_grouped=[]
                    week_start = current_week_start - timedelta(weeks=i)
                    week_end = week_start + timedelta(days=today.weekday())
                    records= request.env['crm.lead'].sudo().search([
                        ('create_date', '>=', week_start.date()),
                        ('create_date', '<=', week_end.date()),
                        ('stage_id', 'in', [1, 2]),
                        ('medium_id', '=', medium.id)
                    ])
                    sources=records.mapped('source_id')
                    for s in sources:
                        source_records=records.filtered(lambda r: r.source_id == s)
                        source_value = len(source_records)
                        converted_source_value=len(source_records.filtered(lambda r: r.stage_id.id == 2))
                        total_converted_value += converted_source_value
                        source_grouped.append({
                            "source_id":s.id,
                            "source_name":s.name,
                            "max_value":"",
                            "min_value":"",
                            "conversion_value":converted_source_value,
                            "lead_value": source_value
                        })
                        total_lead += source_value

                    medium_grouped.append({
                        "start_date": f"{week_start.strftime('%d-%m-%Y')}",
                        "end_date": f"{week_end.strftime('%d-%m-%Y')}",
                        "max_value":"",
                        "min_value":"",
                        "total_converted_value":total_converted_value,
                        "total_lead_value":total_lead,
                        "sources":source_grouped
                    })




            elif filter_type == "MTD" or not filter_type:
                medium_grouped = []
                for i in range(2,-1,-1):
                    source_grouped=[]
                    total_lead=0
                    total_converted=0
                    month_start = (today.replace(day=1) - relativedelta(months=i))
                    year = month_start.year
                    month = month_start.month
                    days_in_month = calendar.monthrange(year, month)[1]
                    month_end_day = min(today.day, (month_start + relativedelta(months=1) - timedelta(days=1)).day)
                    month_end = month_start.replace(day=month_end_day)

                    records=request.env['crm.lead'].sudo().search([
                        ('create_date', '>=', month_start.date()),
                        ('create_date', '<=', month_end.date()),
                        ('stage_id', 'in', [1, 2]),
                        ('medium_id', '=', medium.id)
                    ])
                    sources=records.mapped('source_id')
                    for s in sources:
                        source_records=records.filtered(lambda r: r.source_id == s)
                        source_value = len(source_records)
                        converted_source_value=len(source_records.filtered(lambda r: r.stage_id.id == 2))
                        total_converted += converted_source_value
                        source_grouped.append({
                            "source_id":s.id,
                            "source_name":s.name,
                            "max_value":"",
                            "min_value":"",
                            "conversion_value":converted_source_value,
                            "lead_value": source_value
                        })
                        total_lead += source_value

                    medium_grouped.append({
                        "start_date": f"{month_start.strftime('%d-%m-%Y')}",
                        "end_date": f"{month_end.strftime('%d-%m-%Y')}",
                        "max_value":"",
                        "min_value":"",
                        "total_converted_value":total_converted,
                        "total_lead_value":total_lead,
                        "sources":source_grouped
                    })




            elif filter_type == "YTD":
                medium_grouped=[]
                for year_diff in range(0,3):
                    total_lead=0
                    total_converted=0
                    source_grouped=[]
                    start_date = date(today.year - year_diff, 1, 1)
                    end_date = date(today.year - year_diff, today.month, today.day)

                    records=request.env['crm.lead'].sudo().search([
                        ('create_date', '>=', start_date),
                        ('create_date', '<=', end_date),
                        ('stage_id', 'in', [1, 2]),
                        ('medium_id', '=', medium.id)
                    ])
                    sources=records.mapped('source_id')
                    for s in sources:
                        source_records=records.filtered(lambda r: r.source_id == s)
                        source_value = len(source_records)
                        converted_source_value=len(source_records.filtered(lambda r: r.stage_id.id == 2))
                        total_converted += converted_source_value
                        source_grouped.append({
                            "source_id":s.id,
                            "source_name":s.name,
                            "max_value":"",
                            "min_value":"",
                            "conversion_value":converted_source_value,
                            "lead_value": source_value
                        })
                        total_lead += source_value

                    medium_grouped.append({
                        "start_date": f"{start_date.strftime('%d-%m-%Y')}",
                        "end_date": f"{end_date.strftime('%d-%m-%Y')}",
                        "max_value":"",
                        "min_value":"",
                        "total_converted_value":total_converted,
                        "total_lead_value":total_lead,
                        "sources":source_grouped
                    })


            response = {
                "statusCode": 200,
                "message": "Employee Overview",
                "score_id": score_id,
                "score_name": score_record.score_name,
                "department_id": medium.id,
                "department_name": medium.name,
                "overview_source": medium_grouped
            }

        return request.make_response(
            json.dumps(response),
            headers=[('Content-Type', 'application/json')]
        )



    # response = {
    #     "statusCode": 200,
    #     "message": "Employee Overview",
    #     "score_id": score_id,
    #     "score_name": score_record.score_name,
    #     "department_id": medium.id,
    #     "department_name": medium.name,
    #     "overview_employee": overview_employee
    # }
