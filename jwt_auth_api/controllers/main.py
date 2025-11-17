from odoo import http
from odoo.http import request
import logging
import json
import jwt
import datetime

_logger = logging.getLogger(__name__)

SECRET_KEY = "Your-secret-key"


class CustomAuthController(http.Controller):

    @http.route('/api/login', type='http', auth='none', methods=['POST'], csrf=False)
    def custom_login(self, **kwargs):

        try:
            body = json.loads(request.httprequest.data.decode('utf-8'))
            username = body.get("username")
            password = body.get("password")

            if not username or not password:
                return http.Response(
                    json.dumps({
                        "statusCode": 400,
                        "message": "Missing login or password"
                    }),)

            # elif password !=

            # Dynamic DB selection based on host

            host = request.httprequest.host
            if "laptop-uijcccph:8070" in host:
                db = "bizapp_april23"
            elif "13.233.223.127" in host:
                db = "bitnami_odoo"
            else:
                return http.Response(
                    json.dumps({
                        "statusCode": 400,
                        "message": f"Unknown host: {host}, cannot select DB"
                    }),
                    content_type='application/json',
                    status=400
                )

            credentials = {
                'login': username,
                'password': password,
                'type': 'password'
            }
            user = request.env['res.users'].sudo().search([('login', '=', username)], limit=1)
            if not user:
                return http.Response(
                    json.dumps({
                        "statusCode": 401,
                        "message": "Invalid username or password"
                    }),
                    content_type='application/json',
                    status=401
                )

            try:
                uid = request.session.authenticate(db, credentials)
                if uid:
                    # Generate JWT token
                    payload = {
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
            except Exception as e:
                return http.Response(
                    json.dumps({
                        "statusCode": 401,
                        "message": "Invalid username or password"
                    }),
                    content_type='application/json',
                    status=401
                )


            # else:
            #     return http.Response(
            #         json.dumps({
            #             "statusCode": 401,
            #             "message": "Invalid username or password"
            #         }),
            #         content_type='application/json',
            #         status=401
            #     )


        except Exception as e:
            return json.dumps({
                "statusCode": 500,
                "message": "Internal Server Error"
            })

    @http.route('/api/change_password', type='http', auth='none', methods=['POST'], csrf=False)
    def change_password(self, **kwargs):
        try:
            body = json.loads(request.httprequest.data.decode('utf-8'))
            old_password = body.get("old_password")
            new_password = body.get("new_password")
            print("hello", old_password, new_password)

            if not old_password or not new_password:
                return http.Response(
                    json.dumps({
                        "statusCode": 400,
                        "message": "Missing old_password or new_password"
                    }),
                    content_type='application/json',
                    status=400
                )

            auth_header = request.httprequest.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return http.Response(
                    json.dumps({
                        "statusCode": 401,
                        "message": "Missing or invalid Authorization header"
                    }),
                    content_type='application/json',
                    status=401
                )

            token = auth_header.split(' ', 1)[1]
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
                print("payload", payload)
                if not isinstance(payload, dict) or 'uid' not in payload:
                    raise ValueError("Invalid token")

                if isinstance(payload['uid'], dict) and 'uid' in payload['uid']:
                    uid = int(payload['uid']['uid'])
                else:
                    uid = int(payload['uid'])

                print("user",uid)
            except Exception as e:
                _logger.exception("Invalid token")
                return http.Response(
                    json.dumps({
                        "statusCode": 401,
                        "message": "Invalid token",
                        "error": str(e)
                    }),
                    content_type='application/json',
                    status=401
                )

            if not uid:
                return http.Response(
                    json.dumps({
                        "statusCode": 401,
                        "message": "Token does not contain uid"
                    }),
                    content_type='application/json',
                    status=401
                )

            # Determine DB from host (same logic as login)
            host = request.httprequest.host
            if "laptop-uijcccph:8070" in host:
                db = "bizapp_april23"
            elif "13.233.223.127" in host:
                db = "bitnami_odoo"
            else:
                return http.Response(
                    json.dumps({
                        "statusCode": 400,
                        "message": f"Unknown host: {host}, cannot select DB"
                    }),
                    content_type='application/json',
                    status=400
                )

            # Get user login using direct SQL query
            request.env.cr.execute("""
                SELECT login FROM res_users WHERE id = %s """, (uid,))
            user_data = request.env.cr.fetchone()

            if not user_data:
                return http.Response(
                    json.dumps({
                        "statusCode": 404,
                        "message": "User not found"
                    }),
                    content_type='application/json',
                    status=404
                )

            login = user_data[0]
            print(f"Authenticating user with login: {login} (ID: {uid})")

            credentials = {
                'login': login,
                'password': old_password,
                'type': 'password'
            }
            reuid = request.session.authenticate(db, credentials)
            if not reuid:
                return http.Response(
                    json.dumps({
                        "statusCode": 401,
                        "message": "Old password is incorrect"
                    }),
                    content_type='application/json',
                    status=401
                )
            # Update password

            user = request.env['res.users'].sudo().browse(uid)
            user.sudo().write({'password': new_password})
            return http.Response(
                json.dumps({
                    "statusCode": 200,
                    "message": f"Password changed successfully for user {user.name}"
                }),
                content_type='application/json',
                status=200
            )


        except Exception as e:
            return json.dumps({
                "statusCode": 500,
                "message": "Internal Server Error"

            })
