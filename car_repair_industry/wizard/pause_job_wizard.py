# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class PauseJobWizard(models.TransientModel):
    _name = 'pause.job.wizard'
    _description = 'Pause Job Dialog'

    status_log_id = fields.Many2one('hr.employee.status.log', string='Job Log', required=True)
    pause_reason = fields.Selection([
        ('waiting_parts', '🟡 Waiting for Parts'),
        ('waiting_approval', '🔵 Waiting for Customer Approval'),
        ('waiting_qc', '🟣 Waiting for QC'),
        ('assistance_required', '🟠 Assistance Required'),
        ('tools_issue', '🔷 Tool / Equipment Unavailable'),
        ('other', '⚪ Other'),
    ], string='Pause Reason', required=True, default='waiting_parts')
    notes = fields.Text(string='Notes / Reason Details')

    def action_confirm_pause(self):
        self.ensure_one()
        log = self.status_log_id
        if not log:
            return {'type': 'ir.actions.act_window_close'}

        now = fields.Datetime.now()
        # 1. Pause collective / individual running timers on selected service lines
        selected_lines = log.service_line_ids.filtered(lambda l: l.is_group_selected and l.line_status != 'completed')
        if not selected_lines:
            raise UserError(_("Please select at least 1 service using the checkbox to stop."))

        for line in selected_lines:
            if line.is_timer_running:
                line.action_pause_timer()
            else:
                line.write({
                    'line_status': 'paused',
                    'is_timer_paused': True,
                    'is_timer_running': False,
                    'is_pause_running': True,
                    'pause_timer_start': now,
                })
            line.write({
                'pause_reason': self.pause_reason,
                'pause_notes': self.notes or '',
            })

        # 2. Check if all running lines are now paused
        remaining_running = log.service_line_ids.filtered(lambda l: l.is_timer_running or l.line_status == 'working')

        if not remaining_running:
            w_delta = 0.0
            if log.is_timer_running and log.timer_last_start:
                w_delta = max(0.0, (now - log.timer_last_start).total_seconds())
            new_acc = (log.accumulated_seconds or 0.0) + w_delta

            log.write({
                'status': 'paused',
                'job_status': 'paused',
                'pause_reason': self.pause_reason,
                'pause_notes': self.notes or '',
                'is_timer_running': False,
                'timer_last_start': False,
                'timer_end': now,
                'accumulated_seconds': new_acc,
                'is_pause_running': True,
                'pause_timer_start': now if not log.is_pause_running else (log.pause_timer_start or now),
                'is_current_activity': True,
            })
            if log.employee_id:
                now = fields.Datetime.now()
                other_pending = self.env['fleet.repair.service.line'].search([
                    ('employee_id', '=', log.employee_id.id),
                    ('id', 'not in', log.service_line_ids.ids),
                    ('repair_id.state', 'not in', ['delivery', 'delivered', 'done', 'invoiced', 'cancel']),
                    ('line_status', 'not in', ['completed', 'paused']),
                    ('is_timer_paused', '=', False),
                ], limit=1)
                if other_pending:
                    emp_vals = {
                        'work_status': 'idle',
                        'is_idle_running': True,
                        'idle_timer_start': now,
                        'idle_accumulated_seconds': 0.0,
                        'current_status_start': now,
                        'current_job_id': False,
                        'current_service_line_id': False,
                        'current_pause_reason': False,
                        'status_notes': self.notes or '',
                    }
                else:
                    emp_vals = {
                        'work_status': 'paused',
                        'current_pause_reason': self.pause_reason,
                        'status_notes': self.notes or '',
                    }
                    if log.job_id:
                        emp_vals['current_job_id'] = log.job_id.id
                    if log.service_line_id:
                        emp_vals['current_service_line_id'] = log.service_line_id.id
                log.employee_id.sudo().write(emp_vals)
        else:
            for rrun in remaining_running:
                rrun.write({
                    'is_collective': len(remaining_running) > 1,
                    'collective_member_count': len(remaining_running),
                })
            log.write({
                'status': 'job',
                'job_status': 'working',
                'is_timer_running': True,
                'is_pause_running': False,
            })
            if log.employee_id:
                log.employee_id.sudo().write({
                    'work_status': 'job',
                    'current_pause_reason': False,
                    'status_notes': self.notes or '',
                })

        log._compute_job_status()
        log._compute_collective_timer_info()
        log._compute_time_metrics()
        log._compute_display_status()
        log._compute_display_name()
        new_log = log

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.status.log',
            'res_id': new_log.id,
            'view_mode': 'form',
            'view_id': self.env.ref('car_repair_industry.view_employee_work_status_form').id,
            'target': 'current',
        }

    def action_cancel(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window_close'}
