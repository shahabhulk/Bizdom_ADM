from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class BizdomScore(models.Model):
    _name = 'bizdom.score'
    _description = 'Bizdom Score'

    score_name = fields.Char(string="Score Name", required=True)
    score_line_ids = fields.One2many('bizdom.score.line', 'score_id')
    company_id = fields.Many2one('res.company', string='Company', index=True, default=lambda self: self.env.company)
    # department_id = fields.Many2one('hr.department', string="Department", required=True)
    # score_value = fields.Float(string="Score Value", compute='_compute_score_value', store=False)
    from_date = fields.Date(default=lambda self: date.today().replace(day=1), string='From Date')
    to_date = fields.Date(default=lambda self: date.today(), string='To Date')
    pillar_id = fields.Many2one('bizdom.pillar', string='Pillar Name')
    total_score_value = fields.Float(string='Total Score', compute="_compute_total_score_value", store=True)
    max_score_percentage = fields.Float(string="Max Score")
    min_score_percentage = fields.Float(string="Min Score")
    max_score_number = fields.Float(string="Max Score")
    min_score_number = fields.Float(string="Min Score")
    favorite = fields.Boolean(string='Favorite', default=False)

    type = fields.Selection([
        ('percentage', 'Percentage'),
        ('value', 'Value')
    ])
    # formatted_max_score = fields.Char(
    #     string="Max Score",
    #     compute="_compute_formatted_scores",
    #     store=True
    # )
    #
    # formatted_min_score = fields.Char(
    #     string="Min Score",
    #     compute="_compute_formatted_scores",
    #     store=True
    # )
    _rec_name = 'score_name'

    # @api.depends('max_score_value', 'min_score_value', 'type')
    # def _compute_formatted_scores(self):
    #     for rec in self:
    #         if rec.type == 'percentage':
    #             rec.formatted_max_score = f"{rec.max_score_value} %"
    #             rec.formatted_min_score = f"{rec.min_score_value} %"
    #         else:
    #             rec.formatted_max_score = rec.max_score_value
    #             rec.formatted_min_score = rec.min_score_value

    @api.constrains('favorite')
    def check_favorite_limit(self):
        for rec in self:
            if rec.favorite and rec.pillar_id:
                favorites = self.search_count([
                    ('favorite', '=', 'True'),
                    ('pillar_id', '=', rec.pillar_id.id),
                    ('id', '!=', rec.id)
                ])

                if favorites >= 3:
                    raise ValidationError("You can only choose up to 3 favorite scores per pillar.")

    @api.depends('score_line_ids.score_value')
    def _compute_total_score_value(self):
        for rec in self:
            total = 0.0
            for line in rec.score_line_ids:
                total += line.score_value
            rec.total_score_value = total

    # @api.constrains('pillar_id')
    # def _check_pillar_has_departments(self):
    #     for rec in self:
    #         if rec.pillar_id:
    #             # Get pillar lines for this pillar
    #             pillar_lines = self.env['bizdom.score.line'].search([('pillar_id', '=', rec.pillar_id.id)])
    #             if not pillar_lines:
    #                 raise ValidationError(
    #                     'Selected Pillar has no departments! Please select a pillar with departments.')

    # @api.onchange('pillar_id')
    # def _onchange_pillar_id(self):
    #     if self.pillar_id and not self.score_line_ids:
    #         department_lines = self.env['bizdom.score.line'].search([('pillar_id', '=', self.pillar_id.id)])
    #         lines = []
    #         for pline in department_lines:
    #             if pline.department_id:  # sanity check
    #                 lines.append((0, 0, {
    #                     'department_id': pline.department_id.id
    #                 }))
    #         self.score_line_ids = lines
    #
    # @api.constrains('score_name')
    # def _check_unique_score_name(self):
    #     for rec in self:
    #         if rec.score_name:
    #             domain = [('id', '!=', rec.id), ('score_name', '=ilike', rec.score_name)]
    #             if self.search_count(domain):
    #                 raise ValidationError('Score Name must be unique (case-insensitive)!')


class BizdomScoreLine(models.Model):
    _name = 'bizdom.score.line'
    _description = "Bizdom Score Line"

    department_id = fields.Many2one('hr.department', string="Department", required=True)
    score_value = fields.Float(string="Score Value", store=False)
    score_id = fields.Many2one('bizdom.score')
    # pillar_id=fields.Many2one('bizdom.pillar')

    # @api.depends('score_id.score_name', 'department_id', 'score_id.from_date', 'score_id.to_date')
    # def _compute_score_value(self):
    #     for record in self:
    #         value = 0.0
    #         score = record.score_id
    #         if score and record.department_id and score.from_date and score.to_date:
    #             if score.score_name and score.score_name.strip().lower() == 'productivity':
    #                 employees = self.env['hr.employee'].search([('department_id', '=', record.department_id.id)])
    #                 productivities = []
    #                 for emp in employees:
    #                     timesheet_lines = self.env['account.analytic.line'].search([
    #                         ('employee_id', '=', emp.id),
    #                         ('date', '>=', score.from_date),
    #                         ('date', '<=', score.to_date)
    #                     ])
    #                     actual_hours = sum(timesheet_lines.mapped('unit_amount'))
    #                     personal_prod = (actual_hours / 200) * 100 if actual_hours else 0
    #                     productivities.append(personal_prod)
    #                 value = round(sum(productivities) / len(productivities), 2) if productivities else 0.0
    #         record.score_value = value
