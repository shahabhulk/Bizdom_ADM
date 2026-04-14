from typing import Any
import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BizdomCategoryLvl2(models.Model):
    _name = 'bizdom.category_lvl2'
    _description = 'Bizdom Category Lvl2'

    # Relationships
    category_lvl1_id = fields.Many2one(
        'bizdom.category_lvl1', 
        string='Category Lvl1', 
        required=True,
        ondelete='cascade'
    )

    score_id = fields.Many2one(
        'bizdom.score',
        string='Score',
        related='category_lvl1_id.score_id',
        store=True,
        readonly=True
    )

    # Flexible reference: Employee for Labour/AOV/Conversion, Source for Leads
    category_lvl2_selection = fields.Reference([
        ('hr.employee', 'Employee'),
        ('utm.source', 'Source'),
        ('fleet.feedback.question','Feedback Questions'),
        ('product.product', 'Products'),
        ('product.category','Products Categories'),
        ('fleet.vehicle.model.brand','Car Brand')
    ], string='Category Lvl2', required=True)

    # Helper fields for easier access
    employee_id = fields.Many2one(
        'hr.employee',
        compute='_compute_employee_id',
        store=True,
        string='Employee'
    )

    # Department (from employee or category_lvl1)
    department_id = fields.Many2one(
        'hr.department',
        compute='_compute_department_id',
        store=True,
        string='Department'
    )

    # Medium (from category_lvl1 for Leads/Conversion)
    medium_id = fields.Many2one(
        'utm.medium',
        compute='_compute_medium_id',
        store=True,
        string='Medium'
    )

    # Source (from category_lvl2 for Leads)
    source_id = fields.Many2one(
        'utm.source',
        compute='_compute_source_id',
        store=True,
        string='Source'
    )


    # Score configuration
    type = fields.Selection([
        ('percentage', 'Percentage'),
        ('value', 'Value')
    ])

    max_category_percentage_lvl2 = fields.Float(string="Max Score")
    min_category_percentage_lvl2 = fields.Float(string="Min Score")
    max_category_value_lvl2 = fields.Float(string="Max Score")
    min_category_value_lvl2 = fields.Float(string="Min Score")

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")

    # Computed scores
    score_category_lvl2 = fields.Float(
        string="Category Score",
        compute='_compute_score_category_lvl2',
        store=True
    )

    context_score_category_lvl2 = fields.Float(
        string="Context Category Score",
        compute='_compute_context_score_category_lvl2',
        store=False
    )

    # Computed helper fields
    @api.depends('category_lvl2_selection')
    def _compute_employee_id(self):
        for rec in self:
            if rec.category_lvl2_selection and rec.category_lvl2_selection._name == 'hr.employee':
                rec.employee_id = rec.category_lvl2_selection
            else:
                rec.employee_id = False

    @api.depends('employee_id', 'category_lvl1_id')
    def _compute_department_id(self):
        for rec in self:
            if rec.employee_id:
                rec.department_id = rec.employee_id.department_id
            elif rec.category_lvl1_id and rec.category_lvl1_id.category_lvl1_selection:
                if rec.category_lvl1_id.category_lvl1_selection._name == 'hr.department':
                    rec.department_id = rec.category_lvl1_id.category_lvl1_selection
                else:
                    rec.department_id = False
            else:
                rec.department_id = False

    @api.depends('category_lvl1_id')
    def _compute_medium_id(self):
        for rec in self:
            if rec.category_lvl1_id and rec.category_lvl1_id.category_lvl1_selection:
                if rec.category_lvl1_id.category_lvl1_selection._name == 'utm.medium':
                    rec.medium_id = rec.category_lvl1_id.category_lvl1_selection
                else:
                    rec.medium_id = False
            else:
                rec.medium_id = False

    @api.depends('category_lvl2_selection')
    def _compute_source_id(self):
        for rec in self:
            if rec.category_lvl2_selection and rec.category_lvl2_selection._name == 'utm.source':
                rec.source_id = rec.category_lvl2_selection
            else:
                rec.source_id = False

    # Constraints
    @api.constrains('category_lvl2_selection', 'category_lvl1_id', 'score_id')
    def _check_duplicate_category_lvl2(self):
        """Prevent duplicate records"""
        for rec in self:
            if rec.category_lvl2_selection and rec.category_lvl1_id:
                ref_value = "%s,%s" % (
                    rec.category_lvl2_selection._name,
                    rec.category_lvl2_selection.id
                )
                existing = self.search([
                    ('category_lvl2_selection', '=', ref_value),
                    ('category_lvl1_id', '=', rec.category_lvl1_id.id),
                    ('id', '!=', rec.id)
                ])
                if existing:
                    raise ValidationError(
                        "A record already exists for this selection and category level 1."
                    )

    @api.constrains('category_lvl2_selection', 'category_lvl1_id', 'score_id')
    def _check_selection_type_match(self):
        """Ensure selection type matches score type"""
        for rec in self:
            # Skip validation if required fields are missing
            if not rec.category_lvl2_selection or not rec.category_lvl1_id or not rec.score_id:
                continue

            # Check if category_lvl1_selection exists
            if not rec.category_lvl1_id.category_lvl1_selection:
                raise ValidationError(
                    f"Please select a Category Level 1 (Department or Medium) before creating Category Level 2."
                )

            lvl1_model = rec.category_lvl1_id.category_lvl1_selection._name
            lvl2_model = rec.category_lvl2_selection._name

            # Labour/AOV/Customer Retention: Department → Employee
            if rec.score_id.score_name in ["Labour"]:
                if lvl1_model != 'hr.department':
                    raise ValidationError(
                        f"For {rec.score_id.score_name} score, Category Level 1 must be a Department, "
                        f"but you selected {lvl1_model}."
                    )
                if lvl2_model != 'hr.employee':
                    raise ValidationError(
                        f"For {rec.score_id.score_name} score, Category Level 2 must be an Employee, "
                        f"but you selected {lvl2_model}."
                    )


            elif rec.score_id.score_name == "Customer Retention":
                if lvl1_model != 'hr.department':
                    raise ValidationError(
                        f"For {rec.score_id.score_name} score, Category Level 1 must be a Department, "
                        f"but you selected {lvl1_model}."
                    )

                if lvl2_model != 'fleet.feedback.question':
                    raise ValidationError(
                        f"For {rec.score_id.score_name} score, Category Level 2 must be a Feedback Question, "
                        f"but you selected {lvl2_model}."
                    )

            # Leads: Medium → Source
            elif rec.score_id.score_name == "Leads":
                if lvl1_model != 'utm.medium':
                    raise ValidationError(
                        f"For {rec.score_id.score_name} score, Category Level 1 must be a Medium (Source), "
                        f"but you selected {lvl1_model}."
                    )
                if lvl2_model != 'utm.source':
                    raise ValidationError(
                        f"For {rec.score_id.score_name} score, Category Level 2 must be a Source (utm.source), "
                        f"but you selected {lvl2_model}."
                    )

            # Conversion: Medium → Employee
            elif rec.score_id.score_name == "Conversion":
                if lvl1_model != 'utm.medium':
                    raise ValidationError(
                        f"For {rec.score_id.score_name} score, Category Level 1 must be a Medium (Source), "
                        f"but you selected {lvl1_model}."
                    )
                if lvl2_model != 'hr.employee':
                    raise ValidationError(
                        f"For {rec.score_id.score_name} score, Category Level 2 must be an Employee, "
                        f"but you selected {lvl2_model}."
                    )

    @api.constrains('employee_id', 'category_lvl1_id')
    def _check_employee_department_match(self):
        """Ensure employee belongs to the department in category_lvl1"""
        for rec in self:
            if rec.employee_id and rec.category_lvl1_id:
                # Get department from category_lvl1
                if rec.category_lvl1_id.category_lvl1_selection:
                    lvl1_model = rec.category_lvl1_id.category_lvl1_selection._name
                    if lvl1_model == 'hr.department':
                        dept = rec.category_lvl1_id.category_lvl1_selection
                        if rec.employee_id.department_id != dept:
                            raise ValidationError(
                                f"Employee {rec.employee_id.name} does not belong to "
                                f"department {dept.name} selected in Category Level 1."
                            )

    # Backend score computation
    @api.depends('category_lvl2_selection', 'category_lvl1_id', 'score_id', 'start_date', 'end_date')
    def _compute_score_category_lvl2(self):
        """Compute score based on selection type and score name"""
        for rec in self:
            rec.score_category_lvl2 = 0.0

            if not rec.category_lvl2_selection or not rec.score_id or not rec.start_date or not rec.end_date:
                continue

            # Labour score - employee-specific
            if rec.score_id.score_name == "Labour":
                if rec.category_lvl2_selection._name != 'hr.employee':
                    continue
                employee = rec.category_lvl2_selection
                domain = [
                    ('employee_id', '=', employee.id),
                    ('date', '>=', rec.start_date),
                    ('date', '<=', rec.end_date),
                    ('invoice_id.payment_state','=','paid')
                ]
                records = self.env["labour.billing"].search(domain)
                rec.score_category_lvl2 = sum(records.mapped('charge_amount'))

            # Leads score - source-specific
            if rec.score_id.score_name == "Leads":
                if rec.category_lvl2_selection._name != 'utm.source':
                    continue
                source = rec.category_lvl2_selection
                medium = rec.medium_id
                if not medium:
                    continue
                company_id = rec.score_id.company_id.id

                domain = [
                    ('lead_date', '>=', rec.start_date),
                    ('lead_date', '<=', rec.end_date),
                    ('stage_id.sequence', 'in', [0, 1]),
                    ('medium_id', '=', medium.id),
                    ('source_id', '=', source.id),
                    ('company_id', '=', company_id)
                ]
                records = self.env['crm.lead'].search(domain)
                rec.score_category_lvl2 = len(records)

            # Conversion score - employee-specific
            if rec.score_id.score_name == "Conversion":
                if rec.category_lvl2_selection._name != 'hr.employee':
                    continue
                employee = rec.category_lvl2_selection
                medium = rec.medium_id
                if not medium:
                    continue
                # Get the user_id (salesperson) from the employee
                if not employee.user_id:
                    continue
                company_id = rec.score_id.company_id.id

                domain = [
                    ('lead_date', '>=', rec.start_date),
                    ('lead_date', '<=', rec.end_date),
                    ('stage_id.sequence', '=', 2),
                    ('medium_id', '=', medium.id),
                    ('user_id', '=', employee.user_id.id),
                    ('company_id', '=', company_id)
                ]
                records = self.env['crm.lead'].search(domain)
                rec.score_category_lvl2 = len(records)

            # AOV score - employee-specific
            if rec.score_id.score_name == "AOV":
                if rec.category_lvl2_selection._name != 'fleet.vehicle.model.brand':
                    continue
                brand = rec.category_lvl2_selection

                car_domain = [
                    ('invoice_id.fleet_repair_invoice_id.fleet_id', '=', brand.id),
                    ('department_id', '=', rec.department_id.id),
                    ('date', '>=', rec.start_date),
                    ('date', '<=', rec.end_date),
                    ('invoice_id.payment_state', '=', 'paid')
                ]
                car_records  = self.env["department.charges"].search(car_domain)
                total_car_sum = sum(car_records.mapped('charge_amount'))

                car_number_records = self.env['department.charges'].search([
                    ('date', '>=', rec.start_date),
                    ('date', '<=', rec.end_date),
                    ('invoice_id.payment_state', '=', 'paid')
                ])
                total_cars = len(set(car_number_records.mapped('car_number')))

                rec.score_category_lvl2 = total_car_sum / total_cars if total_cars > 0 else 0.0

            # Customer Retention score - feedback question -specific


            if rec.score_id.score_name == "Customer Retention":

                if rec.category_lvl2_selection._name != 'fleet.feedback.question':
                    continue
                selected_question = rec.category_lvl2_selection

                records = self.env['fleet.feedback.line'].search([
                    ('feedback_date', '>=', rec.start_date),
                    ('feedback_date', '<=', rec.end_date),
                    ('question_id', '=', selected_question.id),
                    ('rating','!=',False)
                ])

                if records:
                    ratings = [int(r.rating) for r in records if r.rating]
                    if ratings:
                        rec.score_category_lvl2 = sum(ratings) / len(ratings)
                    else:
                        rec.score_category_lvl2 = 0.0
                else:
                    rec.score_category_lvl2 = 0.0


    #        Income score - product or service specific
            if rec.score_id.score_name == "Income":
                if rec.category_lvl2_selection._name != 'product.category':
                    continue
                selected_product=rec.category_lvl2_selection

                records=self.env['account.move.line'].search([
                    ('date', '>=', rec.start_date),
                    ('date', '<=', rec.end_date),
                    ('product_id.categ_id', '=', selected_product.id),
                    ('move_id.payment_state','=','paid'),
                    ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
                ])
                rec.score_category_lvl2 = abs(sum(records.mapped('balance')))


            if rec.score_id.score_name == "Expense":
                if rec.category_lvl2_selection._name not in ('product.category', 'product.product'):
                    continue
                selected_product = rec.category_lvl2_selection
                if rec.category_lvl2_selection._name == 'product.category':
                    records = self.env['account.move.line'].search([
                        ('date', '>=', rec.start_date),
                        ('date', '<=', rec.end_date),
                        ('product_id.categ_id', '=', selected_product.id),
                        ('account_id.account_type', 'in', ['expense', 'expense_direct_cost', 'expense_depreciation']),
                        '|',
                        '&', ('move_id.move_type', '=', 'in_invoice'), ('move_id.payment_state', '=', 'paid'),
                        '&', ('move_id.move_type', '=', 'entry'), ('move_id.state', '=', 'posted'),
                    ])
                    rec.score_category_lvl2 = abs(sum(records.mapped('balance')))
                elif rec.category_lvl2_selection._name == 'product.product':
                    records = self.env['account.move.line'].search([
                        ('date', '>=', rec.start_date),
                        ('date', '<=', rec.end_date),
                        ('product_id', '=', selected_product.id),
                        ('account_id.account_type', 'in', ['expense', 'expense_direct_cost', 'expense_depreciation']),
                        '|',
                        '&', ('move_id.move_type', '=', 'in_invoice'), ('move_id.payment_state', '=', 'paid'),
                        '&', ('move_id.move_type', '=', 'entry'), ('move_id.state', '=', 'posted'),
                   ])
                    rec.score_category_lvl2 = abs(sum(records.mapped('balance')))

                # _logger.info(
                #     "Expense compute | rec_id=%s | model=%s | selected_id=%s | lines=%s | total_balance=%s",
                #     rec.id,
                #     rec.category_lvl2_selection._name,
                #     selected_product.id,
                #     len(records),
                #     rec.score_category_lvl2,
                # )





    # Frontend context score computation
    @api.depends('category_lvl2_selection', 'category_lvl1_id', 'score_id')
    def _compute_context_score_category_lvl2(self):
        """Compute score based on context dates (for frontend app)"""
        for rec in self:
            rec.context_score_category_lvl2 = 0.0

            start_date = self._context.get('force_date_start', rec.start_date)
            end_date = self._context.get('force_date_end', rec.end_date)

            if not rec.category_lvl2_selection or not rec.score_id or not start_date or not end_date:
                continue

            # Labour score with context dates
            if rec.score_id.score_name == "Labour":
                if rec.category_lvl2_selection._name != 'hr.employee':
                    continue
                employee = rec.category_lvl2_selection
                domain = [
                    ('employee_id', '=', employee.id),
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('invoice_id.payment_state', '=', 'paid')
                ]
                records = self.env["labour.billing"].search(domain)
                rec.context_score_category_lvl2 = sum(records.mapped('charge_amount'))

            # Leads score with context dates
            if rec.score_id.score_name == "Leads":
                if rec.category_lvl2_selection._name != 'utm.source':
                    continue
                source = rec.category_lvl2_selection
                medium = rec.medium_id
                if not medium:
                    continue
                company_id = self._context.get('company_id', rec.score_id.company_id.id)

                domain = [
                    ('lead_date', '>=', start_date),
                    ('lead_date', '<=', end_date),
                    ('stage_id.sequence', 'in', [0, 1]),
                    ('medium_id', '=', medium.id),
                    ('source_id', '=', source.id),
                    ('company_id', '=', company_id)
                ]
                records = self.env['crm.lead'].search(domain)
                rec.context_score_category_lvl2 = len(records)

            # Conversion score with context dates
            if rec.score_id.score_name == "Conversion":
                if rec.category_lvl2_selection._name != 'hr.employee':
                    continue
                employee = rec.category_lvl2_selection
                medium = rec.medium_id
                if not medium:
                    continue
                # Get the user_id (salesperson) from the employee
                if not employee.user_id:
                    continue
                company_id = self._context.get('company_id', rec.score_id.company_id.id)

                domain = [
                    ('lead_date', '>=', start_date),
                    ('lead_date', '<=', end_date),
                    ('stage_id.sequence', '=', 2),
                    ('medium_id', '=', medium.id),
                    ('user_id', '=', employee.user_id.id),
                    ('company_id', '=', company_id)
                ]
                records = self.env['crm.lead'].search(domain)
                rec.context_score_category_lvl2 = len(records)

            # AOV score with context dates
            if rec.score_id.score_name == "AOV":
                if rec.category_lvl2_selection._name != 'fleet.vehicle.model.brand':
                    continue
                brand = rec.category_lvl2_selection

                car_domain = [
                    ('invoice_id.fleet_repair_invoice_id.fleet_id', '=', brand.id),
                    ('department_id','=',rec.department_id.id),
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('invoice_id.payment_state', '=', 'paid')
                ]
                car_records = self.env["department.charges"].search(car_domain)
                total_car_sum = sum(car_records.mapped('charge_amount'))

                car_number_records = self.env['department.charges'].search([
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('invoice_id.payment_state', '=', 'paid')
                ])

                total_cars = len(set(car_number_records.mapped('car_number')))

                rec.context_score_category_lvl2 = total_car_sum / total_cars if total_cars > 0 else 0.0

            # Customer Retention score with context dates
            if rec.score_id.score_name == "Customer Retention":
                # Get all feedback records in the date range (use context dates)
                if rec.category_lvl2_selection._name != 'fleet.feedback.question':
                    continue

                selected_question = rec.category_lvl2_selection


                records = self.env['fleet.feedback.line'].search([
                    ('feedback_date', '>=', start_date),
                    ('feedback_date', '<=', end_date),
                    ('question_id', '=', selected_question.id),
                    ('rating', '!=', False)
                ])

                if records:
                    ratings = [int(r.rating) for r in records if r.rating]
                    if ratings:
                        rec.context_score_category_lvl2 = sum(ratings) / len(ratings)
                    else:
                        rec.context_score_category_lvl2 = 0.0
                else:
                    rec.context_score_category_lvl2 = 0.0

            if rec.score_id.score_name == "Income":
                if rec.category_lvl2_selection._name != 'product.category':
                    continue
                selected_product=rec.category_lvl2_selection

                records=self.env['account.move.line'].search([
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('product_id.categ_id', '=', selected_product.id),
                    ('move_id.payment_state','=','paid'),
                    ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
                ])
                rec.context_score_category_lvl2 = abs(sum(records.mapped('balance')))


            if rec.score_id.score_name == "Expense":
                if rec.category_lvl2_selection._name != 'product.category' and rec.category_lvl2_selection._name != 'product.product':
                    continue
                selected_product = rec.category_lvl2_selection
                if rec.category_lvl2_selection._name=='product.category':
                    records = self.env['account.move.line'].search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date),
                        ('product_id.categ_id', '=', selected_product.id),
                        ('account_id.account_type', 'in', ['expense', 'expense_direct_cost', 'expense_depreciation']),
                        '|',
                        '&', ('move_id.move_type', '=', 'in_invoice'), ('move_id.payment_state', '=', 'paid'),
                        '&', ('move_id.move_type', '=', 'entry'), ('move_id.state', '=', 'posted'),
                    ])
                    rec.context_score_category_lvl2 = abs(sum(records.mapped('balance')))
                elif rec.category_lvl2_selection._name=='product.product':
                    records = self.env['account.move.line'].search([
                        ('date', '>=', start_date),
                        ('date', '<=', end_date),
                        ('product_id', '=', selected_product.id),
                        ('account_id.account_type', 'in', ['expense', 'expense_direct_cost', 'expense_depreciation']),
                        '|',
                        '&', ('move_id.move_type', '=', 'in_invoice'), ('move_id.payment_state', '=', 'paid'),
                        '&', ('move_id.move_type', '=', 'entry'), ('move_id.state', '=', 'posted'),
                    ])
                    rec.context_score_category_lvl2 = abs(sum(records.mapped('balance')))


