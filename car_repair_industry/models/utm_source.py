# -*- coding: utf-8 -*-

from odoo import fields, models


class UtmSource(models.Model):
    _inherit = 'utm.source'

    medium_id = fields.Many2one('utm.medium', string='Medium')
