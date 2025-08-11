from odoo import api, models, fields


class BizdomSignal(models.Model):
    _name = 'bizdom.signal'

    name = fields.Char(string="Name")
    company_id = fields.Many2one('res.company', string='Company', index=True, default=lambda self: self.env.company)
