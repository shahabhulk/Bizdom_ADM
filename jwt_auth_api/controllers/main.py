import jwt
from datetime import datetime, timedelta
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError

SECRET_KEY = 'your_secret_key_here'

class JWTAuthController(http.Controller):

    @http.route('/api/login', type='json', auth="none", csrf=False, methods=['POST'])
    def jwt_login(self, **kwargs):
        db = kwargs.get('db')
        login = kwargs.get('login')
        password = kwargs.get('password')

        print(db,login,password)


        if not db or not login or not password:
            return {"error": "Missing login credentials"}

        if not http.db_filter([db]):
            raise AccessError("Database not found.")

        credentials = {'login': login, 'password': password, 'type': 'password'}
        try:
            auth_info = request.session.authenticate(db, credentials)
        except Exception as e:
            return {"error": f"Login failed: {str(e)}"}

        if not auth_info or not auth_info.get('uid'):
            return {"error": "Invalid login or password"}


        payload = {
            'user_id': auth_info['uid'],
            'db': db,
            'login': login,
            'exp': datetime.utcnow() + timedelta(hours=1),
        }
        print(payload)


        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

        return {
            'token': token,
            'uid': auth_info['uid'],
            'user_context': request.session.context
        }
