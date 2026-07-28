from functools import wraps
from datetime import datetime
import json
import jwt

from odoo import http, Command
from odoo.http import request, Response
from odoo.tools import html2plaintext

SECRET_KEY = "Your-secret-key"
VALID_TODO_PRIORITIES = {"low", "medium", "high"}


def _json_response(data, status=200):
    return Response(
        json.dumps(data),
        content_type="application/json",
        status=status,
    )


def _auth_or_error():
    """Validate auth and set request env user. Returns an error Response or None.

    Supports both:
    - Bearer JWT (external API clients)
    - Odoo session user (internal dashboard calls)
    """
    auth_header = request.httprequest.headers.get("Authorization")
    if not auth_header:
        session_uid = request.session.uid
        if session_uid:
            request.update_env(user=int(session_uid))
            return None
        return _json_response({"statusCode": 401, "message": "Token missing"}, 401)

    token = auth_header.split(" ", 1)[1] if auth_header.startswith("Bearer ") else auth_header
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        uid = payload.get("uid")
        if isinstance(uid, dict):
            uid = uid.get("uid")
        uid = int(uid)
    except jwt.ExpiredSignatureError:
        return _json_response({"statusCode": 401, "message": "Token expired"}, 401)
    except (jwt.InvalidTokenError, TypeError, ValueError):
        return _json_response({"statusCode": 401, "message": "Invalid token"}, 401)

    request.update_env(user=uid)
    return None


def jwt_required(fn):
    """Handles CORS preflight + JWT authentication. Use below @http.route."""
    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        if request.httprequest.method == "OPTIONS":
            return _json_response({}, 200)
        err = _auth_or_error()
        if err:
            return err
        return fn(self, *args, **kwargs)
    return wrapper


def _serialize_user(u):
    host = request.httprequest.host_url.rstrip("/")
    return {
        "id": u.id,
        "name": u.name,
        "login": u.login,
        "avatar_url": f"{host}/web/image/res.users/{u.id}/avatar_128",
    }


def _serialize_todo(t):
    description = html2plaintext(t.description or "").strip()
    return {
        "id": t.id,
        "name": t.name,
        "description": description,
        "pillar_id": t.pillar_id.id if t.pillar_id else None,
        "pillar_name": t.pillar_id.name if t.pillar_id else None,
        "date_deadline": t.date_deadline.isoformat() if t.date_deadline else None,
        "state": t.state,
        "priority": t.bizdom_priority or "low",
        "user_ids": [_serialize_user(u) for u in t.user_ids],
        "create_date": t.create_date.isoformat() if t.create_date else None,
        "write_date": t.write_date.isoformat() if t.write_date else None,
    }


def _resolve_user_ids(raw_user_ids, creator_uid=None):
    """Validate and normalize an incoming user_ids list.

    Returns (list_of_ids, None) on success or (None, error_response).
    """
    if raw_user_ids is None:
        raw_user_ids = []
    if not isinstance(raw_user_ids, list):
        return None, _json_response(
            {"statusCode": 400, "message": "user_ids must be a list of integers"}, 400
        )
    try:
        ids = [int(u) for u in raw_user_ids]
    except (TypeError, ValueError):
        return None, _json_response(
            {"statusCode": 400, "message": "user_ids must contain integers"}, 400
        )

    if creator_uid is not None and creator_uid not in ids:
        ids.append(creator_uid)

    if not ids:
        return [], None

    valid = request.env["res.users"].sudo().search([
        ("id", "in", ids),
        ("active", "=", True),
        ("share", "=", False),
    ])
    if len(valid) != len(set(ids)):
        return None, _json_response(
            {"statusCode": 404, "message": "One or more user_ids are invalid"}, 404
        )
    return valid.ids, None


def _parse_json_body():
    try:
        return json.loads(request.httprequest.data.decode("utf-8") or "{}"), None
    except Exception:
        return None, _json_response({"statusCode": 400, "message": "Invalid JSON body"}, 400)


