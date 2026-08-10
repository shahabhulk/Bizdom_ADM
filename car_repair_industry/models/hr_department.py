# -*- coding: utf-8 -*-
from odoo import models, fields


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    model_ids = fields.Many2many(
        'ir.model',
        string='Models',
        help="Models associated with this department for filtering in job cards and other forms."
    )


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        domain="[('model_ids.model', '=', 'hr.employee')]"
    )