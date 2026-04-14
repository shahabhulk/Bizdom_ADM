from odoo import models, fields



class CustomResUsers(models.Model):
    _inherit = 'res.users'

    bizdom_allowed_pillar_ids = fields.Many2many(
        'bizdom.pillar',
        string='Bizdom Allowed Pillars'
    )