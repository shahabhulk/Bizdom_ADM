from datetime import date, datetime
from odoo import http
from odoo.http import request
import jwt

SECRET_KEY = "Your-secret-key"

class BizdomDashboard(http.Controller):

    @http.route('/api/dashboard', type='json', auth='none', methods=['POST'], csrf=False)
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
        start_date_str = kwargs.get("startDate")
        end_date_str = kwargs.get("endDate")

        if not start_date_str or not end_date_str:
            today = date.today()
            start_date = today.replace(day=1)  # 1st day of current month
            end_date = today
        else:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        # Get the logged-in user
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
                })
            pillers.append({
                "id": p.id,
                "piller_name": p.name,
                "scores": scores
            })

        return {
            "statusCode": 200,
            "message": "Pillers and scores data fetched",
            "company_name": company.name,
            "company_id": company.id,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "pillers": pillers
        }
