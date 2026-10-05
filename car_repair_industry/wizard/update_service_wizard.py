# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class UpdateServiceWizard(models.TransientModel):
    _name = 'update.service.wizard'
    _description = 'Update Service Dialog'

    service_line_id = fields.Many2one('fleet.repair.service.line', string='Service Line', required=True)
    service_name = fields.Char(string='Service', readonly=True)
    status_log_id = fields.Many2one('hr.employee.status.log', string='Job Log')

    action_type = fields.Selection([
        ('completed', 'Completed'),
        ('pause', 'Pause Service'),
    ], string='What happened?', required=True, default='pause')

    pause_reason = fields.Selection([
        ('waiting_parts', 'Waiting for Parts'),
        ('waiting_approval', 'Waiting for Customer Approval'),
        ('waiting_qc', 'Waiting for QC'),
        ('assistance_required', 'Assistance Required'),
        ('tools_issue', 'Tool / Equipment Unavailable'),
        ('other', 'Other'),
    ], string='Pause Reason', default='waiting_parts')

    notes = fields.Text(string='Notes / Reason Details')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line_id = self.env.context.get('default_service_line_id')
        if line_id:
            line = self.env['fleet.repair.service.line'].browse(line_id)
            if line.exists():
                res['service_line_id'] = line.id
                res['service_name'] = line.product_id.name if line.product_id else (line.name or '')
                if line.status_log_id and not res.get('status_log_id'):
                    res['status_log_id'] = line.status_log_id.id
        return res

    def action_confirm(self):
        self.ensure_one()
        line = self.service_line_id
        log = self.status_log_id or line.status_log_id
        now = fields.Datetime.now()

        if self.action_type == 'completed':
            # 1. Stop work timer permanently and mark completed
            run_sec = 0.0
            if line.is_timer_running and line.timer_last_start:
                delta = (now - line.timer_last_start).total_seconds()
                if line.is_collective and (line.collective_member_count or 1) > 1:
                    delta = delta / float(line.collective_member_count)
                run_sec = delta

            # Also stop any running pause timer
            pause_delta = 0.0
            if line.is_pause_running and line.pause_timer_start:
                pause_delta = (now - line.pause_timer_start).total_seconds()

            line.write({
                'is_timer_running': False,
                'is_timer_paused': False,
                'is_pause_running': False,
                'pause_timer_start': False,
                'pause_accumulated_seconds': (line.pause_accumulated_seconds or 0.0) + pause_delta,
                'timer_end': now,
                'timer_last_start': False,
                'accumulated_seconds': (line.accumulated_seconds or 0.0) + run_sec,
                'is_collective': False,
                'is_group_selected': False,
                'line_status': 'completed',
            })
            line._compute_time_diff()
            line._sync_to_work_lines()

            # Record timeline entry for completion
            if log and log.employee_id:
                self.env['employee.timeline.history'].create_activity_log(
                    log.employee_id.id,
                    status='completed',
                    job_id=log.job_id.id if log.job_id else False,
                    service_line_id=line.id,
                    service_name=line.product_id.name if line.product_id else (line.name or ''),
                    start_datetime=now,
                    status_log_id=log.id,
                    accumulated_seconds=line.accumulated_seconds or 0.0,
                )

        elif self.action_type == 'pause':
            # 1. Pause work timer and detach from collective running group
            run_sec = 0.0
            if line.is_timer_running and line.timer_last_start:
                delta = (now - line.timer_last_start).total_seconds()
                if line.is_collective and (line.collective_member_count or 1) > 1:
                    delta = delta / float(line.collective_member_count)
                run_sec = delta

            line.write({
                'is_collective': False,
                'is_timer_running': False,
                'is_timer_paused': True,
                'timer_last_start': False,
                'accumulated_seconds': (line.accumulated_seconds or 0.0) + run_sec,
                'is_group_selected': False,
                'line_status': 'paused',
                'pause_reason': self.pause_reason,
                'pause_notes': self.notes or '',
                'is_pause_running': True,
                'pause_timer_start': now,
            })
            line._compute_time_diff()
            line._compute_pause_duration()
            line._compute_pause_reason_display()

            # Record timeline entry for paused service
            if log and log.employee_id:
                self.env['employee.timeline.history'].create_activity_log(
                    log.employee_id.id,
                    status='paused',
                    job_id=log.job_id.id if log.job_id else False,
                    service_line_id=line.id,
                    service_name=line.product_id.name if line.product_id else (line.name or ''),
                    pause_reason=self.pause_reason,
                    pause_notes=self.notes or '',
                    start_datetime=now,
                    status_log_id=log.id,
                    accumulated_seconds=line.accumulated_seconds or 0.0,
                )

        # Check remaining active services for the Collective Timer
        if log:
            active_lines = log.service_line_ids.filtered(lambda l: l.is_timer_running)
            if active_lines:
                # Update split member count for remaining active services
                active_lines.write({'collective_member_count': len(active_lines), 'is_collective': True})
                log._compute_collective_timer_info()
            else:
                # No other active service to work on: pause the Collective Timer
                pause_delta = 0.0
                if log.is_timer_running and log.timer_last_start:
                    pause_delta = (now - log.timer_last_start).total_seconds()
                log.write({
                    'status': 'paused',
                    'job_status': 'paused',
                    'pause_reason': self.pause_reason if self.action_type == 'pause' else False,
                    'pause_notes': self.notes if self.action_type == 'pause' else '',
                    'is_timer_running': False,
                    'timer_last_start': False,
                    'is_pause_running': True if self.action_type == 'pause' else False,
                    'pause_timer_start': now if self.action_type == 'pause' else False,
                    'accumulated_seconds': (log.accumulated_seconds or 0.0) + pause_delta,
                })
                if log.employee_id:
                    log.employee_id.sudo().write({
                        'work_status': 'paused',
                        'current_pause_reason': self.pause_reason if self.action_type == 'pause' else False,
                    })
                log._compute_collective_timer_info()

        return {'type': 'ir.actions.act_window_close'}
