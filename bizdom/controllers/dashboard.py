import json
from datetime import date, datetime, timedelta
from odoo import http
from odoo.http import request
import jwt

SECRET_KEY = "Your-secret-key"


class BizdomDashboard(http.Controller):

    def _batch_compute_scores(self, pillar_records, start_date, end_date, favorites_only, company_id):
        """
        Batch compute all scores for all pillars in one operation.
        This eliminates N+1 queries by computing all scores together.
        
        Returns: Dictionary mapping pillar_id -> list of score dictionaries
        """
        # Collect all score IDs from all pillars
        all_score_ids = []
        pillar_scores_map = {}  # Track which scores belong to which pillar
        
        for p in pillar_records:
            # Get scores based on favoritesOnly parameter
            if favorites_only:
                score_records = request.env['bizdom.score'].sudo().search([
                    ('pillar_id', '=', p.id),
                    ('favorite', '=', True),
                    ('company_id', '=', company_id)
                ])
            else:
                score_records = p.score_name_ids  # All scores (original logic)
            
            # Store score IDs with pillar reference
            for s in score_records:
                all_score_ids.append(s.id)
                if p.id not in pillar_scores_map:
                    pillar_scores_map[p.id] = []
                pillar_scores_map[p.id].append(s)
        
        # Batch compute all scores with same date range using context
        # Create a mapping of score IDs to context-enabled records for lookup
        score_id_to_context_record = {}
        if all_score_ids:
            # Create a single recordset from all score IDs
            all_scores = request.env['bizdom.score'].sudo().browse(all_score_ids)
            scores_with_context = all_scores.with_context(
                force_date_start=start_date,
                force_date_end=end_date
            )
            # Trigger batch computation - this computes all scores in optimized batches
            scores_with_context._compute_context_total_score()
            
            # Create mapping for quick lookup
            for s_ctx in scores_with_context:
                score_id_to_context_record[s_ctx.id] = s_ctx
        
        # Build results grouped by pillar
        result = {}
        for pillar_id, score_list in pillar_scores_map.items():
            pillar_scores = []
            for s in score_list:
                # Get the context-enabled record to access computed value
                s_ctx = score_id_to_context_record.get(s.id, s)
                score_value = s_ctx.context_total_score if hasattr(s_ctx, 'context_total_score') else 0.0
                
                if s.type == "percentage":
                    min_value = s.min_score_percentage
                    max_value = s.max_score_percentage
                else:
                    min_value = s.min_score_number
                    max_value = s.max_score_number
                
                pillar_scores.append({
                    "score_id": s.id,
                    "score_name": s.score_name,
                    "type": s.type,
                    "min_value": min_value,
                    "max_value": max_value,
                    "total_score_value": round(score_value, 2)
                })
            result[pillar_id] = pillar_scores
        
        return result

    @http.route('/api/dashboard', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def get_dashboard(self, **kwargs):
        # Support both JWT token and session-based auth
        auth_header = request.httprequest.headers.get("Authorization")
        uid = False
        
        if auth_header:
            # Strip "Bearer " if present
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
            else:
                token = auth_header

            try:
                if not token:
                    return json.dumps({"statusCode": 401, "message": "Token missing"})
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
        else:
            # Fallback to session-based auth for internal dashboard
            uid = request.session.uid
        
        if not uid:
            return json.dumps({"statusCode": 401, "message": "Token missing"})

        # start_date_str = body.get("startDate")
        # end_date_str = body.get("endDate")
        # filter_type = body.get("filterType")

        # Get date range from request or set default
        start_date_str = kwargs.get("startDate")
        end_date_str = kwargs.get("endDate")
        filter_type = kwargs.get("filterType")
        favorites_only = kwargs.get("favoritesOnly", "false").lower() == "true"  # Optional parameter to filter favorites

        # Removed debug print statements

        # if not start_date_str or not end_date_str:
        #     today = date.today()
        #     start_date = today.replace(day=1)  # 1st day of current month
        #     end_date = today
        # else:
        #     start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
        #     end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()

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

                pillar_records = request.env['bizdom.pillar'].sudo().search([
                    ('company_id', '=', company.id)
                ])

                # Batch compute all scores at once
                pillar_scores_map = self._batch_compute_scores(
                    pillar_records, start_date, end_date, favorites_only, company.id
                )

                # Build response
                pillars = []
                for p in pillar_records:
                    pillars.append({
                        "pillar_id": p.id,
                        "pillar_name": p.name,
                        "scores": pillar_scores_map.get(p.id, [])
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

            except ValueError:
                return json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"})

        elif filter_type == "WTD":
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            if today.weekday() == 6:  # Sunday
                week_start = today - timedelta(days=6)
            week_end = today if today.weekday() < 6 else today - timedelta(days=(today.weekday() - 4))

            try:
                pillar_records = request.env['bizdom.pillar'].sudo().search([
                    ('company_id', '=', company.id)
                ])

                # Batch compute all scores at once
                pillar_scores_map = self._batch_compute_scores(
                    pillar_records, week_start, week_end, favorites_only, company.id
                )

                # Build response
                pillars = []
                for p in pillar_records:
                    pillars.append({
                        "pillar_id": p.id,
                        "pillar_name": p.name,
                        "scores": pillar_scores_map.get(p.id, [])
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
            pillar_records = request.env['bizdom.pillar'].sudo().search([
                ('company_id', '=', company.id)
            ])

            # Batch compute all scores at once
            pillar_scores_map = self._batch_compute_scores(
                pillar_records, month_start, month_end, favorites_only, company.id
            )

            # Build response
            pillars = []
            for p in pillar_records:
                pillars.append({
                    "pillar_id": p.id,
                    "pillar_name": p.name,
                    "scores": pillar_scores_map.get(p.id, [])
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
            pillar_records = request.env['bizdom.pillar'].sudo().search([
                ('company_id', '=', company.id)
            ])

            # Batch compute all scores at once
            pillar_scores_map = self._batch_compute_scores(
                pillar_records, year_start, year_end, favorites_only, company.id
            )

            # Build response
            pillars = []
            for p in pillar_records:
                pillars.append({
                    "pillar_id": p.id,
                    "pillar_name": p.name,
                    "scores": pillar_scores_map.get(p.id, [])
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

    # controllers/dashboard.py
    # @http.route('/bizdom/score-dashboard/client-action', type='json', auth='user')
    # def score_dashboard_client_action(self, score_id, **kw):
    #     score = request.env['bizdom.score'].browse(int(score_id))
    #     if not score.exists():
    #         return {'error': 'Score not found'}
    #
    #     return {
    #         'type': 'ir.actions.client',
    #         'tag': 'bizdom_score_dashboard',
    #         'name': f'{score.score_name} Dashboard',
    #         'params': {
    #             'scoreId': score.id,
    #             'scoreName': score.score_name
    #         }
    #     }

    # Fetch pillar data