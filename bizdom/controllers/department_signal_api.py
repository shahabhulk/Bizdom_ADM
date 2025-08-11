from odoo import http
from odoo.http import request



class SignalAPI(http.Controller):

    # API to create a new signal under a pillar_id

    @http.route('/api/signal/<int:pillar_id>', type='json', auth='user', methods=['POST'], csrf=False)
    def create_pillar(self, company_id, **kwargs):
        name = kwargs.get('name')
        if not name:
            return {'error': 'Name is required'}
        company = request.env['res.company'].sudo().browse(company_id)
        if not company.exists():
            return {'error': 'Company not found'}
        pillar = request.env['bizdom.pillar'].sudo().create({
            'name': name,
            'company_id': company.id,
        })

        return {
            'message': 'Pillar created successfully',
            'name': pillar.name,
        }
