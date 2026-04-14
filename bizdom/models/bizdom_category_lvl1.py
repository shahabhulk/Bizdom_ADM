from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BizdomCategoryLvl1(models.Model):
    _name = 'bizdom.category_lvl1'
    _description = 'Bizdom Category Lvl1'
    _order = 'score_id, id'
    _rec_name = 'name'

    # Computed name field for display
    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
        readonly=True
    )

    type = fields.Selection([
        ('percentage', 'Percentage'),
        ('value', 'Value')
    ])
    max_category_percentage_lvl1 = fields.Float(string="Max Score")
    min_category_percentage_lvl1 = fields.Float(string="Min Score")
    max_category_value_lvl1 = fields.Float(string="Max Score")
    min_category_value_lvl1 = fields.Float(string="Min Score")
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    score_category_lvl1 = fields.Float(string="Category Score", compute='_compute_score_category_lvl1', store=False)

    # Add a context-based computed field similar to context_total_score
    context_score_category_lvl1 = fields.Float(
        string="Context Category Score",
        compute='_compute_context_score_category_lvl1',
        store=False
    )

    score_id = fields.Many2one('bizdom.score', string='Score')
    category_lvl1_id = fields.Many2one('bizdom.category_lvl1', string='Category Lvl1')
    category_lvl1_selection = fields.Reference([
        ('hr.department', 'Department'),
        ('utm.medium', 'Medium')
    ], string='Category Lvl1 ')

    category_type = fields.Char(compute='_compute_category_type', store=False)

    # One2many relationship to Category Level 2
    category_lvl2_ids = fields.One2many(
        'bizdom.category_lvl2',
        'category_lvl1_id',
        string='Category Lvl2'
    )

    @api.depends('score_id', 'score_id.score_name')
    def _compute_name(self):
        """Compute name in format: {score_name}/Q2001, Q2002, Q2003, etc."""
        for rec in self:
            if not rec.score_id or not rec.score_id.score_name:
                rec.name = False
                continue

            score_name = rec.score_id.score_name

            # If record has an ID, find its position among existing records
            if rec.id:
                # Get all records for the same score_id, ordered by id
                same_score_records = self.search([
                    ('score_id', '=', rec.score_id.id)
                ], order='id')

                # Find the sequence number (position in the list)
                sequence_number = 1
                for idx, record in enumerate(same_score_records, start=1):
                    if record.id == rec.id:
                        sequence_number = idx
                        break
            else:
                # For new records without ID, count existing records + 1
                existing_count = self.search_count([
                    ('score_id', '=', rec.score_id.id)
                ])
                sequence_number = existing_count + 1

            # Format: {score_name}/Q2{zero-padded sequence number} -> Q2001, Q2002, Q2003
            rec.name = f"{score_name}/Q2{sequence_number:03d}"

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure proper sequence numbering"""
        records = super().create(vals_list)
        # Trigger recomputation of names for all created records
        records._compute_name()
        return records

    def write(self, vals):
        """Override write to recompute names if score_id changes"""
        result = super().write(vals)
        if 'score_id' in vals:
            # Recompute names for all records with the same score_id
            for rec in self:
                if rec.score_id:
                    same_score_records = self.search([
                        ('score_id', '=', rec.score_id.id)
                    ], order='id')
                    same_score_records._compute_name()
        return result

    @api.depends('category_lvl1_selection')
    def _compute_category_type(self):
        for rec in self:
            if rec.category_lvl1_selection:
                model_name = rec.category_lvl1_selection._name
                # Map model names to display names
                if model_name == 'hr.department':
                    rec.category_type = 'Department'
                elif model_name == 'utm.medium':
                    rec.category_type = 'Medium'
                else:
                    rec.category_type = model_name
            else:
                rec.category_type = ''

    @api.constrains('category_lvl1_selection', 'score_id')
    def _check_duplicate_category_lvl1(self):
        """Prevent duplicate records with the same category_lvl1_selection and score_id"""
        for rec in self:
            if rec.category_lvl1_selection and rec.score_id:
                # Reference fields are stored as strings "model_name,id" in database
                # We need to compare the string representation
                ref_value = "%s,%s" % (rec.category_lvl1_selection._name, rec.category_lvl1_selection.id)
                existing_record = self.search([
                    ('category_lvl1_selection', '=', ref_value),
                    ('score_id', '=', rec.score_id.id),
                    ('id', '!=', rec.id)
                ])
                if existing_record:
                    raise ValidationError("The record already exists for this category and score.")

    # frontend app
    @api.depends('category_lvl1_selection', 'score_id')
    def _compute_context_score_category_lvl1(self):
        """Compute score based on context dates (like context_total_score pattern)"""
        for rec in self:
            rec.context_score_category_lvl1 = 0.0

            # Get dates from context or use record's dates
            start_date = self._context.get('force_date_start', rec.start_date)
            end_date = self._context.get('force_date_end', rec.end_date)

            if not rec.category_lvl1_selection or not rec.score_id or not start_date or not end_date:
                continue

            # Handle Labour score with departments
            if rec.score_id.score_name == "Labour":
                if rec.category_lvl1_selection._name != 'hr.department':
                    continue

                department = rec.category_lvl1_selection

                # Calculate Labour score using context dates
                domain = [
                    ('department_id', '=', department.id),
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('invoice_id.payment_state', '=', 'paid')
                ]
                records = self.env["labour.billing"].search(domain)
                rec.context_score_category_lvl1 = sum(records.mapped('charge_amount'))

            # Handle Leads score with utm.medium (sources)
            if rec.score_id.score_name == "Leads":
                if rec.category_lvl1_selection._name != 'utm.medium':
                    continue

                medium = rec.category_lvl1_selection
                # Get company from context or score
                company_id = self._context.get('company_id', rec.score_id.company_id.id)

                # Search for leads matching the medium and date range
                domain = [
                    ('lead_date', '>=', start_date),
                    ('lead_date', '<=', end_date),
                    ('stage_id.sequence', 'in', [0, 1]),
                    ('medium_id', '=', medium.id),
                    ('company_id', '=', company_id)
                ]
                records = self.env['crm.lead'].search(domain)
                rec.context_score_category_lvl1 = len(records)

            # Handle Conversion score with utm.medium (sources)
            if rec.score_id.score_name == "Conversion":
                if rec.category_lvl1_selection._name != 'utm.medium':
                    continue

                medium = rec.category_lvl1_selection
                # Get company from context or score
                company_id = self._context.get('company_id', rec.score_id.company_id.id)

                # Search for conversions (stage_id.sequence = 2) matching the medium and date range
                domain = [
                    ('lead_date', '>=', start_date),
                    ('lead_date', '<=', end_date),
                    ('stage_id.sequence', '=', 2),
                    ('medium_id', '=', medium.id),
                    ('company_id', '=', company_id)
                ]
                records = self.env['crm.lead'].search(domain)
                rec.context_score_category_lvl1 = len(records)

            if rec.score_id.score_name == "AOV":
                department = rec.category_lvl1_selection
                if department._name != 'hr.department':
                    continue
                dept_domain = [
                    ('department_id', '=', department.id),
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('invoice_id.payment_state', '=', 'paid')
                ]
                car_records = self.env['department.charges'].search([
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('invoice_id.payment_state', '=', 'paid')
                ])
                total_cars = len(set(car_records.mapped('car_number')))
                dept_record_charges = self.env["department.charges"].search(dept_domain)
                total_dept_sum = sum(dept_record_charges.mapped('charge_amount'))
                rec.context_score_category_lvl1 = total_dept_sum / total_cars if total_cars > 0 else 0.0

            if rec.score_id.score_name == "Customer Retention":
                department = rec.category_lvl1_selection
                # Check if category_lvl1_selection is a department
                if not department or department._name != 'hr.department':
                    rec.context_score_category_lvl1 = 0
                    return

                # Get all feedback records in the date range (use context dates)
                records = self.env['fleet.repair.feedback'].search([
                    ('feedback_date', '>=', start_date),
                    ('feedback_date', '<=', end_date),
                    ('customer_id', '!=', False)
                ])

                # Get unique customer IDs from the period
                customer_ids_in_period = records.mapped('customer_id.id')
                unique_customer_ids = list(set([cid for cid in customer_ids_in_period if cid]))
                if not unique_customer_ids:
                    rec.context_score_category_lvl1 = 0
                else:
                    # Get ALL feedbacks for these customers (both in current period AND before)
                    all_feedbacks = self.env['fleet.repair.feedback'].search([
                        ('customer_id', 'in', unique_customer_ids),
                        ('feedback_date', '<=', end_date),  # Includes both current period and before (use context date)
                        ('feedback_date', '!=', False),
                        ('customer_id', '!=', False)
                    ])

                    # Count ALL feedbacks per customer (including current period and before)

                    total_feedback_count = {}
                    for feedback in all_feedbacks:
                        customer_id = feedback.customer_id.id
                        total_feedback_count[customer_id] = total_feedback_count.get(customer_id, 0) + 1

                    # Categorize based on TOTAL feedback count (current + previous)

                    # new customer = 1, repeated customer = 2, client = 3, advocate = 4+

                    new_customers = [cid for cid in unique_customer_ids if total_feedback_count.get(cid, 0) == 1]
                    repeated_customers = [cid for cid in unique_customer_ids if total_feedback_count.get(cid, 0) == 2]
                    clients = [cid for cid in unique_customer_ids if total_feedback_count.get(cid, 0) == 3]
                    advocates = [cid for cid in unique_customer_ids if total_feedback_count.get(cid, 0) >= 4]

                    # print("Department name:", department.name)
                    # print("Total feedback count (current + previous):", total_feedback_count)
                    # print("New customers (1 feedback):", len(new_customers))
                    # print("Repeated customers (2 feedbacks):", len(repeated_customers))
                    # print("Clients (3 feedbacks):", len(clients))
                    # print("Advocates (4+ feedbacks):", len(advocates))

                    # Return count based on department name
                    if department.name == "New Customers":
                        rec.context_score_category_lvl1 = len(new_customers)
                    elif department.name == "Repeated Customers":
                        rec.context_score_category_lvl1 = len(repeated_customers)
                    elif department.name == "Client":
                        rec.context_score_category_lvl1 = len(clients)
                    elif department.name == "Advocate":
                        rec.context_score_category_lvl1 = len(advocates)
                    else:
                        rec.context_score_category_lvl1 = 0

            if rec.score_id.score_name == "Income":
                department = rec.category_lvl1_selection
                if department._name != 'hr.department':
                    continue
                domain = [
                    ('department_id', '=', department.id),
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),  # Customer invoices and refunds
                    # Only posted invoices
                    ('move_id.payment_state', '=', 'paid'),  # Only paid invoices
                    ('company_id', '=', rec.score_id.company_id.id),
                    ('account_id.account_type', 'in', ['income', 'income_direct_cost'])
                ]
                records = self.env['account.move.line'].search(domain)
                rec.context_score_category_lvl1 = -sum(records.mapped('balance'))

            if rec.score_id.score_name == "Expense":
                department = rec.category_lvl1_selection
                if department._name != 'hr.department':
                    continue

                expense_bills = [
                    ('department_id', '=', department.id),
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('company_id', '=', rec.score_id.company_id.id),
                    ('account_id.account_type', 'in', ['expense', 'expense_direct_cost', 'expense_depreciation']),
                    '|',
                    '&', ('move_id.move_type', '=', 'in_invoice'), ('move_id.payment_state', '=', 'paid'),
                    '&', ('move_id.move_type', '=', 'entry'), ('move_id.state', '=', 'posted'),
                ]
                records = self.env['account.move.line'].search(expense_bills)

                rec.context_score_category_lvl1 = sum(records.mapped('debit'))

                for i in records:
                    print(i.name)
                    print(i.debit)

            if rec.score_id.score_name == "Cashflow":
                department = rec.category_lvl1_selection
                if department._name != 'hr.department':
                    continue

                # Search ALL posted journal entries for this department in the date range
                records = self.env['account.move.line'].search([
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('move_id.state', '=', 'posted'),
                    ('company_id', '=', rec.score_id.company_id.id),
                    ('department_id', '=', department.id),
                ])

                operating_in = 0.0
                operating_out = 0.0

                for line in records:
                    account_type = line.account_id.account_type
                    balance = line.balance
                    move = line.move_id
                    move_type = move.move_type or 'N/A'
                    account_name = line.account_id.name or 'N/A'

                    # TAX LINES: Include tax in cash flow (part of actual payment/receipt)
                    if line.display_type == 'tax' or line.tax_line_id:
                        if move_type == 'in_invoice':
                            # Vendor bill: Tax is part of cash outflow
                            tax_amount = abs(balance) if balance < 0 else balance
                            operating_out += tax_amount
                            continue
                        elif move_type == 'out_invoice':
                            # Customer invoice: Tax is part of cash inflow
                            tax_amount = abs(balance)
                            operating_in += tax_amount
                            continue
                        else:
                            continue

                    # Skip tax accounts (GST/VAT) - but only if NOT a tax line (already handled above)
                    if any(kw in account_name for kw in ['GST', 'TAX', 'SGST', 'CGST', 'IGST']):
                        continue

                    # Skip bank/payment accounts (they're just transfers, not cash flow)
                    if account_type in ['asset_cash', 'liability_credit_card']:
                        continue

                    # Skip current assets that are not receivables
                    if account_type == 'asset_current' and account_type != 'asset_receivable':
                        if any(kw in account_name.lower() for kw in ['outstanding', 'payment', 'bank']):
                            continue

                    # Operating Activities - Inflow
                    if account_type in ['income', 'income_direct_cost']:
                        operating_in += abs(balance)
                    # Operating Activities - Outflow
                    elif account_type in ['expense', 'expense_depreciation', 'expense_direct_cost']:
                        operating_out += balance
                    # Receivable (advance payments, but skip accrual entries from invoices)
                    elif account_type == 'asset_receivable' and balance > 0:
                        if move_type == 'out_invoice':
                            continue  # Skip accrual entries - no cash received yet
                        operating_in += balance
                    # Payable (advance payments, but skip accrual entries from bills)
                    elif account_type == 'liability_payable' and balance < 0:
                        if move_type == 'in_invoice':
                            continue  # Skip accrual entries - no cash paid yet
                        operating_out += abs(balance)
                    # Skip investing/financing - only "Operating" at this level

                rec.context_score_category_lvl1 = operating_in - operating_out

    # Backend app
    @api.depends('category_lvl1_selection', 'score_id', 'start_date', 'end_date')
    def _compute_score_category_lvl1(self):
        """Compute Labour score based on department and date range"""
        for rec in self:
            rec.score_category_lvl1 = 0.0

            # Add validation check at the beginning
            if not rec.category_lvl1_selection or not rec.score_id or not rec.start_date or not rec.end_date:
                continue

            if rec.score_id.score_name == "Labour":
                department = rec.category_lvl1_selection
                # Additional check for department type
                if department._name != 'hr.department':
                    continue
                domain = [
                    ('department_id', '=', department.id),
                    ('date', '>=', rec.start_date),
                    ('date', '<=', rec.end_date),
                    ('invoice_id.payment_state', '=', 'paid')
                ]
                records = self.env["labour.billing"].search(domain)
                rec.score_category_lvl1 = sum(records.mapped('charge_amount'))

            if rec.score_id.score_name == "AOV":
                department = rec.category_lvl1_selection
                if department._name != 'hr.department':
                    continue
                dept_domain = [
                    ('department_id', '=', department.id),
                    ('date', '>=', rec.start_date),
                    ('date', '<=', rec.end_date),
                    ('invoice_id.payment_state', '=', 'paid')
                ]
                car_records = self.env['department.charges'].search([
                    ('date', '>=', rec.start_date),
                    ('date', '<=', rec.start_date),
                    ('invoice_id.payment_state', '=', 'paid')
                ])

                total_cars = len(set(car_records.mapped('car_number')))
                dept_record_charges = self.env["department.charges"].search(dept_domain)
                total_dept_sum = sum(dept_record_charges.mapped('charge_amount'))
                rec.score_category_lvl1 = total_dept_sum / total_cars if total_cars > 0 else 0

            if rec.score_id.score_name == "Leads":
                medium = rec.category_lvl1_selection
                # Additional check for medium type
                if medium._name != 'utm.medium':
                    continue
                # Get company from context or score
                company_id = self._context.get('company_id', rec.score_id.company_id.id)

                # Search for leads matching the medium and date range
                domain = [
                    ('lead_date', '>=', rec.start_date),
                    ('lead_date', '<=', rec.end_date),
                    ('stage_id.sequence', 'in', [0, 1]),
                    ('medium_id', '=', medium.id),
                    ('company_id', '=', company_id)
                ]
                records = self.env['crm.lead'].search(domain)
                rec.score_category_lvl1 = len(records)

            if rec.score_id.score_name == "Conversion":
                medium = rec.category_lvl1_selection
                # Additional check for medium type
                if medium._name != 'utm.medium':
                    continue
                # Get company from context or score
                company_id = self._context.get('company_id', rec.score_id.company_id.id)

                # Search for conversions (stage_id.sequence = 2) matching the medium and date range
                domain = [
                    ('lead_date', '>=', rec.start_date),
                    ('lead_date', '<=', rec.end_date),
                    ('stage_id.sequence', '=', 2),
                    ('medium_id', '=', medium.id),
                    ('company_id', '=', company_id)
                ]
                records = self.env['crm.lead'].search(domain)
                rec.score_category_lvl1 = len(records)

            # elif rec.score_id.score_name == "Customer Retention":
            #     department = rec.category_lvl1_selection
            #     records=self.env['fleet.repair.feedback'].search([
            #         ('start_date', '>=', rec.start_date),
            #         ('end_date', '<=', rec.end_date)
            #     ])

            if rec.score_id.score_name == "Customer Retention":
                department = rec.category_lvl1_selection
                # Check if category_lvl1_selection is a department
                if not department or department._name != 'hr.department':
                    rec.score_category_lvl1 = 0
                    return

                # Get all feedback records in the date range
                records = self.env['fleet.repair.feedback'].search([
                    ('feedback_date', '>=', rec.start_date),
                    ('feedback_date', '<=', rec.end_date),
                    ('customer_id', '!=', False)
                ])

                # Get unique customer IDs from the period
                customer_ids_in_period = records.mapped('customer_id.id')
                unique_customer_ids = list(set([cid for cid in customer_ids_in_period if cid]))
                if not unique_customer_ids:
                    rec.score_category_lvl1 = 0
                else:
                    # Get ALL feedbacks for these customers (both in current period AND before)
                    all_feedbacks = self.env['fleet.repair.feedback'].search([
                        ('customer_id', 'in', unique_customer_ids),
                        ('feedback_date', '<=', rec.end_date),
                        # Includes both current period and before (use context date)
                        ('feedback_date', '!=', False),
                        ('customer_id', '!=', False)
                    ])

                    # Count ALL feedbacks per customer (including current period and before)

                    total_feedback_count = {}
                    for feedback in all_feedbacks:
                        customer_id = feedback.customer_id.id
                        total_feedback_count[customer_id] = total_feedback_count.get(customer_id, 0) + 1

                    # Categorize based on TOTAL feedback count (current + previous)

                    # new customer = 1, repeated customer = 2, client = 3, advocate = 4+

                    new_customers = [cid for cid in unique_customer_ids if total_feedback_count.get(cid, 0) == 1]
                    repeated_customers = [cid for cid in unique_customer_ids if total_feedback_count.get(cid, 0) == 2]
                    clients = [cid for cid in unique_customer_ids if total_feedback_count.get(cid, 0) == 3]
                    advocates = [cid for cid in unique_customer_ids if total_feedback_count.get(cid, 0) >= 4]

                    # print("Department name:", department.name)
                    # print("Total feedback count (current + previous):", total_feedback_count)
                    # print("New customers (1 feedback):", len(new_customers))
                    # print("Repeated customers (2 feedbacks):", len(repeated_customers))
                    # print("Clients (3 feedbacks):", len(clients))
                    # print("Advocates (4+ feedbacks):", len(advocates))

                    # Return count based on department name
                    if department.name == "New Customers":
                        rec.score_category_lvl1 = len(new_customers)
                    elif department.name == "Repeated Customers":
                        rec.score_category_lvl1 = len(repeated_customers)
                    elif department.name == "Client":
                        rec.score_category_lvl1 = len(clients)
                    elif department.name == "Advocate":
                        rec.score_category_lvl1 = len(advocates)
                    else:
                        rec.score_category_lvl1 = 0

            if rec.score_id.score_name == "Income":
                department = rec.category_lvl1_selection
                if department._name != 'hr.department':
                    continue
                domain = [
                    ('department_id', '=', department.id),
                    ('date', '>=', rec.start_date),
                    ('date', '<=', rec.end_date),
                    ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),  # Customer invoices and refunds
                    # Only posted invoices
                    ('move_id.payment_state', '=', 'paid'),  # Only paid invoices
                    ('company_id', '=', rec.score_id.company_id.id),
                    ('account_id.account_type', 'in', ['income', 'income_direct_cost'])
                ]
                records = self.env['account.move.line'].search(domain)
                rec.score_category_lvl1 = -sum(records.mapped('balance'))


            elif rec.score_id.score_name == "Expense":
                department = rec.category_lvl1_selection
                if department._name != 'hr.department':
                    continue

                expense_bills = [
                    ('department_id', '=', department.id),
                    ('company_id', '=', rec.score_id.company_id.id),
                    ('date', '>=', rec.start_date),
                    ('date', '<=', rec.end_date),
                    ('account_id.account_type', 'in', ['expense', 'expense_direct_cost', 'expense_depreciation']),
                    '|',
                    '&', ('move_id.move_type', '=', 'in_invoice'), ('move_id.payment_state', '=', 'paid'),
                    '&', ('move_id.move_type', '=', 'entry'), ('move_id.state', '=', 'posted'),
                ]

                # expense_bills=[
                #     ('product_id', '=', department.id),
                #     ('date', '>=', rec.start_date),
                #     ('date', '<=', rec.end_date),
                #     ('company_id', '=', rec.score_id.company_id.id),
                #     ('account_id.account_type', 'in', ['expense', 'expense_direct_cost', 'expense_depreciation'])
                # ]

                records = self.env['account.move.line'].search(expense_bills)
                # expense_records = self.env['hr.expense'].search(expense_bills)

                rec.score_category_lvl1 = sum(records.mapped('debit'))
                if records:
                    print('yes')
                else:
                    print('no')

                for i in records:
                    print('exp dept', i.department_id.name)
                    print('exp name', i.name)
                    print('exp debit', i.debit)

            if rec.score_id.score_name == "Cashflow":
                department = rec.category_lvl1_selection
                if department._name != 'hr.department':
                    continue

                # Search ALL posted journal entries for this department in the date range
                records = self.env['account.move.line'].search([
                    ('date', '>=', rec.start_date),
                    ('date', '<=', rec.end_date),
                    ('move_id.state', '=', 'posted'),
                    ('company_id', '=', rec.score_id.company_id.id),
                    ('department_id', '=', department.id),
                ])

                operating_in = 0.0
                operating_out = 0.0

                for line in records:
                    account_type = line.account_id.account_type
                    balance = line.balance
                    move = line.move_id
                    move_type = move.move_type or 'N/A'
                    account_name = line.account_id.name or 'N/A'

                    # TAX LINES: Include tax in cash flow (part of actual payment/receipt)
                    if line.display_type == 'tax' or line.tax_line_id:
                        if move_type == 'in_invoice':
                            # Vendor bill: Tax is part of cash outflow
                            tax_amount = abs(balance) if balance < 0 else balance
                            operating_out += tax_amount
                            continue
                        elif move_type == 'out_invoice':
                            # Customer invoice: Tax is part of cash inflow
                            tax_amount = abs(balance)
                            operating_in += tax_amount
                            continue
                        else:
                            continue

                    # Skip tax accounts (GST/VAT) - but only if NOT a tax line (already handled above)
                    if any(kw in account_name for kw in ['GST', 'TAX', 'SGST', 'CGST', 'IGST']):
                        continue

                    # Skip bank/payment accounts (they're just transfers, not cash flow)
                    if account_type in ['asset_cash', 'liability_credit_card']:
                        continue

                    # Skip current assets that are not receivables
                    if account_type == 'asset_current' and account_type != 'asset_receivable':
                        if any(kw in account_name.lower() for kw in ['outstanding', 'payment', 'bank']):
                            continue

                    # Operating Activities - Inflow
                    if account_type in ['income', 'income_direct_cost']:
                        operating_in += abs(balance)
                    # Operating Activities - Outflow
                    elif account_type in ['expense', 'expense_depreciation', 'expense_direct_cost']:
                        operating_out += balance
                    # Receivable (advance payments, but skip accrual entries from invoices)
                    elif account_type == 'asset_receivable' and balance > 0:
                        if move_type == 'out_invoice':
                            continue  # Skip accrual entries - no cash received yet
                        operating_in += balance
                    # Payable (advance payments, but skip accrual entries from bills)
                    elif account_type == 'liability_payable' and balance < 0:
                        if move_type == 'in_invoice':
                            continue  # Skip accrual entries - no cash paid yet
                        operating_out += abs(balance)
                    # Skip investing/financing - only "Operating" at this level

                rec.score_category_lvl1 = operating_in - operating_out
