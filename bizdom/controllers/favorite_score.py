from odoo import http
from odoo.http import request, Response
import json
import jwt

SECRET_KEY = "Your-secret-key"


class FavoriteScore(http.Controller):


    def _json_response(self, data, status=200):
        """Helper to return clean JSON responses."""
        return Response(
            json.dumps(data),
            content_type="application/json",
            status=status
        )

    @http.route('/api/score/toggle_favorite', type='http', auth='user', methods=['POST'], csrf=False)
    def toggle_favorite(self):
        # Get JWT token from request headers
        auth_header = request.httprequest.headers.get("Authorization")
        if not auth_header:
            return self._json_response({"statusCode": 401, "message": "Token missing"}, 401)

        token = auth_header.split(" ")[1] if auth_header.startswith("Bearer ") else auth_header

        try:
            body = json.loads(request.httprequest.data.decode("utf-8"))
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            uid = payload.get("uid")
            if isinstance(uid, dict):
                uid = uid.get("uid")
        except jwt.ExpiredSignatureError:
            return self._json_response({"statusCode": 401, "message": "Token expired"}, 401)
        except jwt.InvalidTokenError:
            return self._json_response({"statusCode": 401, "message": "Invalid token"}, 401)
        except Exception as e:
            return self._json_response({"statusCode": 400, "message": f"Invalid request: {str(e)}"}, 400)
        # Extract body params
        pillar_id = body.get("pillar_id")
        score_id = body.get("score_id")
        favorite = body.get("favorite")

        if not score_id:
            return self._json_response({"statusCode": 400, "message": "score_id is required"}, 400)

        score = request.env['bizdom.score'].sudo().browse(score_id)
        if not score.exists():
            return self._json_response({"statusCode": 404, "message": "Score not found"}, 404)

        pillar = request.env['bizdom.pillar'].sudo().browse(pillar_id)
        if not pillar.exists():
            return self._json_response({"statusCode": 404, "message": "Pillar not found"}, 404)

        # Check max favorites constraint BEFORE writing
        if favorite:
            favorites = request.env['bizdom.score'].sudo().search_count([
                ('favorite', '=', True),
                ('pillar_id', '=', pillar_id),
            ])
            if favorites >= 3:
                return self._json_response({
                    "statusCode": 400,
                    "message": "You can only choose up to 3 favorite scores per pillar."
                }, 400)
            score.write({'favorite': True})
        else:
            score.write({'favorite': False})

        # Final response
        return self._json_response({
            "statusCode": 200,
            "message": "Favorite score updated successfully",
            "pillar_name": pillar.name,
            "score_name": score.score_name
        }, 200)