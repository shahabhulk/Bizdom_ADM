from odoo import api, models, fields
from odoo.http import request


class FleetLead(models.Model):
    _inherit = 'crm.lead'

    vehicle_model_id = fields.Many2one('fleet.vehicle.model', string='Vehicle Model')
    vehicle_brand_id = fields.Many2one('fleet.vehicle.model.brand', string='Vehicle Brand')
    medium_type = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
    ], string='Medium Type', default='online', store=True)


    def action_open_crm_lead(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'CRM Lead',
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    @api.model
    def action_open_lead_view(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Leads',
            'res_model': 'crm.lead',
            'view_mode': 'tree,form',
            'target': 'current',
        }
