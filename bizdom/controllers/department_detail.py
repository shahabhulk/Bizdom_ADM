from odoo import http
from odoo.http import request
import json


class DepartmentAPI(http.Controller):

    # API to create a new pillar under a company_id

    @http.route('/api/pillar/<int:company_id>', type='json', auth='user', methods=['POST'], csrf=False)
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

    # API to get all pillars of a company
    @http.route('/api/pillars/<int:company_id>', type='http', auth='user', methods=['GET'], csrf=False)
    def get_pillars(self, company_id):
        try:
            pillars = request.env['bizdom.pillar'].sudo().search([('company_id', '=', company_id)])
            pillar_list = []
            for pillar in pillars:
                pillar_list.append({
                    'id': pillar.id,
                    'piller_name': pillar.name
                })

            response = {
                "statusCode": 200,
                "message": "Data fetched",
                "company_id": company_id,
                "pillers": pillar_list
            }

            return http.Response(
                json.dumps(response),
                content_type='application/json',
                status=200
            )

        except Exception as e:
            error_response = {
                "statusCode": 500,
                "message": "Error fetching data",
                "error": str(e)
            }
            return http.Response(
                json.dumps(error_response),
                content_type='application/json',
                status=500
            )

    # API to get a specific pillar
    @http.route('/api/pillar/<int:pillar_id>', type='json', auth='user', methods=['GET'], csrf=False)
    def get_pillar(self, pillar_id):
        pillar = request.env['bizdom.pillar'].sudo().browse(pillar_id)
        if not pillar.exists():
            return {'error': 'Pilar not found'}
        return {
            'id': pillar.id,
            'name': pillar.name,
            'company_id': pillar.company_id.id
        }

    # API  to update a pillar of a specific company
    @http.route('/api/pillar/<int:pillar_id>', type='json', auth='user', methods=['PUT'], csrf=False)
    def update_pillar(self, pillar_id, **kwargs):
        pillar = request.env['bizdom.pillar'].sudo().browse(pillar_id)

        if not pillar.exists():
            return {'error': 'Pillar not found'}

        name = kwargs.get('name')
        if not name:
            return {'error': 'Name is required'}

        pillar.write({'name': name})

        return {
            'message': 'Pillar updated successfully',
            'pillar': {
                'id': pillar.id,
                'name': pillar.name,
                'company_id': pillar.company_id.id,
            }
        }

    # API to deleta a pillar of a specific company
    @http.route('/api/pillar/<int:pillar_id>', type='json', auth='user', methods=['DELETE'], csrf=False)
    def delete_pillar(self, pillar_id):
        pillar = request.env['bizdom.pillar'].sudo().browse(pillar_id)
        if not pillar.exists():
            return {'error': 'Pillar not found'}
        # Delete the pillar 
        pillar.unlink()
        return {'message': 'Pillar deleted successfully'}

    # -----------------------------------------------------------------------------------------------------------------

    # API to create a new department under a pillar

    @http.route('/api/department/<int:pillar_id>', type='json', auth='user', methods=['POST'], csrf=False)
    def create_department(self, pillar_id, **kwargs):
        name = kwargs.get('name')
        if not name:
            return {'error': 'Name is required'}

        pillar = request.env['bizdom.pillar'].sudo().browse(pillar_id)
        if not pillar.exists():
            return {'error': 'Pillar not found'}

        # even if the department is case insensitiive we need to check if the department already exists

        existing_department = request.env['hr.department'].sudo().search([
            ('company_id', '=', pillar.company_id.id)
        ])
        existing_department = existing_department.filtered(lambda d: d.name.strip().lower() == name.strip().lower())

        if existing_department:
            return {'error': f"Department with name '{name}' already exists in the {pillar.name}."}

        else:
            department = request.env['hr.department'].sudo().create({
                'name': name,
                'company_id': pillar.company_id.id
            })
            pillar_line = request.env['bizdom.pillar.line'].sudo().create({
                'department_id': department.id,
                'pillar_id': pillar.id
            })

        return {
            'department_id': department.id,
            'message': 'Department created successfully',

        }

    # Get all departments of a pillar
    # @http.route('/api/d/<int:company_id>', type='json', auth='user', methods=['GET'], csrf=False)

    @http.route('/api/departments/<int:pillar_id>', type='json', auth='user', methods=['GET'], csrf=False)
    def get_departments(self, pillar_id):
        pillar = request.env['bizdom.pillar'].sudo().browse(pillar_id)
        department_list = []
        for department in pillar.department_biz_ids:
            department_list.append({
                'id': department.id,
                'name': department.department_id.name,
                'department_id': department.department_id.id
            })
        return department_list

    @http.route('/api/department/<int:department_id>', type='json', auth='user', methods=['GET'], csrf=False)
    def get_department(self, department_id):
        department = request.env['hr.department'].sudo().browse(department_id)
        if not department.exists():
            return {'error': 'Department not found'}
        return {
            'id': department.id,
            'name': department.name,
            'company_id': department.company_id.id if department.company_id else None,
        }

    # API to update a department of a specific pillar
    @http.route('/api/department/<int:department_id>', type='json', auth='user', methods=[
        'PUT'], csrf=False)
    def update_department(self, department_id, **kwargs):
        department = request.env['hr.department'].sudo().browse(department_id)
        if not department.exists():
            return {'error': 'Department not found'}
        name = kwargs.get('name')
        if not name:
            return {'error': 'Name is required'}
        department.write({'name': name})
        return {
            'message': 'Department updated successfully'
        }

    # API to delete a department of a specific pillar
    @http.route('/api/department/<int:department_id>', type='json', auth='user', methods=['DELETE'], csrf=False)
    def delete_department(self, department_id):
        department = request.env['hr.department'].sudo().browse(department_id)
        bizdom_pillar_lines = request.env['bizdom.pillar.line'].sudo().browse()
        if not department.exists():
            return {'error': 'Department not found'}

        else:
            department.unlink()
            return {'message': 'Department deleted successfully'}

# --------------------------------------------------------------------------------------------------------
