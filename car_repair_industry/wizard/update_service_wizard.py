# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class UpdateServiceWizard(models.TransientModel):
    _name = 'update.service.wizard'
    _description = 'Stop Service Wizard'

    service_line_id = fields.Many2one('fleet.repair.service.line', string='Service Line', required=True)
    status_log_id = fields.Many2one('hr.employee.status.log', string='Job Log')
    service_name = fields.Char(string='Service Name', readonly=True)
    stop_reason_id = fields.Many2one(
        'service.idle.reason',
        string='Stop Reason',
        required=True,
    )
    # Backward compatibility alias
    pause_reason_id = fields.Many2one(
        'service.idle.reason',
        string='Stop Reason',
    )

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
        first_reason = self.env['service.idle.reason'].search([('active', '=', True)], order='sequence, id', limit=1)
        if first_reason:
            res['stop_reason_id'] = first_reason.id
            res['pause_reason_id'] = first_reason.id
        return res

    def action_confirm(self):
        self.ensure_one()
        line = self.service_line_id
        if not line:
            return {'type': 'ir.actions.act_window_close'}

        now = fields.Datetime.now()
        reason = self.stop_reason_id or self.pause_reason_id
        reason_name = reason.name if reason else 'Stop'

        # 1. Stop work timer and set to paused
        run_sec = 0.0
        if line.is_timer_running and line.timer_last_start:
            delta = (now - line.timer_last_start).total_seconds()
            if line.is_collective and (line.collective_member_count or 1) > 1:
                delta = delta / float(line.collective_member_count)
            run_sec = max(0.0, delta)

        line.write({
            'accumulated_seconds': (line.accumulated_seconds or 0.0) + run_sec,
            'timer_last_start': False,
            'is_timer_running': False,
            'is_timer_paused': True,
            'is_pause_running': True,
            'pause_timer_start': now,
            'is_collective': False,
            'is_group_selected': False,
            'line_status': 'paused',
            'pause_reason': reason_name,
            'service_idle_reason_id': reason.id if reason else False,
        })
        line._compute_time_diff()
        line._compute_pause_duration()
        line._compute_pause_reason_display()
        if hasattr(line, '_compute_stop_reason'):
            line._compute_stop_reason()
        line._sync_to_work_lines()
        line._sync_to_employee_status_log()

        if line.repair_id and line.repair_id.state not in ('done', 'cancel'):
            line.repair_id.invalidate_recordset(['service_line_ids', 'fleet_work_line_ids'])
            line.repair_id._update_header_status_from_service_lines()

        # Check remaining active services for the Collective Timer / Job Log
        log = self.status_log_id or line.status_log_id
        if not log and line.employee_id and line.repair_id:
            log = self.env['hr.employee.status.log'].search([
                ('employee_id', '=', line.employee_id.id),
                ('job_id', '=', line.repair_id.id),
            ], order='id desc', limit=1)

        if log:
            active_lines = log.service_line_ids.filtered(lambda l: l.id != line.id and (l.is_timer_running or l.line_status == 'working'))
            if active_lines:
                active_lines.write({
                    'collective_member_count': len(active_lines),
                    'is_collective': len(active_lines) > 1,
                })
                log.write({
                    'status': 'job',
                    'job_status': 'working',
                    'is_timer_running': True,
                })
                log._compute_job_status()
                log._compute_collective_timer_info()
                log._compute_time_metrics()
                log._compute_display_status()
                log._compute_display_name()
            else:
                # All active services on this log are now stopped
                w_delta = 0.0
                if log.is_timer_running and log.timer_last_start:
                    w_delta = max(0.0, (now - log.timer_last_start).total_seconds())
                new_acc = (log.accumulated_seconds or 0.0) + w_delta
                log.write({
                    'status': 'paused',
                    'job_status': 'paused',
                    'is_job_stop_reason': False,
                    'pause_reason': False,
                    'pause_reason_id': False,
                    'is_timer_running': False,
                    'timer_last_start': False,
                    'timer_end': now,
                    'accumulated_seconds': new_acc,
                    'is_pause_running': True,
                    'pause_timer_start': now if not log.is_pause_running else (log.pause_timer_start or now),
                    'is_current_activity': True,
                })
                if log.employee_id:
                    other_pending = self.env['fleet.repair.service.line'].search([
                        ('employee_id', '=', log.employee_id.id),
                        ('id', 'not in', log.service_line_ids.ids),
                        ('repair_id.state', 'not in', ['delivery', 'delivered', 'done', 'invoiced', 'cancel']),
                        ('line_status', 'not in', ['completed', 'paused']),
                        ('is_timer_paused', '=', False),
                    ], limit=1)
                    if other_pending:
                        log.employee_id.sudo().write({
                            'work_status': 'idle',
                            'is_idle_running': True,
                            'idle_timer_start': now,
                            'idle_accumulated_seconds': 0.0,
                            'current_status_start': now,
                            'current_job_id': False,
                            'current_service_line_id': False,
                            'current_pause_reason': False,
                        })
                    else:
                        log.employee_id.sudo().write({
                            'work_status': 'paused',
                            'current_pause_reason': reason_name,
                        })
                log._compute_collective_timer_info()
                log._compute_job_status()
                log._compute_pause_reason_display()
                log._compute_display_status()

        return {'type': 'ir.actions.act_window_close'}
