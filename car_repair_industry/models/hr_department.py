# -*- coding: utf-8 -*-
from odoo import models, fields


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    model_ids = fields.Many2many(
        'ir.model',
        string='Models',
        help="Models associated with this department for filtering in job cards and other forms."
    )

    