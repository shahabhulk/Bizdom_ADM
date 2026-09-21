# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
import base64

from odoo import http, _
from odoo.http import request
from datetime import datetime, timedelta


class Appointment(http.Controller):

    @http.route('/appointment-book', auth='public', type='http', website=True)
    def appointment(self, **post):
        return request.render("car_repair_industry.appointment_form")

    @http.route('/appointment/confirm', auth='public', type='http', website=True)
    def appointment_confirm(self, **post):
        if post:
            meeting = request.env['calendar.event'].sudo()
            partner = request.env['res.partner'].sudo().search([('email', '=', post['email_from'])], limit=1)
            appoint_date_str = post.get('appoint_date')
            time_slot_float = float(post.get('time_slot'))
            hours = int(time_slot_float)
            minutes = int((time_slot_float - hours) * 60)
            time_slot_str = f"{hours:02}:{minutes:02}:00"
            combined_datetime_str = f"{appoint_date_str} {time_slot_str}"
            combined_datetime = datetime.strptime(combined_datetime_str, '%Y-%m-%d %H:%M:%S')
            stop_datetime = combined_datetime + timedelta(hours=1)
            combined_datetime_str_formatted = combined_datetime.strftime('%Y-%m-%d %H:%M:%S')
            stop_datetime_str_formatted = stop_datetime.strftime('%Y-%m-%d %H:%M:%S')
            weekday_id_get = request.env['appointement.slots'].sudo().search(
                [('appointment_date', '=', post.get('appoint_date'))], limit=1)
            if not partner:
                partner_new = request.env['res.partner'].sudo().create({
                    'name': post['name'],
                    'email': post['email_from'],
                    'phone': post['phone'],
                })
            values = {
                'name': post.get('subject'),
                'appoi_name': post.get('name'),
                'email': post.get('email_from'),
                'phone': post.get('phone'),
                'start': combined_datetime_str_formatted,
                'stop': stop_datetime_str_formatted,
                'duration': 1.0,
                'time_slot': post.get('time_slot'),
                'partner_id': partner.id,
                'description': post.get('description'),
                'weekday_get': weekday_id_get.id if weekday_id_get.id else '',
            }
            meeting_val = meeting.create(values)

            return request.render("car_repair_industry.appointment_confirm", values)

    @http.route('/service-repair', auth='public', type='http', website=True)
    def service_repair_form(self, **post):
        return request.render("car_repair_industry.service_repair_form")

    @http.route('/service/repair/form/submit', auth='public', type='http', website=True)
    def service_repair_form_submit(self, **post):
        if post:
            car_repair = request.env['fleet.repair'].sudo()
            car_detail = request.env['fleet.vehicle'].sudo()

            Attachments = request.env['ir.attachment'].sudo()
            # upload_file = post['upload']
            name_get = request.env['res.users'].sudo().search([('name', '=', post.get('name'))])
            default_user = request.env['res.users'].sudo().browse(request.uid)
            service_type_get = request.env['service.type'].sudo().search([('id', '=', post.get('service'))], limit=1)
            car_brand_get = request.env['fleet.vehicle'].sudo().search([('id', '=', post.get('car_brand'))], limit=1)
            car_model_get = request.env['fleet.vehicle.model'].sudo().search([('id', '=', post.get('car_model'))],
                                                                             limit=1)
            val = {
                'service_type': service_type_get.id if service_type_get.id else '',
                'fleet_id': car_brand_get.id if car_brand_get.id else '',
                'model_id': car_model_get.id if car_model_get.id else '',
                'car_year': post.get('car_manuf_year'),
                'service_detail': post.get('reason_for_repair_detail'),
                'list_of_damage': post.get('list_of_damage'),
            }
            values = {
                'client_id': name_get.partner_id.id if name_get.partner_id.id else default_user.partner_id.id,
                'name': post.get('reason_of_repair'),
                'client_email': post.get('email_from'),
                'client_phone': post.get('phone'),
                'priority': post.get('priority'),
                'fleet_repair_line': [(0, 0, val)],

            }
            car_repair_obj = car_repair.create(values)

            file = request.httprequest.files.getlist('file')
            if file:
                for i in range(len(file)):
                    attachment_id = Attachments.sudo().create({
                        'name': file[i].filename,
                        'type': 'binary',
                        'datas': base64.b64encode(file[i].read()),
                        'public': True,
                    })
                    car_repair_obj.update({'images_ids': [(4, attachment_id.id)]})
            return request.render("car_repair_industry.service_repair_form_submit", values)

    @http.route('/feedback/form/<model("fleet.repair"):repair>', auth='public', type='http', website=True)
    def feedback_form(self, repair, **post):
        values = {
            'fleet_repair_id': repair.id
        }
        return request.render("car_repair_industry.feedback_form", values)

    @http.route('/feedback/form/submit', auth='public', type='http', website=True, csrf=False)
    def feedbacksubmit(self, **post):
        if post:
            car_repair = request.env['fleet.repair'].sudo().browse(int(post.get('fleet_repair')))
            values = {
                'feedback_description': post.get('feedback_description'),
                'rating': post.get('customer_rating')
            }
            car_repair.update(values)
        return request.render("car_repair_industry.review_submit", values)

    @http.route('/fleet_repair/dashboard_data', type="json", auth='user')
    def fleet_repair_dashboard_data(self, department=None, **kwargs):
        request.env.invalidate_all()
        company_id = request.env.user.company_id.id

        repair_domain = []
        diagnose_domain = []
        workorder_domain = []
        feedback_domain = []
        service_type_domain = []

        if department:
            repair_domain = [('department_id.name', 'ilike', department)]
            diagnose_domain = [('fleet_repair_id.department_id.name', 'ilike', department)]
            workorder_domain = [('fleet_repair_id.department_id.name', 'ilike', department)]
            feedback_domain = [('department_ids.name', 'ilike', department)]
            service_type_domain = [('department_id.name', 'ilike', department)]

        fleet_repair = request.env['fleet.repair'].sudo().search(repair_domain + [('state', 'not in', ['done', 'invoiced', 'cancel'])])
        fleet_diagnose = request.env['fleet.diagnose'].sudo().search(diagnose_domain)
        fleet_diagnos_d = request.env['fleet.diagnose'].sudo().search(diagnose_domain + [('state', '=', 'in_progress')])
        fleet_repair_d = request.env['fleet.repair'].sudo().search(repair_domain + [('state', '=', 'done')])
        fleet_workorder = request.env['fleet.workorder'].sudo().search(workorder_domain)
        fleet_service_type = request.env['service.type'].sudo().search(service_type_domain)
        lead_count = request.env['crm.lead'].sudo().search_count([
            ('company_id', '=', company_id)
        ])
        feedback_count = request.env['fleet.repair.feedback'].sudo().search(feedback_domain)
        parts_purchase_count = request.env['purchase.order'].sudo().search_count([
            ('company_id', '=', company_id),
        ])
        company_expense_count = request.env['hr.expense'].sudo().search_count([
            ('company_id', '=', company_id),
        ])

        user_department = False
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.uid)], limit=1)
        if employee and employee.department_id and employee.department_id.name:
            dept_name = employee.department_id.name.lower()
            if 'bodyshop' in dept_name:
                user_department = 'bodyshop'
            elif 'workshop' in dept_name:
                user_department = 'workshop'

        bodyshop_repair_count = request.env['fleet.repair'].sudo().search_count([
            ('department_id.name', 'ilike', 'bodyshop'),
            ('state', 'not in', ['done', 'invoiced', 'cancel'])
        ])
        workshop_repair_count = request.env['fleet.repair'].sudo().search_count([
            ('department_id.name', 'ilike', 'workshop'),
            ('state', 'not in', ['done', 'invoiced', 'cancel'])
        ])

        dashboard_data = {
            'fleet_repair_count': len(fleet_repair),
            'bodyshop_repair_count': bodyshop_repair_count,
            'workshop_repair_count': workshop_repair_count,
            'user_department': user_department,
            'fleet_diagnos_count': len(fleet_diagnose),
            'fleet_diagnos_d_count': len(fleet_diagnos_d),
            'fleet_repair_d_count': len(fleet_repair_d),
            'fleet_workorder_count': len(fleet_workorder),
            'fleet_service_type_count': len(fleet_service_type),
            'feedback_count': len(feedback_count),
            'lead_count': lead_count,
            'parts_purchase_count': parts_purchase_count,
            'company_expense_count': company_expense_count,
            'department': department,
        }
        return dashboard_data
