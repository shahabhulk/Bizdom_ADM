from odoo import models, fields, api


class FeedbackData(models.Model):
    _name = "feedback.data"
    _description = "Feedback Data"

    customer_id = fields.Many2one('res.partner', string="Customer")
    feedback_date = fields.Date(string="Feedback Date")
    department_id = fields.Many2one('hr.department', string="Department")
    fleet_feedback_line_id = fields.Many2one('fleet.feedback.line', string="Feedback Line", ondelete="cascade")
    invoice_name = fields.Char(related='fleet_feedback_line_id.feedback_id.name', string="Invoice", store=True)
    job_card_name = fields.Char(related='fleet_feedback_line_id.feedback_id.job_card_name', string="Job Card",
                                store=True)
    feedback_question = fields.Text(related='fleet_feedback_line_id.question_id.name', string="Feedback Question")
    rating = fields.Selection(related='fleet_feedback_line_id.rating', string="Rating", store=True)
    total_average_rating = fields.Float(related='fleet_feedback_line_id.feedback_id.average_rating',
                                        string="Total Average Rating", store=True)

    def sync_feedback_data(self):
        """Manually trigger feedback data sync for ALL feedback records"""
        # Clear existing feedback data to prevent duplicates
        self.search([]).unlink()

        # Get all feedback records
        feedbacks = self.env['fleet.repair.feedback'].search([])
        total_synced = 0

        for feedback in feedbacks:
            for line in feedback.question_line_ids:
                if hasattr(line, '_sync_service_feedback'):
                    line._sync_service_feedback()
                    total_synced += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success' if total_synced > 0 else 'No Data',
                'message': f'Synced {total_synced} feedback records!' if total_synced > 0
                else 'No feedback records found to sync',
                'sticky': False,
            }
        }
