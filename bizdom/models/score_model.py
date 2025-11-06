from odoo import models, fields, api,_
from odoo.exceptions import ValidationError
from datetime import date, timedelta
from odoo.exceptions import UserError


class BizdomScore(models.Model):
    _name = 'bizdom.score'
    _description = 'Bizdom Score'

    score_name = fields.Char(string="Score Name", required=True)
    score_line_ids = fields.One2many('bizdom.score.line', 'score_id')
    company_id = fields.Many2one('res.company', string='Company', index=True, default=lambda self: self.env.company)
    # department_id = fields.Many2one('hr.department', string="Department", required=True)
    # score_value = fields.Float(string="Score Value", compute='_compute_score_value', store=False)
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    # from_date = fields.Date(default=lambda self: date.today().replace(day=1), string='From Date')
    # to_date = fields.Date(default=lambda self: date.today(), string='To Date')
    pillar_id = fields.Many2one('bizdom.pillar', string='Pillar Name')
    total_score_value = fields.Float(string='Total Score', compute="_compute_total_score_value", store=True)
    total_score_value_percentage = fields.Float(string='Total Score', compute="_compute_total_score_value", store=True)
    max_score_percentage = fields.Float(string="Max Score")
    min_score_percentage = fields.Float(string="Min Score")
    max_score_number = fields.Float(string="Max Score")
    min_score_number = fields.Float(string="Min Score")
    # model_ref_id = fields.Many2one('ir.model', string="Information Model")
    favorite = fields.Boolean(string='Favorite', default=False)
    context_total_score = fields.Float(compute='_compute_context_total_score')

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

    # @api.depends('score_line_ids.score_value')
    # def _compute_total_score_value(self):
    #     for rec in self:
    #         total = 0.0
    #         for line in rec.score_line_ids:
    #             total += line.score_value
    #         rec.total_score_value = total

    @api.constrains('start_date', 'end_date')
    def _check_date_range(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError("Start Date cannot be greater than End Date.")

    def action_set_wtd(self):
        today = fields.Date.today()
        start_of_week = today - timedelta(days=today.weekday())
        self.write({
            'start_date': start_of_week,
            'end_date': today
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    def action_set_mtd(self):
        today = fields.Date.today()
        start_of_month = today.replace(day=1)
        self.write({
            'start_date': start_of_month,
            'end_date': today
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    def action_set_ytd(self):
        today = fields.Date.today()
        start_of_year = today.replace(month=1, day=1)
        self.write({
            'start_date': start_of_year,
            'end_date': today
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    # for the frontend app
    @api.model
    def _recompute_with_dates(self, record, start_date, end_date):
        record_ctx = record.with_context(
            force_date_start=start_date,
            force_date_end=end_date
        )
        # Invalidate and recompute the context value
        record_ctx.invalidate_recordset(['context_total_score'])
        value = record_ctx.context_total_score
        print(f"Context value for {record.id} with dates {start_date} to {end_date}: {value}")
        # Return both the record and the value
        return {'record': record_ctx, 'value': value}

    # for the frontend app
    @api.depends('start_date', 'end_date', 'score_name')
    def _compute_context_total_score(self):
        for rec in self:
            rec.context_total_score = 0.0
            start_date = self._context.get('force_date_start', rec.start_date)
            end_date = self._context.get('force_date_end', rec.end_date)

            if not start_date or not end_date:
                rec.context_total_score = 0
                continue

            if rec.pillar_id.name == "Operations":
                print("lkjasfdlkja")
                if rec.score_name == "Labour":
                    records = self.env['labour.billing'].search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date)
                    ])
                    rec.context_total_score = sum(records.mapped('charge_amount'))
                elif rec.score_name == "Customer Satisfaction":
                    records = self.env['fleet.repair.feedback'].search([
                        ('feedback_date', '>=', start_date),
                        ('feedback_date', '<=', end_date)
                    ])
                    # calculate the average rating
                    list_of_records = records.mapped('average_rating')
                    average_total_rating = sum(list_of_records) / len(list_of_records) if len(list_of_records) else 0
                    average_total_rating_percentage = average_total_rating / 5
                    rec.context_total_score = average_total_rating_percentage
                elif rec.score_name == "TAT":
                    repair_delivered_records = self.env['fleet.repair'].search([
                        ('invoice_order_id', '!=', False),
                        ('invoice_order_id.invoice_date', '!=', False),
                        ('invoice_order_id.invoice_date', '>=', start_date),
                        ('invoice_order_id.invoice_date', '<=', end_date)
                    ])
                    repair_pending_records = self.env['fleet.repair'].search([
                        ('receipt_date', '>=', start_date),
                        ('receipt_date', '<=', end_date),
                        ('invoice_order_id', '=', False)
                    ])
                    pre_repair_pending_records = self.env['fleet.repair'].search([
                        ('receipt_date', '<', start_date),
                        ('invoice_order_id', '=', False)
                    ])
                    # for i in repair_records:
                    #     print(i.job_card_display) mj
                    total_delivered_tat_days = 0.0
                    total_pending_tat_days = 0.0
                    total_pre_pending_tat_days = 0.0
                    valid_pre_pending_records = 0
                    valid_delivered_records = 0
                    valid_pending_records = 0
                    for repair in repair_delivered_records:
                        if repair.receipt_date and repair.invoice_order_id.invoice_date:
                            receipt_date = repair.receipt_date.date() if hasattr(repair.receipt_date,
                                                                                 'date') else repair.receipt_date
                            invoice_date = repair.invoice_order_id.invoice_date.date() if hasattr(
                                repair.invoice_order_id.invoice_date, 'date') else repair.invoice_order_id.invoice_date
                            delta = invoice_date - receipt_date
                            total_delivered_tat_days += abs(delta.days)
                            valid_delivered_records += 1
                            print(repair.job_card_display, ":", delta.days)

                    for repair in repair_pending_records:
                        if repair.receipt_date and not repair.invoice_order_id.invoice_date:
                            receipt_date = repair.receipt_date.date() if hasattr(repair.receipt_date,
                                                                                 'date') else repair.receipt_date
                            end_date_dt = end_date.date() if hasattr(end_date, 'date') else end_date
                            delta = end_date_dt - receipt_date
                            total_pending_tat_days += abs(delta.days)
                            valid_pending_records += 1
                            print(repair.job_card_display, ":", delta.days)

                    for repair in pre_repair_pending_records:
                        if repair.receipt_date and not repair.invoice_order_id.invoice_date:
                            receipt_date = repair.receipt_date.date() if hasattr(repair.receipt_date,
                                                                                 'date') else repair.receipt_date
                            end_date_dt = end_date.date() if hasattr(end_date, 'date') else end_date
                            delta = end_date_dt - receipt_date
                            total_pending_tat_days += abs(delta.days)
                            valid_pending_records += 1
                            print(repair.job_card_display, ":", delta.days)

                    rec.total_score_value = (
                                                        total_pending_tat_days + total_delivered_tat_days + total_pre_pending_tat_days) / (
                                                        valid_pending_records + valid_delivered_records + valid_pre_pending_records) if valid_pending_records + valid_delivered_records + valid_pre_pending_records > 0 else 0.0
                    rec.context_total_score = rec.total_score_value

            elif rec.pillar_id.name == "Sales and Marketing":
                if rec.score_name == "Leads":
                    records = self.env['crm.lead'].search([
                        ('create_date', '>=', start_date),
                        ('create_date', '<=', end_date),
                        ('stage_id', 'in', [1, 2]),
                        ('company_id', '=', self.company_id.id)
                    ])
                    rec.total_score_value = len(records)
                    rec.context_total_score = rec.total_score_value

    # for the backend app
    @api.depends('start_date', 'end_date', 'score_name')
    def _compute_total_score_value(self):
        for rec in self:
            # _ = self._context
            start_date = self._context.get('force_date_start', rec.start_date)
            end_date = self._context.get('force_date_end', rec.end_date)

            if not start_date or not end_date:
                rec.total_score_value = 0
                continue

            if rec.pillar_id.name == "Operations":
                if rec.score_name == "Labour":

                    # Check if we have any records in the date range
                    records = self.env['labour.billing'].search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date)
                    ])
                    total = sum(records.mapped('charge_amount'))
                    rec.total_score_value = total


                elif rec.score_name == "TAT":
                    repair_delivered_records = self.env['fleet.repair'].search([
                        ('invoice_order_id', '!=', False),
                        ('invoice_order_id.invoice_date', '!=', False),
                        ('invoice_order_id.invoice_date', '>=', start_date),
                        ('invoice_order_id.invoice_date', '<=', end_date)
                    ])
                    repair_pending_records = self.env['fleet.repair'].search([
                        ('receipt_date', '>=', start_date),
                        ('receipt_date', '<=', end_date),
                        ('invoice_order_id', '=', False)
                    ])
                    pre_repair_pending_records = self.env['fleet.repair'].search([
                        ('receipt_date', '<', start_date),
                        ('invoice_order_id', '=', False)
                    ])
                    # for i in repair_records:
                    #     print(i.job_card_display) mj
                    total_delivered_tat_days = 0.0
                    total_pending_tat_days = 0.0
                    total_pre_pending_tat_days = 0.0
                    valid_pre_pending_records = 0
                    valid_delivered_records = 0
                    valid_pending_records = 0
                    for repair in repair_delivered_records:
                        if repair.receipt_date and repair.invoice_order_id.invoice_date:
                            delta = repair.invoice_order_id.invoice_date - repair.receipt_date.date()
                            total_delivered_tat_days += abs(delta.days)
                            valid_delivered_records += 1
                            print(repair.job_card_display, ":", delta.days)

                    for repair in repair_pending_records:
                        if repair.receipt_date and not repair.invoice_order_id.invoice_date:
                            delta = end_date - repair.receipt_date.date()
                            total_pending_tat_days += abs(delta.days)
                            valid_pending_records += 1
                            print(repair.job_card_display, ":", delta.days)

                    for repair in pre_repair_pending_records:
                        if repair.receipt_date and not repair.invoice_order_id.invoice_date:
                            delta = end_date - repair.receipt_date.date()
                            total_pending_tat_days += abs(delta.days)
                            valid_pending_records += 1
                            print(repair.job_card_display, ":", delta.days)

                    rec.total_score_value = (
                                                    total_pending_tat_days + total_delivered_tat_days + total_pre_pending_tat_days) / (
                                                    valid_pending_records + valid_delivered_records + valid_pre_pending_records) if valid_pending_records + valid_delivered_records + valid_pre_pending_records > 0 else 0.0

                    # rec.total_score_value_percentage = rec.total_score_value

                    # for repair in repair_records:
                    #     if repair.receipt_date and repair.invoice_order_id.invoice_date:
                    #         delta = repair.invoice_order_id.invoice_date - repair.receipt_date.date()
                    #         total_tat_days += abs(delta.days)
                    #         valid_records += 1
                    #         print(repair.job_card_display, ":", delta.days)
                    #
                    # rec.total_score_value = total_tat_days / valid_records if valid_records > 0 else 0.0
                    # rec.total_score_value_percentage = rec.total_score_value

                elif rec.score_name == "Customer Satisfaction":
                    print("helloooooo")
                    records = self.env['fleet.repair.feedback'].search([
                        ('feedback_date', '>=', start_date),
                        ('feedback_date', '<=', end_date)
                    ])
                    list_of_records = list(records.mapped('average_rating'))
                    average_total_rating = sum(list_of_records) / len(list_of_records) if len(
                        list_of_records) > 0 else 0.0
                    average_total_rating_percentage = average_total_rating / 5
                    rec.total_score_value = average_total_rating_percentage
                    rec.total_score_value_percentage = average_total_rating_percentage

            elif rec.pillar_id.name == "Sales and Marketing":
                if rec.score_name == "Leads":
                    records = self.env['crm.lead'].search([
                        ('create_date', '>=', start_date),
                        ('create_date', '<=', end_date),
                        ('stage_id', 'in', [1, 2]),
                        ('company_id', '=', self.company_id.id)
                    ])
                    rec.total_score_value = len(records)


class BizdomScoreLine(models.Model):
    _name = 'bizdom.score.line'
    _description = "Bizdom Score Line"

    department_id = fields.Many2one('hr.department', string="Department", required=True)
    score_value = fields.Float(string="Score Value", compute="_compute_score_value", store=False)
    score_id = fields.Many2one('bizdom.score')
    max_dep_score = fields.Float(string="Max Score")
    min_dep_score = fields.Float(string="Min Score")

    # pillar_id=fields.Many2one('bizdom.pillar')
    @api.onchange('score_id.start_date', 'score_id.end_date', 'score_id.score_name', 'department_id')
    def _compute_score_value(self):
        for rec in self:
            rec.score_value = 0.0
            if not rec.score_id or not rec.department_id:
                continue

            # Common domain filters
            # domain = [('department_id', '=', rec.department_id.id)]

            if rec.score_id.pillar_id.name == "Operations":
                if rec.score_id.score_name == "Labour":
                    domain = [('department_id', '=', rec.department_id.id)]
                    # Date domain for labour billing
                    labour_domain = list(domain)
                    if rec.score_id.start_date:
                        labour_domain.append(('date', '>=', rec.score_id.start_date))
                    if rec.score_id.end_date:
                        labour_domain.append(('date', '<=', rec.score_id.end_date))

                    records = self.env["labour.billing"].search(labour_domain)
                    rec.score_value = sum(records.mapped('charge_amount'))
                elif rec.score_id.score_name == "Customer Satisfaction":
                    # Date domain for feedback
                    feedback_domain = []
                    if rec.score_id.start_date:
                        feedback_domain.append(('feedback_date', '>=', rec.score_id.start_date))
                    if rec.score_id.end_date:
                        feedback_domain.append(('feedback_date', '<=', rec.score_id.end_date))

                    # Get all feedback records for the department
                    record_jc = self.env['feedback.data'].search(feedback_domain)
                    for i in record_jc:
                        print("jc name", i.job_card_name)
                    domain = [('department_id', '=', rec.department_id.id)]
                    records = self.env['feedback.data'].search(feedback_domain + domain)
                    ratings = [int(rating) for rating in records.mapped('rating') if rating]
                    list_of_jc = list(set(records.mapped('job_card_name')))
                    print('list', list_of_jc)
                    average_total_rating = sum(ratings) / len(list_of_jc) if len(list_of_jc) > 0 else 0.0
                    average_total_rating_percentage = average_total_rating / 5 * 100
                    rec.score_value = average_total_rating_percentage

                elif rec.score_id.score_name == "TAT":
                    delivered_records = self.env['fleet.repair'].search([
                        ('invoice_order_id', '!=', False),
                        ('invoice_order_id.invoice_date', '!=', False),
                        ('invoice_order_id.invoice_date', '>=', rec.score_id.start_date),
                        ('invoice_order_id.invoice_date', '<=', rec.score_id.end_date)

                    ])

                    # for i in delivered_records:
                    #     print("jcc",i.job_card_display)

                    delivered_rec = []
                    for i in delivered_records:
                        for j in i.fleet_work_line_ids:
                            if j.department_type_id.id == rec.department_id.id:
                                delivered_rec.append(j)

                    for i in delivered_rec:
                        print("ssss", i.repair_id.job_card_display)

                    job_card_num = []
                    for i in delivered_rec:
                        job_card_num.append(i.repair_id.job_card_display)

                    job_card_num = list(set(job_card_num))
                    print("job_card_num", len(job_card_num))

                    total_hours = 0.0
                    for record in delivered_rec:
                        # Assuming time_diff is in hours with decimal minutes (e.g., 1.5 hours = 1 hour 30 minutes)
                        hours = record.time_diff  # Get whole hours
                        # Get minutes from decimal part
                        total_hours += hours  # Convert everything to hours

                    total_days = total_hours / 24.0  # Convert total hours to days
                    print("total_hours", total_hours, "total_days", total_days, 'length', len(list(set(delivered_rec))))
                    rec.score_value = total_days / len(job_card_num) if len(job_card_num) > 0 else 0.0
