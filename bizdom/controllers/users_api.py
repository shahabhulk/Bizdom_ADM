from odoo import http
from odoo.http import request

from .to_do_api import _json_response, jwt_required, _serialize_user


class BizdomUsersAPI(http.Controller):

    @http.route('/api/users', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @jwt_required
    def list_users(self, **kwargs):
        search = (kwargs.get("search") or "").strip()

        try:
            limit = min(int(kwargs.get("limit", 50)), 200)
            offset = int(kwargs.get("offset", 0))
        except (TypeError, ValueError):
            limit, offset = 50, 0

        domain = [("active", "=", True), ("share", "=", False)]
        if search:
            domain += ["|", ("name", "ilike", search), ("login", "ilike", search)]

        Users = request.env["res.users"].sudo()
        total = Users.search_count(domain)
        users = Users.search(domain, limit=limit, offset=offset, order="name asc")

        return _json_response({
            "statusCode": 200,
            "data": [_serialize_user(u) for u in users],
            "meta": {"total": total, "limit": limit, "offset": offset},
        })
