from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta
from odoo.exceptions import UserError


class BizdomScore(models.Model):
    _name = 'bizdom.score'
    _description = 'Bizdom Score'

    score_name = fields.Char(string="Score Name", required=True, index=True)
    score_line_ids = fields.One2many('bizdom.score.line', 'score_id')
    company_id = fields.Many2one('res.company', string='Company', index=True, default=lambda self: self.env.company)
    # department_id = fields.Many2one('hr.department', string="Department", required=True)
    # score_value = fields.Float(string="Score Value", compute='_compute_score_value', store=False)
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    # from_date = fields.Date(default=lambda self: date.today().replace(day=1), string='From Date')
    # to_date = fields.Date(default=lambda self: date.today(), string='To Date')
    pillar_id = fields.Many2one('bizdom.pillar', string='Pillar Name', index=True)
    total_score_value = fields.Float(string='Total Score', compute="_compute_total_score_value", store=True)
    total_score_value_percentage = fields.Float(string='Total Score', compute="_compute_total_score_value", store=True)
    max_score_percentage = fields.Float(string="Max Score")
    min_score_percentage = fields.Float(string="Min Score")
    max_score_number = fields.Float(string="Max Score")
    min_score_number = fields.Float(string="Min Score")
    # model_ref_id = fields.Many2one('ir.model', string="Information Model")
    favorite = fields.Boolean(string='Favorite', default=False, index=True)
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

    @api.onchange('start_date', 'end_date')
    def _onchange_dates(self):
        """Trigger recalculation of score lines when dates change"""
        result = {}
        if self.score_line_ids:
            # Build the command list to update all score lines
            line_commands = []
            for line in self.score_line_ids:
                # Recalculate the score value
                line._compute_score_value()
                # Add UPDATE command (1, id, {values})
                line_commands.append((1, line.id, {'score_value': line.score_value}))

            if line_commands:
                result['value'] = {
                    'score_line_ids': line_commands
                }
        return result

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
                elif rec.score_name == "AOV":
                    labour_records = self.env['labour.billing'].search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date)
                    ])
                    customer_records = self.env['fleet.repair.feedback'].search([
                        ('feedback_date', '>=', start_date),
                        ('feedback_date', '<=', end_date),
                        ('customer_id', '!=', False)
                    ])
                    total_labour_charges = sum(labour_records.mapped('charge_amount'))
                    total_customers = len(set(customer_records.mapped('customer_id.id')))
                    rec.context_total_score = total_labour_charges / total_customers if total_customers > 0 else 0.0

            elif rec.pillar_id.name == "Sales and Marketing":
                if rec.score_name == "Leads":
                    records = self.env['crm.lead'].search([
                        ('lead_date', '>=', start_date),
                        ('lead_date', '<=', end_date),
                        ('stage_id.sequence', 'in', [0, 1]),
                        ('company_id', '=', rec.company_id.id)
                    ])
                    rec.context_total_score = len(records)


                elif rec.score_name == "Conversion":
                    records = self.env['crm.lead'].search([
                        ('lead_date', '>=', start_date),
                        ('lead_date', '<=', end_date),
                        ('stage_id.sequence', 'in', [2]),
                        ('company_id', '=', rec.company_id.id)
                    ])
                    rec.context_total_score = len(records)


                elif rec.score_name == "Customer Retention":
                    records = self.env['fleet.repair.feedback'].search([
                        ('feedback_date', '>=', start_date),
                        ('feedback_date', '<=', end_date),
                        ('customer_id', '!=', False)
                    ])
                    # rec.context_total_score = len(records)
                    rec.context_total_score = len(set(records.mapped('customer_id.id')))

                # elif rec.score_name == "RCR":
                #     records = self.env['fleet.repair.feedback'].search([
                #         ('feedback_date', '>=', start_date),
                #         ('feedback_date', '<=', end_date)
                #     ])
                #     # calculate the average rating
                #     list_of_records = records.mapped('average_rating')
                #     average_total_rating = sum(list_of_records) / len(list_of_records) if len(list_of_records) else 0
                #     average_total_rating_percentage = average_total_rating / 5
                #     # For percentage type scores, multiply by 100 to convert from decimal (0-1) to percentage (0-100)
                #     if rec.type == 'percentage':
                #         rec.context_total_score = average_total_rating_percentage * 100
                #     else:
                #         rec.context_total_score = average_total_rating_percentage


            elif rec.pillar_id.name == "Finance":
                if rec.score_name == "Income":
                    records = self.env['account.move.line'].search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date),
                        ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
                        ('move_id.state', 'in', ['posted']),
                        ('company_id', '=', rec.company_id.id),
                        ('account_id.account_type', 'in', ['income', 'income_direct_cost']),
                        ('move_id.fleet_repair_invoice_id', '!=', False)
                    ])
                    rec.context_total_score = -sum(records.mapped('balance'))
                elif rec.score_name == "Expense":
                    records = self.env['account.move.line'].search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date),
                        ('move_id.move_type', 'in', ['in_invoice', 'in_refund']),
                        ('move_id.state', 'in', ['draft', 'posted']),
                        ('company_id', '=', rec.company_id.id),
                        ('account_id.account_type', 'in', ['expense', 'expense_depreciation', 'expense_direct_cost'])
                    ])
                    rec.context_total_score = sum(records.mapped('balance'))



                elif rec.score_name == "Cashflow":
                    def _categorize_cash_flow(line):
                        """Categorize account move line into operating/financing/investing"""
                        account_type = line.account_id.account_type
                        balance = line.balance
                        move = line.move_id

                        # Get invoice/document information for debugging
                        move_name = move.name or 'N/A'
                        move_type = move.move_type or 'N/A'
                        partner_name = move.partner_id.name if move.partner_id else 'N/A'
                        account_name = line.account_id.name or 'N/A'
                        account_code = line.account_id.code or 'N/A'

                        # TAX LINES: Include tax in cash flow (part of actual payment/receipt)
                        # MUST CHECK THIS FIRST before the name-based filter below
                        # Tax is part of the total amount paid/received
                        if line.display_type == 'tax' or line.tax_line_id:
                            if move_type == 'in_invoice':
                                # Vendor bill: Tax is part of cash outflow (you pay tax with the bill)
                                tax_amount = abs(balance) if balance < 0 else balance
                                print(
                                    f"📊 OPERATING OUTFLOW (Tax) - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{tax_amount:,.2f}")
                                return ('operating', 'out', tax_amount)
                            elif move_type == 'out_invoice':
                                # Customer invoice: Tax is part of cash inflow (you receive tax with payment)
                                tax_amount = abs(balance)
                                print(
                                    f"📊 OPERATING INFLOW (Tax) - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{tax_amount:,.2f}")
                                return ('operating', 'in', tax_amount)
                            # For other move types, skip tax (not part of operating cash flow)
                            return None

                        # Skip tax accounts (GST/VAT) - but only if NOT a tax line (already handled above)
                        # This catches any remaining tax-related accounts that aren't actual tax lines
                        if 'GST' in account_name or 'TAX' in account_name or 'SGST' in account_name or 'CGST' in account_name or 'IGST' in account_name:
                            return None

                        # Skip bank/payment accounts (they're just transfers, not cash flow)
                        if account_type in ['asset_cash', 'liability_credit_card']:
                            return None

                        # Skip current assets that are not receivables (like Outstanding Payments)
                        if account_type == 'asset_current' and account_type != 'asset_receivable':
                            if 'outstanding' in account_name.lower() or 'payment' in account_name.lower() or 'bank' in account_name.lower():
                                return None

                        # Operating Activities
                        if account_type in ['income', 'income_direct_cost']:
                            print(
                                f"📊 OPERATING INFLOW - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{abs(balance):,.2f}")
                            return ('operating', 'in', abs(balance))
                        elif account_type in ['expense', 'expense_depreciation', 'expense_direct_cost']:
                            print(
                                f"📊 OPERATING OUTFLOW - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{balance:,.2f}")
                            return ('operating', 'out', balance)
                        elif account_type == 'asset_receivable' and balance > 0:
                            # CRITICAL FIX: Skip receivable lines from customer invoices
                            # These are accrual entries, not actual cash received
                            if move_type == 'out_invoice':
                                return None  # Don't count - no cash received yet
                            print(
                                f"📊 OPERATING INFLOW (Advance) - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{balance:,.2f}")
                            return ('operating', 'in', balance)
                        elif account_type == 'liability_payable' and balance < 0:
                            # CRITICAL FIX: Skip payable lines from vendor bills
                            # These are accrual entries, not actual cash paid
                            if move_type == 'in_invoice':
                                return None  # Don't count - no cash paid yet
                            # Only count negative payables from actual payments (not bills)
                            print(
                                f"📊 OPERATING OUTFLOW (Advance) - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{abs(balance):,.2f}")
                            return ('operating', 'out', abs(balance))

                        # Investing Activities
                        elif account_type == 'asset_fixed':
                            direction = 'out' if balance < 0 else 'in'
                            direction_label = 'OUTFLOW' if balance < 0 else 'INFLOW'
                            print(
                                f"💼 INVESTING {direction_label} - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{abs(balance):,.2f}")
                            return ('investing', direction, abs(balance))
                        elif account_type == 'asset_non_current':
                            direction = 'out' if balance < 0 else 'in'
                            direction_label = 'OUTFLOW' if balance < 0 else 'INFLOW'
                            print(
                                f"💼 INVESTING {direction_label} - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{abs(balance):,.2f}")
                            return ('investing', direction, abs(balance))

                        # Financing Activities
                        elif account_type in ['equity', 'equity_unaffected']:
                            direction = 'in' if balance > 0 else 'out'
                            direction_label = 'INFLOW' if balance > 0 else 'OUTFLOW'
                            print(
                                f"💰 FINANCING {direction_label} - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{abs(balance):,.2f}")
                            return ('financing', direction, abs(balance))
                        elif account_type == 'liability_non_current':
                            direction = 'in' if balance > 0 else 'out'
                            direction_label = 'INFLOW' if balance > 0 else 'OUTFLOW'
                            print(
                                f"💰 FINANCING {direction_label} - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{abs(balance):,.2f}")
                            return ('financing', direction, abs(balance))

                        return None

                    # Get all records
                    print(f"\n{'=' * 80}")
                    print(f"🔍 CASH FLOW CALCULATION - {rec.company_id.name}")
                    print(f"📅 Period: {start_date} to {end_date}")
                    print(f"{'=' * 80}\n")

                    records = self.env['account.move.line'].search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date),
                        ('move_id.state', '=', 'posted'),
                        ('company_id', '=', rec.company_id.id),
                    ])

                    print(f"📋 Total Transactions Found: {len(records)}\n")

                    # Categorize
                    operating_in = operating_out = 0.0
                    financing_in = financing_out = 0.0
                    investing_in = investing_out = 0.0

                    categorized_count = 0
                    uncategorized_count = 0

                    for line in records:
                        result = _categorize_cash_flow(line)
                        if result:
                            categorized_count += 1
                            category, direction, amount = result
                            if category == 'operating':
                                if direction == 'in':
                                    operating_in += amount
                                else:
                                    operating_out += amount
                            elif category == 'financing':
                                if direction == 'in':
                                    financing_in += amount
                                else:
                                    financing_out += amount
                            elif category == 'investing':
                                if direction == 'in':
                                    investing_in += amount
                                else:
                                    investing_out += amount
                        else:
                            uncategorized_count += 1
                            move = line.move_id
                            print(
                                f"⚠️  UNCATEGORIZED - Invoice: {move.name or 'N/A'} | Type: {move.move_type or 'N/A'} | Account: {line.account_id.code or 'N/A'} {line.account_id.name or 'N/A'} | Type: {line.account_id.account_type} | Balance: ₹{line.balance:,.2f}")

                    # Calculate net cash flows
                    net_operating = operating_in - operating_out
                    net_financing = financing_in - financing_out
                    net_investing = investing_in - investing_out

                    # Print summary
                    print(f"\n{'=' * 80}")
                    print(f"📊 CASH FLOW SUMMARY")
                    print(f"{'=' * 80}")
                    print(f"✅ Categorized Transactions: {categorized_count}")
                    print(f"⚠️  Un categorized Transactions: {uncategorized_count}")
                    print(f"\n{'─' * 80}")
                    print(f"OPERATING ACTIVITIES:")
                    print(f"  💰 Cash Inflow:  ₹{operating_in:,.2f}")
                    print(f"  💸 Cash Outflow: ₹{operating_out:,.2f}")
                    print(f"  📈 Net Operating: ₹{net_operating:,.2f}")
                    print(f"\n{'─' * 80}")
                    print(f"INVESTING ACTIVITIES:")
                    print(f"  💰 Cash Inflow:  ₹{investing_in:,.2f}")
                    print(f"  💸 Cash Outflow: ₹{investing_out:,.2f}")
                    print(f"  📈 Net Investing: ₹{net_investing:,.2f}")
                    print(f"\n{'─' * 80}")
                    print(f"FINANCING ACTIVITIES:")
                    print(f"  💰 Cash Inflow:  ₹{financing_in:,.2f}")
                    print(f"  💸 Cash Outflow: ₹{financing_out:,.2f}")
                    print(f"  📈 Net Financing: ₹{net_financing:,.2f}")
                    print(f"\n{'─' * 80}")
                    print(f"TOTAL NET CASH FLOW: ₹{net_operating + net_financing + net_investing:,.2f}")
                    print(f"{'=' * 80}\n")

                    # Total cash flow
                    rec.context_total_score = net_operating

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

    @api.model
    def get_score_dashboard_data(self, score_id, filter_type='MTD', start_date=None, end_date=None):
        """
        Get score dashboard data with historical overview in the specified format.
        
        :param score_id: ID of the score record
        :param filter_type: Filter type (MTD, WTD, or YTD)
        :param start_date: Optional start date (YYYY-MM-DD)
        :param end_date: Optional end date (YYYY-MM-DD)
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
        overview = self._get_score_overview(score, filter_type, start_date, end_date)

        return {
            'statusCode': 200,
            'message': 'Score Overview',
            'score_id': score_id,
            'score_name': score.score_name,
            'score_type': score.type or 'value',
            'overview': overview
        }

    # score dashboard overview
    def _get_score_overview(self, score, filter_type='MTD', start_date=None, end_date=None):
        """
        Get historical score overview data based on filter type.
        
        :param score: Score record
        :param filter_type: MTD, WTD, or YTD
        :param start_date: Optional start date
        :param end_date: Optional end date
        :return: List of dictionaries with period data
        """
        from datetime import datetime, timedelta
        from dateutil.relativedelta import relativedelta
        import calendar

        filter_type = (filter_type or 'MTD').upper()
        allowed_filters = ('MTD', 'WTD', 'YTD', 'CUSTOM')
        if filter_type not in allowed_filters:
            filter_type = 'MTD'

        def _to_date(value):
            if isinstance(value, date):
                return value
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, str):
                return datetime.strptime(value, '%Y-%m-%d').date()
            return None

        def _default_range(f_type):
            today = fields.Date.today()
            if f_type == 'WTD':
                day_of_week = today.weekday()
                start_dt = today - timedelta(days=day_of_week)
                return start_dt, today
            if f_type == 'YTD':
                start_dt = today.replace(month=1, day=1)
                return start_dt, today
            # default MTD
            start_dt = today.replace(day=1)
            return start_dt, today

        start_date = _to_date(start_date)
        end_date = _to_date(end_date)

        if filter_type == 'CUSTOM' and (not start_date or not end_date):
            # Can't honour custom without explicit range; fallback gracefully
            filter_type = 'MTD'

        default_start, default_end = _default_range(filter_type if filter_type != 'CUSTOM' else 'MTD')
        base_start = start_date or default_start
        base_end = end_date or default_end

        if base_start > base_end:
            base_start, base_end = base_end, base_start

        overview = []

        # Helper: detect if this is the Labour score where we want max/min values
        is_labour_score = bool(score.score_name and score.score_name == "Labour")

        # Helper: detect if this is the Leads score where we want conversion values
        is_leads_score = bool(score.score_name and 'lead' in score.score_name.lower())

        def _get_labour_max_min_values(score, period_start, period_end, filter_type):
            """Calculate max and min values for Labour score based on period and filter type."""
            if not is_labour_score:
                return None, None

            min_value = 0
            max_value = 0

            if filter_type == 'MTD':
                # For MTD: calculate per day, then multiply by days elapsed in month
                days_in_month = calendar.monthrange(period_start.year, period_start.month)[1]
                month_end_day = period_end.day

                if score.type == "percentage":
                    min_value = (score.min_score_percentage or 0) / days_in_month
                    max_value = (score.max_score_percentage or 0) / days_in_month
                elif score.type == "value":
                    min_value = (score.min_score_number or 0) / days_in_month
                    max_value = (score.max_score_number or 0) / days_in_month

                min_value = round(min_value * month_end_day, 2)
                max_value = round(max_value * month_end_day, 2)

            elif filter_type == 'WTD':
                # For WTD: calculate per day, then multiply by days elapsed in week
                # Use current month's days_in_month (matching API logic)
                today = fields.Date.today()
                days_in_month = calendar.monthrange(today.year, today.month)[1]
                # Use today.weekday() + 1 to match API logic (0=Monday, so +1 gives days from Monday to today)
                days_elapsed = today.weekday() + 1

                if score.type == "percentage":
                    min_value = (score.min_score_percentage or 0) / days_in_month
                    max_value = (score.max_score_percentage or 0) / days_in_month
                elif score.type == "value":
                    min_value = (score.min_score_number or 0) / days_in_month
                    max_value = (score.max_score_number or 0) / days_in_month

                min_value = round(min_value * days_elapsed, 2)
                max_value = round(max_value * days_elapsed, 2)

            elif filter_type == 'YTD':
                # For YTD: calculate per month (30 days), then multiply by days multiplier
                total_days_elapsed = sum(
                    calendar.monthrange(period_end.year, m)[1] for m in range(1, period_end.month)
                ) + period_end.day

                days_multiplier = total_days_elapsed / 30.0

                if score.type == "percentage":
                    monthly_min_base = score.min_score_percentage or 0
                    monthly_max_base = score.max_score_percentage or 0
                elif score.type == "value":
                    monthly_min_base = score.min_score_number or 0
                    monthly_max_base = score.max_score_number or 0
                else:
                    monthly_min_base = 0
                    monthly_max_base = 0

                min_value = round(monthly_min_base * days_multiplier, 2)
                max_value = round(monthly_max_base * days_multiplier, 2)

            elif filter_type == 'CUSTOM':
                # For CUSTOM: calculate per day, then multiply by days in range
                days_in_range = (period_end - period_start).days + 1
                days_in_month = calendar.monthrange(period_start.year, period_start.month)[1]

                if score.type == "percentage":
                    min_value = (score.min_score_percentage or 0) / days_in_month
                    max_value = (score.max_score_percentage or 0) / days_in_month
                elif score.type == "value":
                    min_value = (score.min_score_number or 0) / days_in_month
                    max_value = (score.max_score_number or 0) / days_in_month

                min_value = round(min_value * days_in_range, 2)
                max_value = round(max_value * days_in_range, 2)

            return min_value, max_value

        def _get_conversion_count(start_dt, end_dt):
            """Return conversion count for Leads score between two dates.

            This mirrors the logic used in the public quadrant API, so both
            internal and public dashboards show the same conversion values.
            """
            if not is_leads_score or not start_dt or not end_dt:
                return None

            Lead = self.env['crm.lead']
            domain = [
                ('create_date', '>=', datetime.combine(start_dt, datetime.min.time())),
                ('create_date', '<=', datetime.combine(end_dt, datetime.max.time())),
                ('stage_id', '=', 2),
            ]
            if score.company_id:
                domain.append(('company_id', '=', score.company_id.id))

            return Lead.search_count(domain)

        if filter_type == 'WTD':
            current_end = base_end
            current_start = base_start or (current_end - timedelta(days=current_end.weekday()))
            for i in range(2, -1, -1):
                # Calculate week end: current_end minus i weeks
                week_end = current_end - timedelta(days=i * 7)
                # Calculate week start: Monday of that week
                # weekday() returns 0=Monday, 1=Tuesday, ..., 6=Sunday
                # So we subtract weekday() days to get to Monday
                week_start = week_end - timedelta(days=week_end.weekday())
                if i == 0:
                    # For current week, use the actual current_start (which is Monday of current week)
                    week_start = current_start
                if week_start > week_end:
                    week_start = week_end
                actual_value = self._calculate_score_for_period(score, week_start, week_end)
                entry = {
                    'period': f'Week {3 - i}',
                    'start_date': week_start.strftime('%d-%m-%Y'),
                    'end_date': week_end.strftime('%d-%m-%Y'),
                    'actual_value': round(actual_value, 1) if actual_value else 0,
                }
                # Add max/min values for Labour score
                min_value, max_value = _get_labour_max_min_values(score, week_start, week_end, 'WTD')
                if min_value is not None and max_value is not None:
                    entry['min_value'] = min_value
                    entry['max_value'] = max_value
                # Add conversion value only for Leads score
                conversion_count = _get_conversion_count(week_start, week_end)
                if conversion_count is not None:
                    entry['conversion_value'] = conversion_count or 0
                overview.append(entry)

        elif filter_type == 'MTD':
            reference_end = base_end
            reference_day = reference_end.day
            for i in range(2, -1, -1):
                month_ref = reference_end - relativedelta(months=i)
                period_start = month_ref.replace(day=1)
                if i == 0:
                    period_start = base_start or period_start
                    period_end = reference_end
                else:
                    last_day = calendar.monthrange(month_ref.year, month_ref.month)[1]
                    period_end = month_ref.replace(day=min(reference_day, last_day))
                if period_start > period_end:
                    period_start = period_end
                actual_value = self._calculate_score_for_period(score, period_start, period_end)
                entry = {
                    'month': month_ref.strftime('%B %Y'),
                    'start_date': period_start.strftime('%d-%m-%Y'),
                    'end_date': period_end.strftime('%d-%m-%Y'),
                    'actual_value': round(actual_value, 1) if actual_value else 0,
                }
                # Add max/min values for Labour score
                min_value, max_value = _get_labour_max_min_values(score, period_start, period_end, 'MTD')
                if min_value is not None and max_value is not None:
                    entry['min_value'] = min_value
                    entry['max_value'] = max_value
                conversion_count = _get_conversion_count(period_start, period_end)
                if conversion_count is not None:
                    entry['conversion_value'] = conversion_count or 0
                overview.append(entry)

        elif filter_type == 'YTD':
            # YTD: Show current year + 2 previous years
            # Each year shows Jan 1 to the same date in that year
            today = fields.Date.today()
            reference_month = today.month
            reference_day = today.day

            for i in range(2, -1, -1):  # 2 years back, 1 year back, current year
                year_ref = today - relativedelta(years=i)
                period_start = year_ref.replace(month=1, day=1)

                # For current year (i=0), end date is today
                # For previous years, end date is same month/day in that year
                if i == 0:
                    period_end = today
                else:
                    try:
                        period_end = year_ref.replace(month=reference_month, day=reference_day)
                    except ValueError:
                        # Handle edge case (e.g., Feb 29 in non-leap year)
                        last_day = calendar.monthrange(year_ref.year, reference_month)[1]
                        period_end = year_ref.replace(month=reference_month, day=min(reference_day, last_day))

                # Ensure start <= end
                if period_start > period_end:
                    period_end = period_start

                actual_value = self._calculate_score_for_period(score, period_start, period_end)
                entry = {
                    'year': str(year_ref.year),
                    'start_date': period_start.strftime('%d-%m-%Y'),
                    'end_date': period_end.strftime('%d-%m-%Y'),
                    'actual_value': round(actual_value, 1) if actual_value else 0,
                }
                # Add max/min values for Labour score
                min_value, max_value = _get_labour_max_min_values(score, period_start, period_end, 'YTD')
                if min_value is not None and max_value is not None:
                    entry['min_value'] = min_value
                    entry['max_value'] = max_value
                conversion_count = _get_conversion_count(period_start, period_end)
                if conversion_count is not None:
                    entry['conversion_value'] = conversion_count or 0
                overview.append(entry)
        elif filter_type == 'CUSTOM':
            actual_value = self._calculate_score_for_period(score, base_start, base_end)
            entry = {
                'period': 'Custom Range',
                'start_date': base_start.strftime('%d-%m-%Y'),
                'end_date': base_end.strftime('%d-%m-%Y'),
                'actual_value': round(actual_value, 1) if actual_value else 0,
            }
            # Add max/min values for Labour score
            min_value, max_value = _get_labour_max_min_values(score, base_start, base_end, 'CUSTOM')
            if min_value is not None and max_value is not None:
                entry['min_value'] = min_value
                entry['max_value'] = max_value
            conversion_count = _get_conversion_count(base_start, base_end)
            if conversion_count is not None:
                entry['conversion_value'] = conversion_count or 0
            overview.append(entry)

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
        # Note: _compute_context_total_score already multiplies by 100 for percentage scores,
        # so we don't need to multiply again here
        score_ctx = score.with_context(
            force_date_start=start_date,
            force_date_end=end_date
        )
        score_ctx._compute_context_total_score()
        value = score_ctx.context_total_score or 0.0

        return value

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

                elif rec.score_name == "AOV":
                    labour_records = self.env['labour.billing'].search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date)
                    ])
                    customer_records = self.env['fleet.repair.feedback'].search([
                        ('feedback_date', '>=', start_date),
                        ('feedback_date', '<=', end_date),
                        ('customer_id', '!=', False)
                    ])
                    total_labour_charges=sum(labour_records.mapped('charge_amount'))
                    total_customers=len(set(customer_records.mapped('customer_id.id')))
                    rec.total_score_value = total_labour_charges / total_customers if total_customers > 0 else 0.0



            elif rec.pillar_id.name == "Sales and Marketing":
                if rec.score_name == "Leads":
                    records = self.env['crm.lead'].search([
                        ('lead_date', '>=', start_date),
                        ('lead_date', '<=', end_date),
                        ('stage_id.sequence', 'in', [0, 1]),
                        ('company_id', '=', rec.company_id.id)
                    ])
                    rec.total_score_value = len(records)

                elif rec.score_name == "Conversion":
                    records = self.env['crm.lead'].search([
                        ('lead_date', '>=', start_date),
                        ('lead_date', '<=', end_date),
                        ('stage_id.sequence', 'in', [2]),
                        ('company_id', '=', rec.company_id.id)
                    ])
                    rec.total_score_value = len(records)

                elif rec.score_name=="Customer Retention":
                    records=self.env['fleet.repair.feedback'].search([
                        ('feedback_date','>=',start_date),
                        ('feedback_date','<=',end_date),
                        ('customer_id','!=',False)
                    ])
                    rec.total_score_value=len(set(records.mapped('customer_id.id')))





                # elif rec.score_name == "RCR":
                #     print("helloooooo")
                #     records = self.env['fleet.repair.feedback'].search([
                #         ('feedback_date', '>=', start_date),
                #         ('feedback_date', '<=', end_date)
                #     ])
                #     list_of_records = list(records.mapped('average_rating'))
                #     average_total_rating = sum(list_of_records) / len(list_of_records) if len(
                #         list_of_records) > 0 else 0.0
                #     average_total_rating_percentage = average_total_rating / 5
                #     rec.total_score_value = average_total_rating_percentage
                #     rec.total_score_value_percentage = average_total_rating_percentage


            elif rec.pillar_id.name == "Finance":
                l = set()
                if rec.score_name == "Income":
                    records = self.env['account.move.line'].search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date),
                        ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
                        ('move_id.state', 'in', ['posted']),
                        ('company_id', '=', rec.company_id.id),
                        ('account_id.account_type', 'in', ['income', 'income_direct_cost']),
                        # ('move_id.fleet_repair_invoice_id', '!=', False)
                    ])
                    rec.total_score_value = -sum(records.mapped('balance'))
                elif rec.score_name == "Expense":
                    records = self.env['account.move.line'].search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date),
                        ('move_id.move_type', 'in', ['in_invoice', 'in_refund']),
                        ('move_id.state', 'in', ['posted']),
                        #  \\ currently also includes pending expense in draft state and also includes posted  ,
                        ('company_id', '=', rec.company_id.id),
                        ('account_id.account_type', 'in', ['expense', 'expense_depreciation', 'expense_direct_cost'])
                    ])
                    # Use 'balance' instead of 'amount' - balance is positive for expenses, negative for refunds
                    rec.total_score_value = sum(records.mapped('balance'))
                elif rec.score_name == "Cashflow":

                    def _categorize_cash_flow(line):
                        """Categorize account move line into operating/financing/investing"""
                        account_type = line.account_id.account_type
                        balance = line.balance
                        move = line.move_id

                        # Get invoice/document information for debugging
                        move_name = move.name or 'N/A'
                        move_type = move.move_type or 'N/A'
                        partner_name = move.partner_id.name if move.partner_id else 'N/A'
                        account_name = line.account_id.name or 'N/A'
                        account_code = line.account_id.code or 'N/A'

                        # TAX LINES: Include tax in cash flow (part of actual payment/receipt)
                        # MUST CHECK THIS FIRST before the name-based filter below
                        # Tax is part of the total amount paid/received
                        if line.display_type == 'tax' or line.tax_line_id:
                            if move_type == 'in_invoice':
                                # Vendor bill: Tax is part of cash outflow (you pay tax with the bill)
                                tax_amount = abs(balance) if balance < 0 else balance
                                print(
                                    f"📊 OPERATING OUTFLOW (Tax) - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{tax_amount:,.2f}")
                                return ('operating', 'out', tax_amount)
                            elif move_type == 'out_invoice':
                                # Customer invoice: Tax is part of cash inflow (you receive tax with payment)
                                tax_amount = abs(balance)
                                print(
                                    f"📊 OPERATING INFLOW (Tax) - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{tax_amount:,.2f}")
                                return ('operating', 'in', tax_amount)
                            # For other move types, skip tax (not part of operating cash flow)
                            return None

                        # Skip tax accounts (GST/VAT) - but only if NOT a tax line (already handled above)
                        # This catches any remaining tax-related accounts that aren't actual tax lines
                        if 'GST' in account_name or 'TAX' in account_name or 'SGST' in account_name or 'CGST' in account_name or 'IGST' in account_name:
                            return None

                        # Skip bank/payment accounts (they're just transfers, not cash flow)
                        if account_type in ['asset_cash', 'liability_credit_card']:
                            return None

                        # Skip current assets that are not receivables (like Outstanding Payments)
                        if account_type == 'asset_current' and account_type != 'asset_receivable':
                            if 'outstanding' in account_name.lower() or 'payment' in account_name.lower() or 'bank' in account_name.lower():
                                return None

                        # Operating Activities
                        if account_type in ['income', 'income_direct_cost']:
                            print(
                                f"📊 OPERATING INFLOW - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{abs(balance):,.2f}")
                            return ('operating', 'in', abs(balance))
                        elif account_type in ['expense', 'expense_depreciation', 'expense_direct_cost']:
                            print(
                                f"📊 OPERATING OUTFLOW - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{balance:,.2f}")
                            return ('operating', 'out', balance)
                        elif account_type == 'asset_receivable' and balance > 0:
                            # CRITICAL FIX: Skip receivable lines from customer invoices
                            # These are accrual entries, not actual cash received
                            if move_type == 'out_invoice':
                                return None  # Don't count - no cash received yet
                            print(
                                f"📊 OPERATING INFLOW (Advance) - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{balance:,.2f}")
                            return ('operating', 'in', balance)
                        elif account_type == 'liability_payable' and balance < 0:
                            # CRITICAL FIX: Skip payable lines from vendor bills
                            # These are accrual entries, not actual cash paid
                            if move_type == 'in_invoice':
                                return None  # Don't count - no cash paid yet
                            # Only count negative payables from actual payments (not bills)
                            print(
                                f"📊 OPERATING OUTFLOW (Advance) - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{abs(balance):,.2f}")
                            return ('operating', 'out', abs(balance))

                        # Investing Activities
                        elif account_type == 'asset_fixed':
                            direction = 'out' if balance < 0 else 'in'
                            direction_label = 'OUTFLOW' if balance < 0 else 'INFLOW'
                            print(
                                f"💼 INVESTING {direction_label} - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{abs(balance):,.2f}")
                            return ('investing', direction, abs(balance))
                        elif account_type == 'asset_non_current':
                            direction = 'out' if balance < 0 else 'in'
                            direction_label = 'OUTFLOW' if balance < 0 else 'INFLOW'
                            print(
                                f"💼 INVESTING {direction_label} - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{abs(balance):,.2f}")
                            return ('investing', direction, abs(balance))

                        # Financing Activities
                        elif account_type in ['equity', 'equity_unaffected']:
                            direction = 'in' if balance > 0 else 'out'
                            direction_label = 'INFLOW' if balance > 0 else 'OUTFLOW'
                            print(
                                f"💰 FINANCING {direction_label} - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{abs(balance):,.2f}")
                            return ('financing', direction, abs(balance))
                        elif account_type == 'liability_non_current':
                            direction = 'in' if balance > 0 else 'out'
                            direction_label = 'INFLOW' if balance > 0 else 'OUTFLOW'
                            print(
                                f"💰 FINANCING {direction_label} - Invoice: {move_name} | Type: {move_type} | Partner: {partner_name} | Account: {account_code} {account_name} | Amount: ₹{abs(balance):,.2f}")
                            return ('financing', direction, abs(balance))

                        return None

                    # Get all records
                    print(f"\n{'=' * 80}")
                    print(f"🔍 CASH FLOW CALCULATION - {rec.company_id.name}")
                    print(f"📅 Period: {start_date} to {end_date}")
                    print(f"{'=' * 80}\n")

                    records = self.env['account.move.line'].search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date),
                        ('move_id.state', '=', 'posted'),
                        ('company_id', '=', rec.company_id.id),
                    ])

                    print(f"📋 Total Transactions Found: {len(records)}\n")

                    # Categorize
                    operating_in = operating_out = 0.0
                    financing_in = financing_out = 0.0
                    investing_in = investing_out = 0.0

                    categorized_count = 0
                    uncategorized_count = 0

                    for line in records:
                        result = _categorize_cash_flow(line)
                        if result:
                            categorized_count += 1
                            category, direction, amount = result
                            if category == 'operating':
                                if direction == 'in':
                                    operating_in += amount
                                else:
                                    operating_out += amount
                            elif category == 'financing':
                                if direction == 'in':
                                    financing_in += amount
                                else:
                                    financing_out += amount
                            elif category == 'investing':
                                if direction == 'in':
                                    investing_in += amount
                                else:
                                    investing_out += amount
                        else:
                            uncategorized_count += 1
                            move = line.move_id
                            print(
                                f"⚠️  UNCATEGORIZED - Invoice: {move.name or 'N/A'} | Type: {move.move_type or 'N/A'} | Account: {line.account_id.code or 'N/A'} {line.account_id.name or 'N/A'} | Type: {line.account_id.account_type} | Balance: ₹{line.balance:,.2f}")

                    # Calculate net cash flows
                    net_operating = operating_in - operating_out
                    net_financing = financing_in - financing_out
                    net_investing = investing_in - investing_out

                    # Print summary
                    print(f"\n{'=' * 80}")
                    print(f"📊 CASH FLOW SUMMARY")
                    print(f"{'=' * 80}")
                    print(f"✅ Categorized Transactions: {categorized_count}")
                    print(f"⚠️  Un categorized Transactions: {uncategorized_count}")
                    print(f"\n{'─' * 80}")
                    print(f"OPERATING ACTIVITIES:")
                    print(f"  💰 Cash Inflow:  ₹{operating_in:,.2f}")
                    print(f"  💸 Cash Outflow: ₹{operating_out:,.2f}")
                    print(f"  📈 Net Operating: ₹{net_operating:,.2f}")
                    print(f"\n{'─' * 80}")
                    print(f"INVESTING ACTIVITIES:")
                    print(f"  💰 Cash Inflow:  ₹{investing_in:,.2f}")
                    print(f"  💸 Cash Outflow: ₹{investing_out:,.2f}")
                    print(f"  📈 Net Investing: ₹{net_investing:,.2f}")
                    print(f"\n{'─' * 80}")
                    print(f"FINANCING ACTIVITIES:")
                    print(f"  💰 Cash Inflow:  ₹{financing_in:,.2f}")
                    print(f"  💸 Cash Outflow: ₹{financing_out:,.2f}")
                    print(f"  📈 Net Financing: ₹{net_financing:,.2f}")
                    print(f"\n{'─' * 80}")
                    print(f"TOTAL NET CASH FLOW: ₹{net_operating + net_financing + net_investing:,.2f}")
                    print(f"{'=' * 80}\n")

                    # Total cash flow
                    rec.total_score_value = net_operating


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
                elif rec.score_id.score_name == "RCR":
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
                    # print("job_card_num", len(job_card_num))

                    total_hours = 0.0
                    for record in delivered_rec:
                        # Assuming time_diff is in hours with decimal minutes (e.g., 1.5 hours = 1 hour 30 minutes)
                        hours = record.time_diff  # Get whole hours
                        # Get minutes from decimal part
                        total_hours += hours  # Convert everything to hours

                    total_days = total_hours / 24.0  # Convert total hours to days
                    print("total_hours", total_hours, "total_days", total_days, 'length', len(list(set(delivered_rec))))
                    rec.score_value = total_days / len(job_card_num) if len(job_card_num) > 0 else 0.0

            elif rec.score_id.pillar_id.name == "Sales and Marketing":
                pass

            elif rec.score_id.pillar_id.name == "Finance":
                if rec.score_id.score_name == "Income":
                    domain = [
                        ('department_id', '=', rec.department_id.id),
                        ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),  # Customer invoices and refunds
                        ('move_id.state', 'in', ['posted']),  # Only posted invoices
                        ('company_id', '=', rec.score_id.company_id.id),
                        ('account_id.account_type', 'in', ['income', 'income_direct_cost'])
                    ]
                    if rec.score_id.start_date:
                        domain.append(('date', '>=', rec.score_id.start_date))
                    if rec.score_id.end_date:
                        domain.append(('date', '<=', rec.score_id.end_date))
                    records = self.env['account.move.line'].search(domain)
                    rec.score_value = -sum(records.mapped('balance'))
                elif rec.score_id.score_name == "Expense":
                    domain = [
                        ('department_id', '=', rec.department_id.id),
                        ('move_id.move_type', 'in', ['in_invoice', 'in_refund']),  # Vendor bills and refunds
                        ('move_id.state', 'in', ['posted']),  # Include both draft and posted
                        ('company_id', '=', rec.score_id.company_id.id),
                        ('account_id.account_type', 'in', ['expense', 'expense_depreciation', 'expense_direct_cost'])
                    ]
                    if rec.score_id.start_date:
                        domain.append(('date', '>=', rec.score_id.start_date))
                    if rec.score_id.end_date:
                        domain.append(('date', '<=', rec.score_id.end_date))

                    records = self.env['account.move.line'].search(domain)

                    # print(f"Department: {rec.department_id.name}")
                    # print(f"Found {len(records)} records")
                    # print(f"Records with department_id: {len(records.filtered('department_id'))}")
                    # print(f"Records without department_id: {len(records.filtered(lambda r: not r.department_id))}")

                    # Debug: Check if records are found and if department_id is populated

                    rec.score_value = sum(records.mapped('balance'))
                elif rec.score_id.score_name == "Cashflow":
                    pass
