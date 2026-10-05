# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ResetToAssignedWizard(models.TransientModel):
    _name = 'reset.to.assigned.wizard'
    _description = 'Reset to Assigned Confirmation Wizard'

    status_log_id = fields.Many2one('hr.employee.status.log', string='Status Log')
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True)
    job_id = fields.Many2one('fleet.repair', string='Job Card', readonly=True)
    current_status = fields.Char(string='Current Status', readonly=True)
    reset_worked_hours = fields.Boolean(
        string='Also reset worked hours to 00:00:00',
        default=False,
        help='If checked, worked hours on tasks will also be wiped back to zero.'
    )

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
                'current_status': log.display_status or log.status or '',
            })
        elif active_model == 'hr.employee' and active_id:
            emp = self.env['hr.employee'].browse(active_id)
            res.update({
                'employee_id': emp.id,
                'job_id': emp.current_job_id.id if emp.current_job_id else False,
                'current_status': emp.work_status or '',
            })
        return res

    def action_confirm_reset_to_assigned(self):
        self.ensure_one()
        if self.status_log_id:
            self.status_log_id.action_reset_to_assigned(reset_worked_hours=self.reset_worked_hours)
        elif self.employee_id:
            self.employee_id.action_reset_to_assigned()
        return {'type': 'ir.actions.act_window_close'}
