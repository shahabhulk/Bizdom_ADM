from odoo import http, Command
from odoo.http import request, Response
import json
import jwt
from datetime import datetime

SECRET_KEY = "Your-secret-key"


class BizdomTodoAPI(http.Controller):

    def _json_response(self, data, status=200):
        return Response(
            json.dumps(data),
            content_type="application/json",
            status=status
        )

    @http.route('/api/todos', type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def create_todo(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return self._json_response({}, 200)

        auth_header = request.httprequest.headers.get("Authorization")
        if not auth_header:
            return self._json_response({"statusCode": 401, "message": "Token missing"}, 401)

        token = auth_header.split(" ")[1] if auth_header.startswith("Bearer ") else auth_header
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            uid = payload.get("uid")
            if isinstance(uid, dict):
                uid = uid.get("uid")
        except jwt.ExpiredSignatureError:
            return self._json_response({"statusCode": 401, "message": "Token expired"}, 401)
        except jwt.InvalidTokenError:
            return self._json_response({"statusCode": 401, "message": "Invalid token"}, 401)

        if not uid:
            return self._json_response({"statusCode": 401, "message": "Invalid token"}, 401)
        try:
            uid = int(uid)
        except (TypeError, ValueError):
            return self._json_response({"statusCode": 401, "message": "Invalid token"}, 401)

        # auth='none' leaves request.env.user empty; project.task.create calls self.env.user._is_portal()
        request.update_env(user=uid)

        try:
            body = json.loads(request.httprequest.data.decode("utf-8") or "{}")
        except Exception:
            return self._json_response({"statusCode": 400, "message": "Invalid JSON body"}, 400)

        name = body.get("name")
        pillar_id = body.get("pillar_id")
        description = body.get("description")
        user_ids = body.get("user_ids")
        date_deadline = body.get("date_deadline")

        if not name:
            return self._json_response({"statusCode": 400, "message": "name is required"}, 400)

        # Odoo 18 project.task uses user_ids (m2m), not user_id
        vals = {
            "name": name,
            "description": description or False,
            "user_ids": [Command.link(uid)],
        }

        if pillar_id:
            pillar = request.env['bizdom.pillar'].sudo().browse(int(pillar_id))
            if not pillar.exists():
                return self._json_response({"statusCode": 404, "message": "Pillar not found"}, 404)
            vals["pillar_id"] = pillar.id

        if date_deadline:
            try:
                datetime.strptime(date_deadline, "%Y-%m-%d")
                vals["date_deadline"] = date_deadline
            except ValueError:
                return self._json_response(
                    {"statusCode": 400, "message": "date_deadline must be YYYY-MM-DD"},
                    400
                )

        todo = request.env["project.task"].sudo().create(vals)

        return self._json_response({
            "statusCode": 201,
            "message": "Todo created successfully",
            "data": {
                "id": todo.id,
                "name": todo.name,
                "pillar_id": todo.pillar_id.id if todo.pillar_id else None,
            }
        }, 201)
