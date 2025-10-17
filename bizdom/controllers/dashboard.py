import json
from datetime import date, datetime, timedelta
from odoo import http
from odoo.http import request
import jwt

SECRET_KEY = "Your-secret-key"


class BizdomDashboard(http.Controller):

    @http.route('/api/dashboard', type='http', auth='none', methods=['POST'], csrf=False)
    def get_dashboard(self, **kwargs):
        # Get JWT token from headers
        auth_header = request.httprequest.headers.get("Authorization")
        if not auth_header:
            return json.dumps({"statusCode": 401, "message": "Token missing"})

        # Strip "Bearer " if present
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = auth_header

        try:
            if not token:
                return json.dumps({"statusCode": 401, "message": "Token missing"})
            body = json.loads(request.httprequest.data.decode("utf-8"))
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            # Handle both plain integer uid and dict from login payload
            if isinstance(payload.get("uid"), dict):
                uid = payload["uid"].get("uid")
            else:
                uid = payload.get("uid")
        except jwt.ExpiredSignatureError:
            return json.dumps({"statusCode": 401, "message": "Token expired"})

        except jwt.InvalidTokenError:
            return json.dumps({"statusCode": 401, "message": "Invalid token"})

        # Get date range from request or set default
        start_date_str = body.get("startDate")
        end_date_str = body.get("endDate")
        filter_type = body.get("filterType")

        print("request", start_date_str)
        print("request", end_date_str)

        if not start_date_str or not end_date_str:
            today = date.today()
            start_date = today.replace(day=1)  # 1st day of current month
            end_date = today
        else:
            start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
            end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()

        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists():
            return json.dumps({"statusCode": 404, "message": "User not found"})

        company = user.company_id

        if filter_type == "Custom" and start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
                end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()
                if start_date > end_date:
                    return json.dumps({"statusCode": 400, "message": "Start date should be less than end date"})

                pillars = []
                pillar_records = request.env['bizdom.pillar'].sudo().search([
                    ('company_id', '=', company.id)
                ])

                for p in pillar_records:
                    scores = []
                    for s in p.score_name_ids:
                        result = request.env['bizdom.score']._recompute_with_dates(
                            s, start_date, end_date
                        )
                        score_value = result['value']
                        if s.type == "percentage":
                            min_value = s.min_score_percentage
                            max_value = s.max_score_percentage
                        else:
                            min_value = s.min_score_number
                            max_value = s.max_score_number

                        scores.append({
                            "score_id": s.id,
                            "score_name": s.score_name,
                            "type": s.type,
                            "min_value": min_value,
                            "max_value": max_value,
                            "total_score_value": score_value * 100 if s.type == "percentage" else score_value
                        })
                    pillars.append({
                        "pillar_id": p.id,
                        "pillar_name": p.name,
                        "scores": scores
                    })

                response = {
                    "statusCode": 200,
                    "message": "Data fetched",
                    "company_id": company.id,
                    "start_date": start_date.strftime("%d-%m-%Y"),
                    "end_date": end_date.strftime("%d-%m-%Y"),
                    "pillars": pillars
                }

                return http.Response(
                    json.dumps(response),
                    content_type='application/json',
                    status=200
                )
            except Exception as e:
                return json.dumps({"statusCode": 500, "message": "Invalid date range"})

        elif filter_type == "WTD":
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            if today.weekday() == 6:  # Sunday
                week_start = today - timedelta(days=6)
            week_end = today if today.weekday() < 6 else today - timedelta(days=(today.weekday() - 4))

            try:
                pillars = []
                pillar_records = request.env['bizdom.pillar'].sudo().search([
                    ('company_id', '=', company.id)
                ])

                for p in pillar_records:
                    scores = []

                    for s in p.score_name_ids:
                        result = request.env['bizdom.score']._recompute_with_dates(
                            s, week_start, week_end
                        )
                        score_value = result['value']

                        if s.type == "percentage":
                            min_value = s.min_score_percentage
                            max_value = s.max_score_percentage
                        else:
                            min_value = s.min_score_number
                            max_value = s.max_score_number

                        scores.append({
                            "score_id": s.id,
                            "score_name": s.score_name,
                            "type": s.type,
                            "min_value": min_value,
                            "max_value": max_value,
                            "total_score_value":score_value * 100 if s.type == "percentage" else score_value
                        })
                    pillars.append({
                        "pillar_id": p.id,
                        "pillar_name": p.name,
                        "scores": scores
                    })

                response = {
                    "statusCode": 200,
                    "message": "Data fetched",
                    "company_id": company.id,
                    "start_date": week_start.strftime("%d-%m-%Y"),
                    "end_date": week_end.strftime("%d-%m-%Y"),
                    "pillars": pillars
                }

                return http.Response(
                    json.dumps(response),
                    content_type='application/json',
                    status=200
                )

            except Exception as e:
                return json.dumps({"statusCode": 500, "message": "Error processing WTD data"})



        elif filter_type == "MTD" or not filter_type:
            month_start = date.today().replace(day=1)
            month_end = date.today()
            pillars = []
            pillar_records = request.env['bizdom.pillar'].sudo().search([
                ('company_id', '=', company.id)
            ])
            for p in pillar_records:
                scores = []
                for s in p.score_name_ids:
                    result = request.env['bizdom.score']._recompute_with_dates(
                        s, month_start, month_end
                    )
                    score_value = result['value']

                    if s.type == "percentage":
                        min_value = s.min_score_percentage
                        max_value = s.max_score_percentage
                    else:
                        min_value = s.min_score_number
                        max_value = s.max_score_number
                    scores.append({
                        "score_id": s.id,
                        "score_name": s.score_name,
                        "type": s.type,
                        "min_value": min_value,
                        "max_value": max_value,
                        "total_score_value": score_value * 100 if s.type == "percentage" else score_value                    })
                pillars.append({
                    "pillar_id": p.id,
                    "pillar_name": p.name,
                    "scores": scores

                })
            response = {
                "statusCode": 200,
                "message": "Data fetched",
                "company_id": company.id,
                "start_date": month_start.strftime("%d-%m-%Y"),
                "end_date": month_end.strftime("%d-%m-%Y"),
                "pillars": pillars
            }
            return http.Response(
                json.dumps(response),
                content_type='application/json',
                status=200
            )

        elif filter_type == "YTD":
            today = date.today()
            year_start = date(today.year, 1, 1)  # January 1st of current year
            year_end = today
            pillars = []
            pillar_records = request.env['bizdom.pillar'].sudo().search([
                ('company_id', '=', company.id)
            ])

            for p in pillar_records:
                scores = []
                for s in p.score_name_ids:
                    result = request.env['bizdom.score']._recompute_with_dates(
                        s, year_start, year_end
                    )
                    score_value = result['value']

                    if s.type == "percentage":
                        min_value = s.min_score_percentage
                        max_value = s.max_score_percentage
                    else:
                        min_value = s.min_score_number
                        max_value = s.max_score_number

                    scores.append({
                        "score_id": s.id,
                        "score_name": s.score_name,
                        "type": s.type,
                        "min_value": min_value,
                        "max_value": max_value,
                        "total_score_value": score_value * 100 if s.type == "percentage" else score_value
                    })
                pillars.append({
                    "pillar_id": p.id,
                    "pillar_name": p.name,
                    "scores": scores
                })

            response = {
                "statusCode": 200,
                "message": "Data fetched",
                "company_id": company.id,
                "start_date": year_start.strftime("%d-%m-%Y"),
                "end_date": year_end.strftime("%d-%m-%Y"),
                "pillars": pillars
            }
            return http.Response(
                json.dumps(response),
                content_type='application/json',
                status=200
            )

    # Fetch pillar data
