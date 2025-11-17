from odoo import models, fields, api, _
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
    dashboard_overview_data = fields.Text(compute='_compute_dashboard_overview_data', string='Dashboard Overview')

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

        # Check if we're in form view
        if self._context.get('view_type') == 'form' or self._context.get('params', {}).get('view_type') == 'form':
            # Update only the current record
            self.write({
                'start_date': start_of_week,
                'end_date': today
            })
        else:
            # Update all visible records in list view
            domain = self._context.get('search_default_', [])
            records = self.search(domain)
            records.write({
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

        # Check if we're in form view
        if self._context.get('view_type') == 'form' or self._context.get('params', {}).get('view_type') == 'form':
            # Update only the current record
            self.write({
                'start_date': start_of_month,
                'end_date': today
            })
        else:
            # Update all visible records in list view
            domain = self._context.get('search_default_', [])
            records = self.search(domain)
            records.write({
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

        # Check if we're in form view
        if self._context.get('view_type') == 'form' or self._context.get('params', {}).get('view_type') == 'form':
            # Update only the current record
            self.write({
                'start_date': start_of_year,
                'end_date': today
            })
        else:
            # Update all visible records in list view
            domain = self._context.get('search_default_', [])
            records = self.search(domain)
            records.write({
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

    @api.model
    def get_score_with_date_filter(self, score_id, start_date, end_date):
        """
        Compute and return the context_total_score for a score with given date range.
        This method is called from the frontend dashboard when filters (MTD/WTD/YTD) are applied.
        
        :param score_id: ID of the score record
        :param start_date: Start date string in YYYY-MM-DD format
        :param end_date: End date string in YYYY-MM-DD format
        :return: Dictionary with context_total_score
        """
        score = self.browse(score_id)
        if not score.exists():
            return {'context_total_score': 0.0}
        
        # Convert string dates to date objects if needed
        if isinstance(start_date, str):
            from datetime import datetime
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            from datetime import datetime
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Compute score with date context
        score_ctx = score.with_context(
            force_date_start=start_date,
            force_date_end=end_date
        )
        
        # Force recomputation of context_total_score
        score_ctx._compute_context_total_score()
        
        return {
            'context_total_score': score_ctx.context_total_score or 0.0
        }

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

    # @api.model
    # def get_scores_for_dates(self, domain=None, **kwargs):
    #     domain = domain or []
    #     force_date_start = kwargs.get('force_date_start')
    #     force_date_end = kwargs.get('force_date_end')
    #
    #     print("\n=== BIZDOM DEBUG ===")
    #     print("force_date_start:", force_date_start)
    #     print("force_date_end:", force_date_end)
    #     print("====================\n")
    #
    #     scores = self.search(domain)
    #     print("Found scores:", scores.mapped("score_name"))
    #
    #     result = []
    #     for score in scores:
    #         score_ctx = score.with_context(
    #             force_date_start=force_date_start,
    #             force_date_end=force_date_end
    #         )
    #         score_ctx._compute_context_total_score()
    #         print(f"Score {score.score_name} computed => {score_ctx.context_total_score}")
    #
    #         result.append({
    #             'id': score.id,
    #             'score_name': score.score_name,
    #             'score_value': score_ctx.context_total_score,
    #             'pillar_id': score.pillar_id.id,
    #             'favorite': score.favorite,
    #         })
    #     return result

    #

    @api.model
    def get_score_dashboard_data(self, score_id, filter_type='MTD'):
        """
        Get score dashboard data with historical overview in the specified format.
        
        :param score_id: ID of the score record
        :param filter_type: Filter type (MTD, WTD, or YTD)
        :return: Dictionary with statusCode, message, score_id, score_name, and overview
        """
        score = self.browse(score_id)
        if not score.exists():
            return {
                'statusCode': 200,
                'message': 'Score Overview',
                'score_id': score_id,
                'score_name': '',
                'overview': []
            }
        
        # Get historical overview data based on filter type
        overview = self._get_score_overview(score, filter_type)
        
        return {
            'statusCode': 200,
            'message': 'Score Overview',
            'score_id': score_id,
            'score_name': score.score_name,
            'overview': overview
        }
    
    def _get_score_overview(self, score, filter_type='MTD'):
        """
        Get historical score overview data based on filter type.
        
        :param score: Score record
        :param filter_type: MTD, WTD, or YTD
        :return: List of dictionaries with period data
        """
        from datetime import datetime, timedelta
        from dateutil.relativedelta import relativedelta
        import calendar
        
        filter_type = filter_type or 'MTD'
        if filter_type not in ('MTD',):
            filter_type = 'MTD'

        today = fields.Date.today()
        overview = []
        
        if filter_type == 'WTD':
            # Get past 3 weeks of WTD data (including current week)
            for i in range(2, -1, -1):  # 2 weeks back to current week (0)
                week_end = today - timedelta(days=i*7)
                day_of_week = week_end.weekday()
                week_start = week_end - timedelta(days=day_of_week)
                # For current week, end date should be today
                if i == 0:
                    week_end = today
                
                # Calculate score for this period
                actual_value = self._calculate_score_for_period(score, week_start, week_end)
                
                # Format dates as DD-MM-YYYY
                start_date_str = week_start.strftime('%d-%m-%Y')
                end_date_str = week_end.strftime('%d-%m-%Y')
                
                # Determine week number (Week 1, Week 2, etc.)
                week_num = 3 - i  # Week 3 (oldest), Week 2, Week 1 (current)
                
                overview.append({
                    'period': f'Week {week_num}',
                    'start_date': start_date_str,
                    'end_date': end_date_str,
                    'actual_value': round(actual_value, 1) if actual_value else 0
                })
        
        elif filter_type == 'MTD':
            # Get past 3 months of MTD data (including current month)
            for i in range(2, -1, -1):  # 2 months back to current month (0)
                month_date = today - relativedelta(months=i)
                start_date = month_date.replace(day=1)
                # End date is the last day of that month or today if it's the current month
                if i == 0:
                    end_date = today
                else:
                    # For past months, calculate MTD up to the same day of month as today
                    # But if that day doesn't exist in that month, use the last day
                    target_day = today.day
                    last_day = calendar.monthrange(month_date.year, month_date.month)[1]
                    end_day = min(target_day, last_day)
                    end_date = month_date.replace(day=end_day)
                
                # Calculate score for this period
                actual_value = self._calculate_score_for_period(score, start_date, end_date)
                
                # Format dates as DD-MM-YYYY
                start_date_str = start_date.strftime('%d-%m-%Y')
                end_date_str = end_date.strftime('%d-%m-%Y')
                
                # Month name
                month_name = month_date.strftime('%B %Y')
                
                overview.append({
                    'month': month_name,
                    'start_date': start_date_str,
                    'end_date': end_date_str,
                    'actual_value': round(actual_value, 1) if actual_value else 0
                })
        
        elif filter_type == 'YTD':
            # Get past 3 years of YTD data (including current year)
            for i in range(2, -1, -1):  # 2 years back to current year (0)
                year_date = today - relativedelta(years=i)
                start_date = year_date.replace(month=1, day=1)
                if i == 0:
                    end_date = today
                else:
                    # For past years, calculate YTD up to the same month and day as today
                    try:
                        end_date = year_date.replace(month=today.month, day=today.day)
                    except ValueError:
                        # Handle case where Feb 29 doesn't exist in non-leap year
                        end_date = year_date.replace(month=today.month, day=28)
                
                # Calculate score for this period
                actual_value = self._calculate_score_for_period(score, start_date, end_date)
                
                # Format dates as DD-MM-YYYY
                start_date_str = start_date.strftime('%d-%m-%Y')
                end_date_str = end_date.strftime('%d-%m-%Y')
                
                year_label = str(year_date.year)
                
                overview.append({
                    'year': year_label,
                    'start_date': start_date_str,
                    'end_date': end_date_str,
                    'actual_value': round(actual_value, 1) if actual_value else 0
                })
        
        return overview
    
    def _calculate_score_for_period(self, score, start_date, end_date):
        """
        Calculate score value for a specific date period.
        
        :param score: Score record
        :param start_date: Start date
        :param end_date: End date
        :return: Calculated score value
        """
        # Use the existing context_total_score computation logic
        score_ctx = score.with_context(
            force_date_start=start_date,
            force_date_end=end_date
        )
        score_ctx._compute_context_total_score()
        return score_ctx.context_total_score or 0.0

    @api.depends_context('current_filter')
    def _compute_dashboard_overview_data(self):
        """Compute dashboard overview data based on context filter"""
        import json
        for rec in self:
            # Get filter from context, default to MTD
            filter_type = self._context.get('current_filter', 'MTD')
            overview_data = self.get_score_dashboard_data(rec.id, filter_type)
            rec.dashboard_overview_data = json.dumps(overview_data)

    def action_back(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

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


            elif rec.pillar_id.name == "Finance":
                if rec.score_name == "Income":
                    pass
                elif rec.score_name=="Expense":
                    pass

                elif rec.score_name=="Cashflow":
                    pass


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


