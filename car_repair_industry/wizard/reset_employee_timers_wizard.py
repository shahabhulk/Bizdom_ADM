# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ResetEmployeeTimersWizard(models.TransientModel):
    _name = 'reset.employee.timers.wizard'
    _description = 'Reset All Timers Confirmation Wizard'

    status_log_id = fields.Many2one('hr.employee.status.log', string='Status Log')
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True)
    job_id = fields.Many2one('fleet.repair', string='Job Card', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if active_model == 'hr.employee.status.log' and active_id:
            log = self.env['hr.employee.status.log'].browse(active_id)
            res.update({
                'status_log_id': log.id,
                'employee_id': log.employee_id.id if log.employee_id else False,
                'job_id': log.job_id.id if log.job_id else False,
            })
        elif active_model == 'hr.employee' and active_id:
            emp = self.env['hr.employee'].browse(active_id)
            res.update({
                'employee_id': emp.id,
                'job_id': emp.current_job_id.id if emp.current_job_id else False,
            })
        return res

    def action_confirm_reset(self):
        self.ensure_one()
        if self.status_log_id:
            self.status_log_id.action_reset_all_employee_timers()
        elif self.employee_id:
            self.employee_id.action_reset_all_employee_timers()
        return {'type': 'ir.actions.act_window_close'}
