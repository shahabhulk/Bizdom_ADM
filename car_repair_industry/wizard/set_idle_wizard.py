# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class SetIdleWizard(models.TransientModel):
    _name = 'set.idle.wizard'
    _description = 'Set Employee Idle Activity'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    employee_name = fields.Char(related='employee_id.name', string='Employee Name', readonly=True)
    current_work_status = fields.Selection(related='employee_id.work_status', string='Current Status', readonly=True)
    is_already_idle = fields.Boolean(compute='_compute_idle_state')
    current_idle_reason = fields.Selection([
        ('no_job', 'No Job'),
        ('training', 'Training'),
        ('meeting', 'Meeting'),
        ('break_lunch', 'Break / Lunch'),
        ('learning', 'No Job'),
    ], compute='_compute_idle_state', string='Current Idle Reason')
    current_idle_display = fields.Char(compute='_compute_idle_state', string='Current Activity')

    idle_reason = fields.Selection([
        ('no_job', 'No Job'),
        ('training', 'Training'),
        ('meeting', 'Meeting'),
        ('break_lunch', 'Break / Lunch'),
    ], string='Select Activity', required=True, default='no_job')
    notes = fields.Text(string='Notes / Details (Optional)')

    @api.depends('employee_id', 'employee_id.is_idle_running', 'employee_id.idle_reason')
    def _compute_idle_state(self):
        reason_map = {
            'training': '🎓 Training',
            'no_job': '📋 No Job',
            'learning': '📋 No Job',
            'meeting': '👥 Meeting',
            'break_lunch': '☕ Break / Lunch',
        }
        for rec in self:
            rec.is_already_idle = bool(rec.employee_id and rec.employee_id.is_idle_running and rec.employee_id.work_status == 'idle')
            rec.current_idle_reason = rec.employee_id.idle_reason if rec.is_already_idle else False
            rec.current_idle_display = reason_map.get(rec.employee_id.idle_reason, '') if rec.is_already_idle else ''

    def action_start_idle(self):
        self.ensure_one()
        if not self.employee_id:
            raise UserError(_("No employee selected."))
        self.employee_id.action_start_idle(
            idle_reason=self.idle_reason,
            notes=self.notes
        )
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_choose_training(self):
        self.idle_reason = 'training'
        return self.action_start_idle()

    def action_choose_no_job(self):
        self.idle_reason = 'no_job'
        return self.action_start_idle()

    def action_choose_learning(self):
        self.idle_reason = 'no_job'
        return self.action_start_idle()

    def action_choose_meeting(self):
        self.idle_reason = 'meeting'
        return self.action_start_idle()

    def action_choose_break_lunch(self):
        self.idle_reason = 'break_lunch'
        return self.action_start_idle()

    def action_end_idle(self):
        self.ensure_one()
        if not self.employee_id:
            raise UserError(_("No employee selected."))
        self.employee_id.action_end_idle()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
