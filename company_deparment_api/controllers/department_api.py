from odoo import http
from odoo.http import request

class DepartmentAPI(http.Controller):


    @http.route('/api/departments', type='json', auth='user', methods=['GET'], csrf=False)
    def get_departments(self):
        departments = request.env['hr.department'].search([])
        return [
            {
                'id': dept.id,
                'name': dept.name,
                'company_id': dept.company_id.id,
                'company_name': dept.company_id.name
            }
            for dept in departments
        ]


    @http.route('/api/departments/<int:dept_id>', type='json', auth='user', methods=['GET'], csrf=False)
    def get_department(self, dept_id):
        dept = request.env['hr.department'].browse(dept_id)
        if not dept.exists():
            return {'error': 'Department not found'}
        return {
            'id': dept.id,
            'name': dept.name,
            'company_id': dept.company_id.id,
            'company_name': dept.company_id.name
        }


    @http.route('/api/departments', type='json', auth='user', methods=['POST'], csrf=False)
    def create_department(self, **kwargs):
        name = kwargs.get('name')
        company_id = kwargs.get('company_id')

        if not name or not company_id:
            return {'error': 'Both name and company_id are required'}

        dept = request.env['hr.department'].create({
            'name': name,
            'company_id': company_id
        })
        return {'id': dept.id, 'message': 'Department created'}


    @http.route('/api/departments/<int:dept_id>', type='json', auth='user', methods=['PUT'], csrf=False)
    def update_department(self, dept_id, **kwargs):
        dept = request.env['hr.department'].browse(dept_id)
        if not dept.exists():
            return {'error': 'Department not found'}

        dept.write(kwargs)
        return {'message': 'Department updated'}

    @http.route('/api/departments/<int:dept_id>', type='json', auth='user', methods=['DELETE'], csrf=False)
    def delete_department(self, dept_id):
        dept = request.env['hr.department'].browse(dept_id)
        if not dept.exists():
            return {'error': 'Department not found'}

        dept.unlink()
        return {'message': 'Department deleted'}
