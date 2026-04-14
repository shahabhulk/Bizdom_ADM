from odoo import models, fields, api
from odoo.exceptions import UserError


class FleetFeedbackLine(models.Model):
    _inherit = "fleet.feedback.line"

    invoice_name = fields.Char(related='feedback_id.name', string="Invoice", store=True)
    job_card_name = fields.Char(related='feedback_id.job_card_name', string="Job Card", store=True)
    customer_id = fields.Many2one(related='feedback_id.customer_id', string="Customer", store=True)
    feedback_date = fields.Date(related='feedback_id.feedback_date', string="Feedback Date", store=True)