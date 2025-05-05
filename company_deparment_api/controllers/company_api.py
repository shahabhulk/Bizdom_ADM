from odoo import http
from odoo.http import request
import json


class CompanyAPI(http.Controller):

    @http.route('/api/companies', type='json', auth='user', methods=['GET'], csrf=False)
    def get_companies(self):
        companies = request.env['res.company'].sudo().search([])
        company_list = []
        for company in companies:
            company_list.append({
                'id': company.id,
                'name': company.name,
                'street': company.street,
                'city': company.city
            })
        return company_list

    @http.route('/api/companies/<int:company_id>', type='json', auth='user', methods=['GET'], csrf=False)
    def get_company(self, company_id):
        company = request.env['res.company'].sudo().browse(company_id)
        if not company.exists():
            return {'error': 'Company not found'}
        return {
            'id': company.id,
            'name': company.name,
            'street': company.street,
            'city': company.city
        }

    @http.route('/api/companies', type='json', auth='user', methods=['POST'], csrf=False)
    def create_company(self, **kwargs):
        company = request.env['res.company'].sudo().create({
            'name': kwargs.get('name'),
            'street': kwargs.get('street'),
            'city': kwargs.get('city')
        })
        return {'id': company.id, 'message': 'Company created'}

    @http.route('/api/companies/<int:company_id>', type='json', auth='user', methods=['PUT'], csrf=False)
    def update_company(self, company_id, **kwargs):
        company = request.env['res.company'].sudo().browse(company_id)
        if not company.exists():
            return {'error': 'Company not found'}
        company.write(kwargs)
        return {'message': 'Company updated'}

    @http.route('/api/companies/<int:company_id>', type='json', auth='user', methods=['DELETE'], csrf=False)
    def delete_company(self, company_id):
        company = request.env['res.company'].sudo().browse(company_id)

        if not company.exists():
            return {'error': 'Company not found'}


        if company.child_ids:
            company.child_ids.unlink()
        if company.bank_ids:
            company.bank_ids.unlink()
        if company.logo:
            company.logo = False

        if company.account_cash_basis_base_account_id:
            company.account_cash_basis_base_account_id = False
        if company.account_sale_tax_id:
            company.account_sale_tax_id = False
        if company.account_purchase_tax_id:
            company.account_purchase_tax_id = False


        company.user_ids.write({'company_id': None})

        company.unlink()

        return {'message': 'Company deleted'}
