from odoo import models, fields, _, api, Command
from odoo.exceptions import UserError


class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense'

    payment_mode = fields.Selection(default='company_account')
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        help='Department for reporting. Defaults from employee, but can be changed manually.',
    )

    @api.onchange('employee_id')
    def _onchange_employee_id_set_department(self):
        for rec in self:
            rec.department_id = rec.employee_id.department_id

    def _prepare_move_lines_vals(self):
        vals = super()._prepare_move_lines_vals()
        vals['department_id'] = self.department_id.id
        return vals

    def _prepare_payments_vals(self):
        move_vals, payment_vals = super()._prepare_payments_vals()
        if self.department_id and move_vals.get('line_ids'):
            updated_line_ids = []
            for command in move_vals['line_ids']:
                if isinstance(command, tuple) and len(command) >= 3 and command[0] == 0 and isinstance(command[2], dict):
                    line_vals = dict(command[2])
                    line_vals.setdefault('department_id', self.department_id.id)
                    updated_line_ids.append(Command.create(line_vals))
                else:
                    updated_line_ids.append(command)
            move_vals['line_ids'] = updated_line_ids
        return move_vals, payment_vals



class HrExpenseSheetCustom(models.Model):
    _inherit = 'hr.expense.sheet'


    def action_force_done(self):
        for sheet in self:
            if sheet.state == 'done':
                raise UserError(_("This expense report is already done."))

            # Step 1: Submit (if draft)
            if sheet.state == 'draft':
                sheet._do_submit()

            # Step 2: Approve + create journal entries (if submitted)
            if sheet.state == 'submit':
                sheet._do_approve()

            # Step 3: Post journal entries (if approved)
            if sheet.state == 'approve':
                sheet.action_sheet_move_post()

            # Step 4: Register payment (if employee-paid and posted)
            if sheet.state == 'post' and sheet.payment_mode == 'own_account':
                posted_unpaid = sheet.sudo().account_move_ids.filtered(
                    lambda m: m.state == 'posted'
                            and m.payment_state not in ('paid', 'in_payment')
                )
                if posted_unpaid:
                    self.env['account.payment.register'].sudo().with_context(
                        active_model='account.move',
                        active_ids=posted_unpaid.ids,
                        dont_redirect_to_payments=True,
                    ).create({}).action_create_payments()