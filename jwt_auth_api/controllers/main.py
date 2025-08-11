from odoo import http
from odoo.http import request
import logging
import json
import jwt
import datetime

_logger = logging.getLogger(__name__)

SECRET_KEY="Your-secret-key"

class CustomAuthController(http.Controller):

    @http.route('/api/login', type='http', auth='none', methods=['POST'], csrf=False)
    def custom_login(self, **kwargs):
        db = "bizapp_april23"

        try:
            body = json.loads(request.httprequest.data.decode('utf-8'))
            username = body.get("username")
            password = body.get("password")

            if not username or not password:
                return http.Response(
                    json.dumps({
                        "statusCode": 400,
                        "message": "Missing login or password"
                    }),
                    content_type='application/json',
                    status=400
                )

            credentials = {
                'login': username,
                'password': password,
                'type': 'password'
            }

            uid = request.session.authenticate(db, credentials)
            if uid:
                # Generate JWT token
                payload={
                    'uid': uid,
                    'login': username,
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
                }
                token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
                return http.Response(
                    json.dumps({
                        "statusCode": 200,
                        "message": "Login successful",
                        "uid": uid,
                        "token": token
            
                    }),
                    content_type='application/json',
                    status=200
                )
            else:
                return http.Response(
                    json.dumps({
                        "statusCode": 401,
                        "message": "Invalid credentials"
                    }),
                    content_type='application/json',
                    status=401
                )

        except Exception as e:
            _logger.exception("Authentication error")
            return http.Response(
                json.dumps({
                    "statusCode": 500,
                    "message": "Internal Server Error",
                    "error": str(e)
                }),
                content_type='application/json',
                status=500
            )
