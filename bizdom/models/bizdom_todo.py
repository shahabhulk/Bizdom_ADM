from odoo import fields, models



class BizdomTodo(models.Model):
    _inherit = 'project.task'

    pillar_id = fields.Many2one('bizdom.pillar', string='Pillar')
    bizdom_priority = fields.Selection(
        [
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'Urgent'),
        ],
        string='Bizdom Priority',
        default='low',
        index=True,
    )
    