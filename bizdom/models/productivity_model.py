from odoo import api, models, fields
from datetime import date
from dateutil.relativedelta import relativedelta


class BizdomProductivity(models.Model):
    _name = 'bizdom.productivity'

    score_name=fields.Char(string='Score Name')
    department_id = fields.Many2one('hr.department',string="Department")
    score_value = fields.Float(string='Score Value')
    entry_date = fields.Date(string='Entry Date', default=fields.Date.context_today)
    sequence_productivity = fields.Char(string="Reference", required=True, copy=False, readonly=True, index=True,
                       default=lambda self: 'New')

    is_last_3_months = fields.Boolean(
        string="Is Last 3 Months",
        compute="_compute_last_3_months",
        store=False
    )

    # def _compute_last_3_months(self):
    #     today = date.today()
    #     # First day of current month minus two months
    #     first_day = (today.replace(day=1) - relativedelta(months=2))
    #     for rec in self:
    #         rec.is_last_3_months = bool(rec.entry_date and rec.entry_date >= first_day)
    #


    @api.model
    def create(self, vals):
        if vals.get('sequence_productivity', 'New') == 'New':
            vals['sequence_productivity'] = self.env['ir.sequence'].next_by_code('bizdom.productivity') or '/'
        return super(BizdomProductivity, self).create(vals)



