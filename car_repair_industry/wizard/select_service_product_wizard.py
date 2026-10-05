# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class SelectServiceProductWizard(models.TransientModel):
    _name = 'select.service.product.wizard'
    _description = 'Select Services from Product Masters'

    status_log_id = fields.Many2one('hr.employee.status.log', string='Status Log', required=True)
    repair_id = fields.Many2one('fleet.repair', string='Job Card', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True)
    department_id = fields.Many2one('hr.department', string='Department', readonly=True)
    line_ids = fields.One2many('select.service.product.wizard.line', 'wizard_id', string='Available Service Products')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        log_id = res.get('status_log_id') or self.env.context.get('default_status_log_id')
        if not log_id and self.env.context.get('active_model') == 'hr.employee.status.log':
            log_id = self.env.context.get('active_id')
        
        if log_id:
            log = self.env['hr.employee.status.log'].browse(log_id)
            res['status_log_id'] = log.id
            res['repair_id'] = log.job_id.id if log.job_id else False
            res['employee_id'] = log.employee_id.id if log.employee_id else False
            dept = log.department_id or (log.employee_id.department_id if log.employee_id else False)
            res['department_id'] = dept.id if dept else False

            domain = [('type', '=', 'service')]
            if dept:
                domain.extend(['|', ('department_id', '=', False), ('department_id', '=', dept.id)])
            
            products = self.env['product.product'].search(domain, order='item_code, name')
            lines = []
            for prod in products:
                lines.append((0, 0, {
                    'product_id': prod.id,
                    'selected': False,
                }))
            res['line_ids'] = lines
        return res

    def action_add_selected_services(self):
        self.ensure_one()
        log = self.status_log_id
        repair = log.job_id
        emp = log.employee_id
        dept = log.department_id or (emp.department_id if emp else False)

        if not repair:
            raise UserError(_("Please select a Job Card on the Status Log first."))

        selected_lines = self.line_ids.filtered(lambda l: l.selected)
        if not selected_lines:
            raise UserError(_("Please select at least one service product to add."))

        created_lines = self.env['fleet.repair.service.line']
        for line in selected_lines:
            prod = line.product_id
            line_dept = dept.id if dept else (prod.department_id.id if prod.department_id else False)
            fru = prod.alloted_fru or 0
            price = 200.0 if (fru and fru > 0) else (prod.list_price or 200.0)
            
            sline = self.env['fleet.repair.service.line'].sudo().create({
                'repair_id': repair.id,
                'product_id': prod.id,
                'item_code': prod.item_code or False,
                'item_code_id': prod.id,
                'name': prod.name,
                'employee_id': emp.id if emp else False,
                'department_id': line_dept,
                'alloted_fru': fru,
                'unit_price': price,
                'quantity': float(fru) if fru > 0 else 1.0,
            })
            created_lines |= sline

        if created_lines and not log.service_line_id:
            first = created_lines[0]
            log.sudo().write({
                'service_line_id': first.id,
                'product_id': first.product_id.id if first.product_id else False,
                'service_name': first.product_id.name if first.product_id else (first.name or ''),
            })

        return {'type': 'ir.actions.act_window_close'}


class SelectServiceProductWizardLine(models.TransientModel):
    _name = 'select.service.product.wizard.line'
    _description = 'Service Product Wizard Line'

    wizard_id = fields.Many2one('select.service.product.wizard', string='Wizard', ondelete='cascade')
    selected = fields.Boolean(string='Select', default=False)
    product_id = fields.Many2one('product.product', string='Service Product', required=True, readonly=True)
    item_code = fields.Char(related='product_id.item_code', string='Item Code', readonly=True)
    name = fields.Char(related='product_id.name', string='Service Name', readonly=True)
    department_id = fields.Many2one('hr.department', related='product_id.department_id', string='Department', readonly=True)
    alloted_fru = fields.Integer(related='product_id.alloted_fru', string='FRU', readonly=True)
    list_price = fields.Float(related='product_id.list_price', string='Price', readonly=True)
