# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

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
        selected_running_lines = log.service_line_ids.filtered(lambda l: l.is_group_selected and l.is_timer_running)
        for line in selected_running_lines:
            line.action_pause_timer()

        # 2. Check if all running lines are now paused
        remaining_running = log.service_line_ids.filtered(lambda l: l.is_timer_running)

        if not remaining_running:
            if log.is_timer_running and log.timer_last_start:
                delta = (now - log.timer_last_start).total_seconds()
                log.accumulated_seconds = (log.accumulated_seconds or 0.0) + delta
            log.write({
                'status': 'paused',
                'job_status': 'paused',
                'pause_reason': self.pause_reason,
                'pause_notes': self.notes or '',
                'is_timer_running': False,
                'timer_last_start': False,
                'timer_end': now,
                'is_pause_running': True,
                'pause_timer_start': now if not log.is_pause_running else (log.pause_timer_start or now),
                'is_current_activity': True,
            })
            if log.employee_id:
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
            log.write({
                'pause_reason': self.pause_reason,
                'pause_notes': self.notes or '',
                'is_pause_running': True,
                'pause_timer_start': now if not log.is_pause_running else (log.pause_timer_start or now),
            })
            if log.employee_id:
                log.employee_id.sudo().write({
                    'current_pause_reason': self.pause_reason,
                    'status_notes': self.notes or '',
                })

        log._compute_collective_timer_info()
        new_log = log

        # Record into employee.timeline.history model
        self.env['employee.timeline.history'].create_activity_log(
            log.employee_id.id,
            status='paused',
            job_id=log.job_id.id if log.job_id else False,
            service_line_id=log.service_line_id.id if log.service_line_id else False,
            service_name=new_log.service_name or (log.service_name or ''),
            pause_reason=self.pause_reason,
            pause_notes=self.notes or '',
            start_datetime=log.pause_timer_start or now,
            status_log_id=new_log.id,
            accumulated_seconds=log.accumulated_seconds or 0.0,
        )

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
        log = self.status_log_id
        if log:
            # 1. If an unconfirmed open pause was started when opening the wizard, remove it
            unconfirmed_pause = self.env['employee.timeline.history'].search([
                ('employee_id', '=', log.employee_id.id),
                ('job_id', '=', log.job_id.id if log.job_id else False),
                ('status', '=', 'paused'),
                ('end_datetime', '=', False),
            ], order='id desc', limit=1)
            if unconfirmed_pause:
                unconfirmed_pause.unlink()

            # 2. Re-open previous working activity record so there is no split or duplicate entry
            prev_working = self.env['employee.timeline.history'].search([
                ('employee_id', '=', log.employee_id.id),
                ('job_id', '=', log.job_id.id if log.job_id else False),
                ('status', 'in', ('working', 'job')),
            ], order='id desc', limit=1)
            if prev_working:
                prev_working.write({'end_datetime': False})

            log.action_start_collective_timer()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.status.log',
            'res_id': log.id if log else False,
            'view_mode': 'form',
            'view_id': self.env.ref('car_repair_industry.view_employee_work_status_form').id,
            'target': 'current',
        }
