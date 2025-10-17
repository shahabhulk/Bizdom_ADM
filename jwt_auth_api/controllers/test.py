from odoo import http
import json


class TestController(http.Controller):
    """Test controller with CORS support"""

    @http.route('/api/test', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    def test_endpoint(self, **kwargs):
        """
        Test endpoint that returns a simple JSON response
        """
        # Handle preflight request
        if http.request.httprequest.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Max-Age': '86400'  # 24 hours
            }
            return http.Response(status=200, headers=headers)

        # Prepare response headers
        headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        }

        # Sample response data
        response_data = {
            'status': 'success',
            'message': 'Test endpoint is working!',
            'data': {
                'version': '1.0',
                'endpoint': '/api/test'
            }
        }
        return http.Response(
            json.dumps(response_data),
            headers=headers,
            status=200
        )
