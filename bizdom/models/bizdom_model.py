from email.policy import default

from odoo import api, models, fields
from odoo.exceptions import ValidationError
from datetime import date


class BizdomPillar(models.Model):
    _name = 'bizdom.pillar'
    _description = 'Bizdom Pillar'
    _inherit = ['mail.thread']

    name = fields.Char(string="Name")
    company_id = fields.Many2one('res.company', string='Company', index=True, default=lambda self: self.env.company)
    # department_biz_ids = fields.One2many('bizdom.pillar.line', 'pillar_id')
    # score_name_id = fields.Many2one('bizdom.score', string='Score')
    from_date = fields.Date(default=lambda self: date.today().replace(day=1), string='From Date')
    to_date = fields.Date(default=lambda self: date.today(), string='To Date')
    # score_name_ids = fields.One2many('bizdom.pillar.line', 'score_id')
    # score_name_ids = fields.One2many('bizdom.score', 'pillar_id')
    all_score_ids = fields.One2many('bizdom.score', 'pillar_id', string='All Scores')
    score_name_ids = fields.One2many(
        comodel_name='bizdom.score',
        inverse_name='pillar_id',
        string='Favorite Scores',
        compute='_compute_favorite_scores',
        store=False
    )

    @api.depends('all_score_ids.favorite')
    def _compute_favorite_scores(self):
        for record in self:
            record.score_name_ids = record.all_score_ids.filtered(lambda s: s.favorite)

    #
    # @api.constrains('from_date', 'to_date')
    # def _check_date_range(self):
    #     for rec in self:
    #         if rec.from_date and rec.to_date and rec.to_date < rec.from_date:
    #             raise ValidationError("To Date cannot be earlier than From Date.")


# class BizdomPillarLine(models.Model):
#     _name = 'bizdom.pillar.line'
#
#     pillar_id = fields.Many2one('bizdom.pillar')
#     department_id = fields.Many2one('hr.department', string='Department')
#     score_value = fields.Float(string='Score Value',compute="_compute_avg_dep_score")
#     score_name = fields.Char(string="Signal")
#     avg_score = fields.Float(string="Average Score", compute="_compute_avg_score", store=False)
#     score_id = fields.Many2one('bizdom.pillar')
#
#     @api.depends('pillar_id.from_date', 'pillar_id.to_date', 'pillar_id.score_name_id','department_id')
#     def _compute_avg_dep_score(self):
#         for rec in self:
#             avg = 0.0
#             if rec.pillar_id and rec.pillar_id.score_name_id:
#                 signal_name = rec.pillar_id.score_name_id.score_name
#                 from_date = rec.pillar_id.from_date
#                 to_date = rec.pillar_id.to_date
#                 domain = [
#                     ('department_id','=',rec.department_id.id),
#                     ('score_name', '=', signal_name),
#                     ('entry_date', '>=', from_date),
#                     ('entry_date', '<=', to_date)
#                 ]
#
#                 scores = self.env['bizdom.productivity'].search(domain)
#                 print(scores)
#                 if scores:
#                     avg = sum(x.score_value for x in scores) / len(scores)
#             rec.score_value = avg
#
#     @api.depends('score_id.from_date', 'score_id.to_date', 'score_id.score_name_id')
#     def _compute_avg_score(self):
#         for rec in self:
#             avg = 0.0
#             if rec.score_id and rec.score_id.score_name_id:
#                 signal_name = rec.score_id.score_name_id.score_name
#                 from_date = rec.score_id.from_date
#                 to_date = rec.score_id.to_date
#                 domain = [
#                     ('score_name', '=', signal_name),
#                     ('entry_date', '>=', from_date),
#                     ('entry_date', '<=', to_date)
#                 ]
#                 scores = self.env['bizdom.productivity'].search(domain)
#                 if scores:
#                     avg = sum(x.score_value for x in scores) / len(scores)
#             rec.avg_score = avg


# @api.depends('pillar_id.score_name_id', 'department_id', 'pillar_id.from_date', 'pillar_id.to_date')
# def _compute_score_value(self):
#     for line in self:
#         value = 0.0
#         if line.department_id and line.pillar_id and line.pillar_id.score_name_id:
#             score_name = line.pillar_id.score_name_id.score_name
#             from_date = line.pillar_id.from_date
#             to_date = line.pillar_id.to_date
#             if score_name and score_name.strip().lower() == 'productivity' and from_date and to_date:
#                 employees = self.env['hr.employee'].search([('department_id', '=', line.department_id.id)])
#                 productivities = []
#                 for emp in employees:
#                     timesheet_lines = self.env['account.analytic.line'].search([
#                         ('employee_id', '=', emp.id),
#                         ('date', '>=', from_date),
#                         ('date', '<=', to_date)
#                     ])
#                     actual_hours = sum(timesheet_lines.mapped('unit_amount'))
#                     personal_prod = (actual_hours / 200) * 100 if actual_hours else 0
#                     productivities.append(personal_prod)
#                 value = round(sum(productivities) / len(productivities), 2) if productivities else 0.0
#         line.score_value = value


# class HrDepartment(models.Model):
#     _inherit = 'hr.department'
#
#     @api.model
#     def unlink(self):
#         # For each department being deleted
#         for department in self:
#             # Find and delete all linked bizdom pillar lines
#             lines = self.env['bizdom.pillar.line'].sudo().search([('department_id', '=', department.id)])
#             lines.unlink()
#         return super(HrDepartment, self).unlink()
