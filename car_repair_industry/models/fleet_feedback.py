from odoo import api, models, fields
from odoo.exceptions import UserError
import logging


# Service Feedback Model
class FleetRepairFeedback(models.Model):
    _name = "fleet.repair.feedback"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Fleet Repair Feedback"
    _order = 'create_date desc'

    name = fields.Char(string="Name")
    fleet_repair_id = fields.Many2one("fleet.repair", string="Fleet Repair")
    job_card_name = fields.Char(
        string="Job Card No",
        compute="_compute_job_card_name",
        store=True
    )
    customer_id = fields.Many2one(related="account_move_id.partner_id", string="Customer", store=True)
    feedback_date = fields.Date(string="Feedback Date")
    question_line_ids = fields.One2many("fleet.feedback.line", "feedback_id", string="Question Line")
    average_rating = fields.Float(string="Average Rating", compute="_compute_average_rating")
    account_move_id = fields.Many2one('account.move', string='Invoice', readonly=True)
    service_advisor_id = fields.Many2one('res.users', string="Service Advisor", compute='_compute_service_advisor',
                                         store=True, readonly=False)
    state = fields.Selection([
        ('psf', 'PSF Call'),
        ('reschedule', 'Reschedule'),
        ('done', 'Done')
    ], string="State", default='psf')

    department_ids = fields.Many2many('hr.department', string='Department')

    @api.depends('fleet_repair_id', 'fleet_repair_id.user_id')
    def _compute_service_advisor(self):
        for rec in self:
            print("\n=== DEBUG SERVICE ADVISOR ===")  # This will print to console
            print(f"Feedback ID: {rec.id}")
            print(f"Fleet Repair ID: {rec.fleet_repair_id.id if rec.fleet_repair_id else 'None'}")
            if rec.fleet_repair_id:
                print(
                    f"Fleet Repair User ID: {rec.fleet_repair_id.user_id.id if rec.fleet_repair_id.user_id else 'None'}")
            rec.service_advisor_id = rec.fleet_repair_id.user_id if rec.fleet_repair_id else False
            print(f"Set service_advisor_id to: {rec.service_advisor_id.id if rec.service_advisor_id else 'None'}")
            print("===========================\n")

    @api.depends('account_move_id', 'account_move_id.job_card_name')
    def _compute_job_card_name(self):
        for record in self:
            record.job_card_name = record.account_move_id.job_card_name if record.account_move_id else False

    @api.model
    def default_get(self, fields):
        res = super(FleetRepairFeedback, self).default_get(fields)
        if self._context.get('default_question_line_ids') is None:
            questions = self.env['fleet.feedback.question'].search([ '&',('active', '=', True), ('department_id', '=', False)])
            res['question_line_ids'] = [(0, 0, {
                'question_id': q.id,
                'rating': False,
                'feedback_comment': False,
            }) for q in questions]

        # Set default values for customer_id and job_card_name if fleet_repair_id is in context
        if self._context.get('default_fleet_repair_id'):
            repair = self.env['fleet.repair'].browse(self._context['default_fleet_repair_id'])
            res.update({
                'fleet_repair_id': repair.id,
                'customer_id': repair.client_id.id,
                'service_advisor_id': repair.user_id.id if repair.user_id else False
            })

            # Set job card name from invoice if available
        if self._context.get('default_account_move_id'):
            move = self.env['account.move'].browse(self._context['default_account_move_id'])
            res.update({
                'job_card_name': move.job_card_name,
                'account_move_id': move.id,
            })

        return res

    @api.onchange('department_ids')
    def _onchange_department_ids(self):
        # Build the domain of questions that should be visible
        current_dept_ids = self.department_ids.ids if self.department_ids else []
        if current_dept_ids:
            question_domain = [
                '&', ('active', '=', True), '|',
                ('department_id', 'in', current_dept_ids),
                ('department_id', '=', False)
            ]
        else:
            # No departments selected: only questions with no department
            question_domain = [('active', '=', True), ('department_id', '=', False)]

        # Preserve existing answers keyed by question
        answers_by_question = {}
        for line in self.question_line_ids:
            if line.question_id:
                answers_by_question[line.question_id.id] = {
                    'rating': line.rating or False,
                    'feedback_comment': line.feedback_comment or False,
                }

        # Compute the questions that should be present
        questions = self.env['fleet.feedback.question'].search(question_domain, order='sequence, id')

        # Rebuild the one2many completely to handle both saved and unsaved lines
        commands = [(5, 0, 0)]  # clear all existing lines
        for q in questions:
            vals = {
                'question_id': q.id,
                'rating': answers_by_question.get(q.id, {}).get('rating', False),
                'feedback_comment': answers_by_question.get(q.id, {}).get('feedback_comment', False),
                'department_id': q.department_id.id,
            }
            commands.append((0, 0, vals))

        self.question_line_ids = commands

    # @api.model_create_multi
    # def create(self, vals_list):
    #     feedbacks = super().create(vals_list)
    #     for feedback in feedbacks:
    #         questions = self.env['fleet.feedback.question'].search([('active', '=', True)])
    #         for question in questions:
    #             self.env['fleet.feedback.line'].create({
    #                 'feedback_id': feedback.id,
    #                 'question_id': question.id,
    #             })
    #     return feedbacks

    def action_done(self):
        for feedback in self:
            # Check if all questions have been rated
            if any(not line.rating for line in feedback.question_line_ids):
                raise UserError("Please rate all questions before submitting the feedback.")
        return self.write({'state': 'done'})

    def action_draft(self):
        self.write({'state': 'draft'})

    @api.depends('question_line_ids.rating')
    def _compute_average_rating(self):
        for record in self:
            if record.question_line_ids:
                ratings = [int(line.rating) for line in record.question_line_ids if line.rating]
                record.average_rating = sum(ratings) / len(ratings) if ratings else 0.0
            else:
                record.average_rating = 0.0


# Service Feedback Line Model
class FleetFeedbackLine(models.Model):
    _name = "fleet.feedback.line"

    feedback_id = fields.Many2one("fleet.repair.feedback", string="Feedback")
    question_id = fields.Many2one(
        "fleet.feedback.question",
        string="Question",
        required=True,
        domain="[('active', '=', True)]"
    )
    # feedback_question = fields.Text(
    #     related="question_id.name",
    #     string="Question",
    #     store=True,
    #     readonly=True
    # )
    rating = fields.Selection([
        ('1', '1 - Poor'),
        ('2', '2 - Fair'),
        ('3', '3 - Average'),
        ('4', '4 - Good'),
        ('5', '5 - Excellent')
    ], string="Rating")
    feedback_comment = fields.Text(string="Comments")

    # _sql_constraints = [
    #     ('unique_question_per_feedback',
    #      'UNIQUE(feedback_id, question_id)',
    #      'Each question can only be added once per feedback!')
    # ]
    department_id = fields.Many2one("hr.department", string="Department")


# Feedback Question Model
class FleetFeedbackQuestion(models.Model):
    _name = "fleet.feedback.question"
    _description = "Fleet Feedback Question"

    name = fields.Text(string="Question")
    active = fields.Boolean(string="Active", default=True)
    sequence = fields.Integer(string="Sequence", default=10)
    department_id = fields.Many2one("hr.department", string="Department")
