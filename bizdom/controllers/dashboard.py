import json
from datetime import date, datetime
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
            return {"statusCode": 401, "message": "Token missing"}

        # Strip "Bearer " if present
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = auth_header




        try:
            body = json.loads(request.httprequest.data.decode("utf-8"))
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            # Handle both plain integer uid and dict from login payload
            if isinstance(payload.get("uid"), dict):
                uid = payload["uid"].get("uid")
            else:
                uid = payload.get("uid")
        except jwt.ExpiredSignatureError:
            return {"statusCode": 401, "message": "Token expired"}
        except jwt.InvalidTokenError:
            return {"statusCode": 401, "message": "Invalid token"}

        # Get date range from request or set default
        start_date_str = body.get("startDate")
        end_date_str = body.get("endDate")
        print("request",start_date_str)
        print("request",end_date_str)

        if not start_date_str or not end_date_str:
            today = date.today()
            start_date = today.replace(day=1)  # 1st day of current month
            end_date = today
        else:
            start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
            end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()

        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists():
            return {"statusCode": 404, "message": "User not found"}

        company = user.company_id

        # Fetch pillar data
        pillers = []
        piller_records = request.env['bizdom.pillar'].sudo().search([
            ('company_id', '=', company.id)
        ])

        for p in piller_records:
            scores = []
            for s in p.score_name_ids:
                s.start_date=start_date
                s.end_date=end_date
                print(s.start_date)
                print(s.end_date)
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
                    "total_score_value":s.total_score_value
                })
            pillers.append({
                "pillar_id": p.id,
                "pillar_name": p.name,
                "scores": scores
            })


        response={
            "statusCode":200,
            "message":"Data fetched",
            "company_id":company.id,
            "pillars":pillers
        }

        return http.Response(
            json.dumps(response),
            content_type='application/json',
            status=200
        )
