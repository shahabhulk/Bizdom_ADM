from odoo import api, models, fields


class DepartmentCharges(models.Model):
    _name = "department.charges"

    employee_id = fields.Many2one('hr.employee')
    employee_name = fields.Char(related="employee_id.resource_id.name", string="Employee")
    department_id = fields.Many2one('hr.department', string="Department", store=True)
    charge_amount = fields.Float(string="Labour Charge")
    date = fields.Date(string="Date", index=True)
    invoice_line_id = fields.Many2one('account.move.line', string="Source Invoice Line", ondelete='cascade')
    invoice_id = fields.Many2one(related="invoice_line_id.move_id", string="Invoice", store=True)
    invoice_number = fields.Char(related="invoice_line_id.move_id.name", string="Invoice Number", store=True)
    service_description = fields.Char(related="invoice_line_id.name", string="Service Description", store=True)
    car_number = fields.Char(related="invoice_line_id.move_id.license_plate", store=True)
    car_name_line = fields.Char(related="invoice_line_id.move_id.car_name", store=True)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id and self.employee_id.department_id:
            self.department_id = self.employee_id.department_id
