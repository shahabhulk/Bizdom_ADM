import json
from datetime import date, datetime, timedelta
from odoo import http
from odoo.http import request
import jwt
from ..utils.q1_helpers import Q1Helpers

SECRET_KEY = "Your-secret-key"


def _cors_headers():
    return [
        ('Access-Control-Allow-Origin', '*'),
        ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
        ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
    ]


# Odoo automatically adds CORS headers when cors='*' is set in route decorator
# So _with_cors is no longer needed - keeping for backward compatibility but it does nothing
def _with_cors(response):
    return response


class BizdomDashboard(http.Controller):

    def _get_pillar_domain(self, company_id, is_owner, allowed_pillar_ids):
        domain = [('company_id', '=', company_id)]
        if not is_owner:
            domain.append(('id', 'in', allowed_pillar_ids))
        return domain
    def _batch_compute_scores(
        self,
        pillar_records,
        start_date,
        end_date,
        favorites_only,
        company_id,
        filter_type=None,
        is_owner=False,
        allowed_pillar_ids=None,
    ):
        """
        Batch compute all scores for all pillars in one operation.
        This eliminates N+1 queries by computing all scores together.
        
        Returns: Dictionary mapping pillar_id -> list of score dictionaries
        """
        # Collect all score IDs from all pillars
        all_score_ids = []
        pillar_scores_map = {}  # Track which scores belong to which pillar
        
        allowed_pillar_ids = allowed_pillar_ids or []
        # this is the allowed pillar ids that are passed in the request its a list of pillar ids from get_dashboard_data
        # if allowed_pillar_ids is not passed then it will be empty
        for p in pillar_records:
            # Get scores based on favoritesOnly parameter
            score_domain = [
                ('pillar_id', '=', p.id),
                ('company_id', '=', company_id),
            ]
            if not is_owner:
                score_domain.append(('pillar_id', 'in', allowed_pillar_ids))
            if favorites_only:
                score_records = request.env['bizdom.score'].sudo().search(score_domain + [('favorite', '=', True)])
            else:
                score_records = request.env['bizdom.score'].sudo().search(score_domain)
            
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
                
                # Special handling for TAT: Only show Delivered TAT (not pending) in dashboard
                if s.score_name == "TAT":
                    score_value = self._calculate_delivered_tat_only(start_date, end_date, company_id)
                
                # if s.score_name == "Labour" and filter_type:
                #     min_value, max_value = Q1Helpers.calculate_min_max(
                #         s, filter_type, start_date, end_date
                #     )
                #     if min_value is None:
                #         min_value = 0
                #     if max_value is None:
                #         max_value = 0
                if s.type == "percentage":
                    min_value = s.min_score_percentage
                    max_value = s.max_score_percentage
                else:
                    min_value = s.min_score_number
                    max_value = s.max_score_number
                    
                pillar_scores.append({
                    "score_id": s.id,
                    "score_name": s.score_name,
                    "score_identifier":s.score_identifier,
                    "type": s.type,
                    "min_value": min_value,
                    "max_value": max_value,
                    "total_score_value": round(score_value, 2)
                })
            result[pillar_id] = pillar_scores
        
        return result

    def _calculate_delivered_tat_only(self, start_date, end_date, company_id):
        """
        Calculate TAT using only delivered records (excludes pending TAT).
        This is used specifically for the /api/dashboard endpoint.
        """
        repair_delivered_records = request.env['fleet.repair'].sudo().search([
            ('invoice_order_id', '!=', False),
            ('invoice_order_id.invoice_date', '!=', False),
            ('invoice_order_id.invoice_date', '>=', start_date),
            ('invoice_order_id.invoice_date', '<=', end_date),
            ('company_id', '=', company_id),
            ('invoice_order_id.state','=','posted')
        ])
        
        total_delivered_tat_days = 0.0
        valid_delivered_records = 0
        
        for repair in repair_delivered_records:
            if repair.receipt_date and repair.invoice_order_id.invoice_date:
                receipt_date = repair.receipt_date.date() if hasattr(repair.receipt_date, 'date') else repair.receipt_date
                invoice_date = repair.invoice_order_id.invoice_date.date() if hasattr(
                    repair.invoice_order_id.invoice_date, 'date') else repair.invoice_order_id.invoice_date
                delta = invoice_date - receipt_date
                total_delivered_tat_days += abs(delta.days)
                valid_delivered_records += 1
        
        # Calculate average using only delivered records
        delivered_tat = (total_delivered_tat_days / valid_delivered_records) if valid_delivered_records > 0 else 0.0
        return delivered_tat

    @http.route('/api/dashboard', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def get_dashboard(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _with_cors(http.Response(""))
        # Support both JWT token and session-based auth
        auth_header = request.httprequest.headers.get("Authorization")
        uid = False
        
        if auth_header:
            # External API call - require JWT token only (no session fallback)
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
            else:
                token = auth_header

            try:
                if not token:
                    return _with_cors(http.Response(
                        json.dumps({"statusCode": 401, "message": "Token missing"}),
                        content_type='application/json',
                        status=401
                    ))
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                # Handle both plain integer uid and dict from login payload
                if isinstance(payload.get("uid"), dict):
                    uid = payload["uid"].get("uid")
                else:
                    uid = payload.get("uid")
            except jwt.ExpiredSignatureError:
                return _with_cors(http.Response(
                    json.dumps({"statusCode": 401, "message": "Token expired"}),
                    content_type='application/json',
                    status=401
                ))
            except jwt.InvalidTokenError:
                return _with_cors(http.Response(
                    json.dumps({"statusCode": 401, "message": "Invalid token"}),
                    content_type='application/json',
                    status=401
                ))
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
                return _with_cors(http.Response(
                    json.dumps({"statusCode": 401, "message": "Token missing"}),
                    content_type='application/json',
                    status=401
                ))

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
                return _with_cors(http.Response(
                    json.dumps({"statusCode": 401, "message": "Token missing"}),
                    content_type='application/json',
                    status=401
                ))

        
        
        if not uid:
            return _with_cors(http.Response(
                json.dumps({"statusCode": 401, "message": "Token missing"}),
                content_type='application/json',
                status=401
            ))

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
            return _with_cors(http.Response(
                json.dumps({"statusCode": 404, "message": "User not found"}),
                content_type='application/json',
                status=404
            ))

        company = user.company_id
        is_owner = user.has_group('bizdom.group_bizdom_owner')
        allowed_pillar_ids = user.bizdom_allowed_pillar_ids.ids
        pillar_domain = self._get_pillar_domain(company.id, is_owner, allowed_pillar_ids)

        if filter_type == "Custom" and start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
                end_date = datetime.strptime(end_date_str, "%d-%m-%Y").date()
                if start_date > end_date:
                    return _with_cors(http.Response(
                        json.dumps({"statusCode": 400, "message": "Start date should be less than end date"}),
                        content_type='application/json',
                        status=400
                    ))

                pillar_records = request.env['bizdom.pillar'].sudo().search(pillar_domain)

                # Batch compute all scores at once
                pillar_scores_map = self._batch_compute_scores(
                    pillar_records, start_date, end_date, favorites_only, company.id, filter_type="Custom",
                    is_owner=is_owner, allowed_pillar_ids=allowed_pillar_ids
                )

                # Build response
                pillars = []
                for p in pillar_records:
                    pillars.append({
                        "pillar_id": p.id,
                        "pillar_name": p.name,
                        "pillar_identifier": p.pillar_identifier,
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

                return _with_cors(http.Response(
                    json.dumps(response),
                    content_type='application/json',
                    status=200
                ))

            except ValueError:
                return _with_cors(http.Response(
                    json.dumps({"statusCode": 400, "message": "Invalid date format, expected DD-MM-YYYY"}),
                    content_type='application/json',
                    status=400
                ))

        elif filter_type == "Today":
            today = date.today()
            today_start = today
            today_end = today
            pillar_records = request.env['bizdom.pillar'].sudo().search(pillar_domain)

            # Batch compute all scores at once
            pillar_scores_map = self._batch_compute_scores(
                pillar_records, today_start, today_end, favorites_only, company.id, filter_type="Today",
                is_owner=is_owner, allowed_pillar_ids=allowed_pillar_ids
            )

            # Build response
            pillars = []
            for p in pillar_records:
                pillars.append({
                    "pillar_id": p.id,
                    "pillar_name": p.name,
                    "pillar_identifier":p.pillar_identifier,
                    "scores": pillar_scores_map.get(p.id, [])
                })

            response = {
                "statusCode": 200,
                "message": "Data fetched",
                "company_id": company.id,
                "start_date": today_start.strftime("%d-%m-%Y"),
                "end_date": today_end.strftime("%d-%m-%Y"),
                "pillars": pillars
            }
            return _with_cors(http.Response(
                json.dumps(response),
                content_type='application/json',
                status=200
            ))


        elif filter_type == "WTD":
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            if today.weekday() == 6:  # Sunday
                week_start = today - timedelta(days=6)
            week_end = today if today.weekday() < 6 else today - timedelta(days=(today.weekday() - 4))

            try:
                pillar_records = request.env['bizdom.pillar'].sudo().search(pillar_domain)

                # Batch compute all scores at once
                pillar_scores_map = self._batch_compute_scores(
                    pillar_records, week_start, week_end, favorites_only, company.id, filter_type="WTD",
                    is_owner=is_owner, allowed_pillar_ids=allowed_pillar_ids
                )

                # Build response
                pillars = []
                for p in pillar_records:
                    pillars.append({
                        "pillar_id": p.id,
                        "pillar_name": p.name,
                        "pillar_identifier": p.pillar_identifier,
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
                return _with_cors(http.Response(
                    json.dumps({"statusCode": 500, "message": "Error processing WTD data"}),
                    content_type='application/json',
                    status=500
                ))

                

        elif filter_type == "MTD" or not filter_type:
            month_start = date.today().replace(day=1)
            month_end = date.today()
            pillar_records = request.env['bizdom.pillar'].sudo().search(pillar_domain)

            # Batch compute all scores at once
            pillar_scores_map = self._batch_compute_scores(
                pillar_records, month_start, month_end, favorites_only, company.id, filter_type="MTD",
                is_owner=is_owner, allowed_pillar_ids=allowed_pillar_ids
            )

            # Build response
            pillars = []
            for p in pillar_records:
                pillars.append({
                    "pillar_id": p.id,
                    "pillar_name": p.name,
                    "pillar_identifier": p.pillar_identifier,
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
            return _with_cors(http.Response(
                json.dumps(response),
                content_type='application/json',
                status=200
            ))

        elif filter_type == "YTD":
            today = date.today()
            year_start = date(today.year, 1, 1)  # January 1st of current year
            year_end = today
            pillar_records = request.env['bizdom.pillar'].sudo().search(pillar_domain)

            # Batch compute all scores at once
            pillar_scores_map = self._batch_compute_scores(
                pillar_records, year_start, year_end, favorites_only, company.id, filter_type="YTD",
                is_owner=is_owner, allowed_pillar_ids=allowed_pillar_ids
            )

            # Build response
            pillars = []
            for p in pillar_records:
                pillars.append({
                    "pillar_id": p.id,
                    "pillar_name": p.name,
                    "pillar_identifier": p.pillar_identifier,
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
            return _with_cors(http.Response(
                json.dumps(response),
                content_type='application/json',
                status=200
            ))

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