def _parse_deadline(value):
    """Returns (value_or_False, None) or (None, error_response)."""
    if not value:
        return False, None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None, _json_response(
            {"statusCode": 400, "message": "date_deadline must be YYYY-MM-DD"}, 400
        )
    return value, None


class BizdomTodoAPI(http.Controller):

    # ---------------------------------------------------------------------
    # GET /api/todos — list todos assigned to the current user
    # ---------------------------------------------------------------------
    @http.route('/api/todos', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @jwt_required
    def list_todos(self, **kwargs):
        uid = request.env.user.id

        try:
            limit = min(int(kwargs.get("limit", 50)), 200)
            offset = int(kwargs.get("offset", 0))
        except (TypeError, ValueError):
            limit, offset = 50, 0

        domain = [("user_ids", "in", [uid])]

        if kwargs.get("pillar_id"):
            try:
                domain.append(("pillar_id", "=", int(kwargs["pillar_id"])))
            except (TypeError, ValueError):
                return _json_response(
                    {"statusCode": 400, "message": "pillar_id must be an integer"}, 400
                )
        if kwargs.get("search"):
            domain.append(("name", "ilike", kwargs["search"]))
        if kwargs.get("assignee_id"):
            try:
                domain.append(("user_ids", "in", [int(kwargs["assignee_id"])]))
            except (TypeError, ValueError):
                return _json_response(
                    {"statusCode": 400, "message": "assignee_id must be an integer"}, 400
                )

        Task = request.env["project.task"].sudo()
        total = Task.search_count(domain)
        todos = Task.search(
            domain, limit=limit, offset=offset,
            order="date_deadline asc, id desc",
        )

        return _json_response({
            "statusCode": 200,
            "data": [_serialize_todo(t) for t in todos],
            "meta": {"total": total, "limit": limit, "offset": offset},
        })

    # ---------------------------------------------------------------------
    # GET /api/todos/<id> — fetch single todo with hydrated assignees
    # ---------------------------------------------------------------------
    @http.route('/api/todos/<int:todo_id>', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @jwt_required
    def get_todo(self, todo_id, **kwargs):
        uid = request.env.user.id
        todo = request.env["project.task"].sudo().browse(todo_id)
        if not todo.exists():
            return _json_response({"statusCode": 404, "message": "Todo not found"}, 404)
        if uid not in todo.user_ids.ids:
            return _json_response({"statusCode": 403, "message": "Forbidden"}, 403)

        return _json_response({"statusCode": 200, "data": _serialize_todo(todo)})

    # ---------------------------------------------------------------------
    # POST /api/todos — create a todo and assign to multiple users
    # ---------------------------------------------------------------------
    @http.route('/api/todos', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    @jwt_required
    def create_todo(self, **kwargs):
        uid = request.env.user.id

        body, err = _parse_json_body()
        if err:
            return err

        name = body.get("name")
        if not name:
            return _json_response({"statusCode": 400, "message": "name is required"}, 400)

        assignee_ids, err = _resolve_user_ids(body.get("user_ids"), creator_uid=uid)
        if err:
            return err

        vals = {
            "name": name,
            "description": body.get("description") or False,
            "user_ids": [Command.set(assignee_ids)],
        }
        if body.get("priority"):
            if body["priority"] not in VALID_TODO_PRIORITIES:
                return _json_response(
                    {
                        "statusCode": 400,
                        "message": f"priority must be one of: {sorted(VALID_TODO_PRIORITIES)}",
                    },
                    400,
                )
            vals["bizdom_priority"] = body["priority"]

        if body.get("pillar_id"):
            try:
                pillar_id = int(body["pillar_id"])
            except (TypeError, ValueError):
                return _json_response(
                    {"statusCode": 400, "message": "pillar_id must be an integer"}, 400
                )
            pillar = request.env["bizdom.pillar"].sudo().browse(pillar_id)
            if not pillar.exists():
                return _json_response({"statusCode": 404, "message": "Pillar not found"}, 404)
            vals["pillar_id"] = pillar.id

        deadline, err = _parse_deadline(body.get("date_deadline"))
        if err:
            return err
        if deadline:
            vals["date_deadline"] = deadline

        todo = request.env["project.task"].sudo().create(vals)

        return _json_response({
            "statusCode": 201,
            "message": "Todo created successfully",
            "data": _serialize_todo(todo),
        }, 201)

    # ---------------------------------------------------------------------
    # PUT /api/todos/<id> — partial update (only provided keys are changed)
    # ---------------------------------------------------------------------
    @http.route('/api/todos/<int:todo_id>', type='http', auth='none',
                methods=['PUT', 'OPTIONS'], csrf=False, cors='*')
    @jwt_required
    def update_todo(self, todo_id, **kwargs):
        uid = request.env.user.id
        todo = request.env["project.task"].sudo().browse(todo_id)
        if not todo.exists():
            return _json_response({"statusCode": 404, "message": "Todo not found"}, 404)
        if uid not in todo.user_ids.ids:
            return _json_response({"statusCode": 403, "message": "Forbidden"}, 403)

        body, err = _parse_json_body()
        if err:
            return err

        vals = {}

        if "name" in body:
            if not body["name"]:
                return _json_response(
                    {"statusCode": 400, "message": "name cannot be empty"}, 400
                )
            vals["name"] = body["name"]

        if "description" in body:
            vals["description"] = body["description"] or False

        if "pillar_id" in body:
            if body["pillar_id"]:
                try:
                    pillar_id = int(body["pillar_id"])
                except (TypeError, ValueError):
                    return _json_response(
                        {"statusCode": 400, "message": "pillar_id must be an integer"}, 400
                    )
                pillar = request.env["bizdom.pillar"].sudo().browse(pillar_id)
                if not pillar.exists():
                    return _json_response(
                        {"statusCode": 404, "message": "Pillar not found"}, 404
                    )
                vals["pillar_id"] = pillar.id
            else:
                vals["pillar_id"] = False

        if "date_deadline" in body:
            deadline, err = _parse_deadline(body["date_deadline"])
            if err:
                return err
            vals["date_deadline"] = deadline

        if "priority" in body:
            priority = body["priority"] or "low"
            if priority not in VALID_TODO_PRIORITIES:
                return _json_response(
                    {
                        "statusCode": 400,
                        "message": f"priority must be one of: {sorted(VALID_TODO_PRIORITIES)}",
                    },
                    400,
                )
            vals["bizdom_priority"] = priority

        if "user_ids" in body:
            assignee_ids, err = _resolve_user_ids(body["user_ids"])
            if err:
                return err
            if not assignee_ids:
                return _json_response(
                    {"statusCode": 400, "message": "A todo must have at least one assignee"},
                    400,
                )
            vals["user_ids"] = [Command.set(assignee_ids)]

        if vals:
            todo.write(vals)

        return _json_response({
            "statusCode": 200,
            "message": "Todo updated successfully",
            "data": _serialize_todo(todo),
        })

    # ---------------------------------------------------------------------
    # DELETE /api/todos/<id>
    # ---------------------------------------------------------------------
    @http.route('/api/todos/<int:todo_id>', type='http', auth='none',
                methods=['DELETE', 'OPTIONS'], csrf=False, cors='*')
    @jwt_required
    def delete_todo(self, todo_id, **kwargs):
        uid = request.env.user.id
        todo = request.env["project.task"].sudo().browse(todo_id)
        if not todo.exists():
            return _json_response({"statusCode": 404, "message": "Todo not found"}, 404)
        if uid not in todo.user_ids.ids:
            return _json_response({"statusCode": 403, "message": "Forbidden"}, 403)

        todo.unlink()
        return _json_response({"statusCode": 200, "message": "Todo deleted successfully"})
