from odoo import fields, models



class BizdomTodo(models.Model):
    _inherit = 'project.task'

    pillar_id = fields.Many2one('bizdom.pillar', string='Pillar')
    