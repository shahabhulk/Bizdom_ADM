from odoo import api, models, fields


class LabourBilling(models.Model):
    _name = "labour.billing"

    employee_id = fields.Many2one('hr.employee', string="Employee")
    department_id = fields.Many2one(related='employee_id.department_id', store=True)
    charge_amount = fields.Float(string="Labour Charge")
    date = fields.Date(string="Date")
    invoice_line_id = fields.Many2one('account.move.line', string="Source Invoice Line", ondelete='cascade')




