from odoo import models, fields, api
from odoo.exceptions import UserError


class FleetFeedbackLine(models.Model):
    _inherit = "fleet.feedback.line"

    @api.model
    def create(self, vals):
        line = super().create(vals)
        line._sync_service_feedback()
        return line

    def write(self, vals):
        res = super().write(vals)
        self._sync_service_feedback()
        return res

    def _sync_service_feedback(self):
        """Sync feedback line data to feedback.data model"""
        feedbackdata = self.env['feedback.data']

        for line in self:
            if not line.feedback_id or not line.question_id:
                continue

            # Get or create feedback data record
            feedback_data = feedbackdata.search([
                ('fleet_feedback_line_id', '=', line.id)
            ], limit=1)

            values = {
                'customer_id': line.feedback_id.customer_id.id,
                'feedback_date': line.feedback_id.feedback_date or fields.Date.today(),
                'department_id': line.department_id.id if line.department_id else False,
                'fleet_feedback_line_id': line.id,
            }

            if feedback_data:
                feedback_data.write(values)
            else:
                feedbackdata.create(values)

    # def unlink(self):
    #     """Clean up related feedback.data records when feedback line is deleted"""
    #     feedback_data = self.env['feedback.data'].search([
    #         ('fleet_feedback_line_id', 'in', self.ids)
    #     ])
    #     feedback_data.unlink()
    #     return super().unlink()