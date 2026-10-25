# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PauseServiceWizard(models.TransientModel):
    _name = 'pause.service.wizard'
    _description = 'Pause Service Dialog'

    status_log_id = fields.Many2one('hr.employee.status.log', string='Job Log', required=True)
    pause_reason_id = fields.Many2one(
        'service.idle.reason',
        string='Service Idle Reason',
        required=True,
    )
    notes = fields.Text(string='Notes / Reason Details')
    selected_service_display = fields.Char(
        string='Selected Service(s)',
        compute='_compute_selected_service_display',
    )

    @api.depends('status_log_id')
    def _compute_selected_service_display(self):
        for rec in self:
            if rec.status_log_id:
                selected = rec.status_log_id.service_line_ids.filtered(lambda l: l.is_group_selected and l.line_status != 'completed')
                names = [l.product_id.name if l.product_id else (l.name or 'Service') for l in selected]
                rec.selected_service_display = ", ".join(names) if names else ''
            else:
                rec.selected_service_display = ''

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'pause_reason_id' in fields_list and not res.get('pause_reason_id'):
            first_reason = self.env['service.idle.reason'].search([('active', '=', True)], order='sequence, id', limit=1)
            if first_reason:
                res['pause_reason_id'] = first_reason.id
        return res

    def action_confirm_pause(self):
        self.ensure_one()
        log = self.status_log_id
        if not log:
            return {'type': 'ir.actions.act_window_close'}

        now = fields.Datetime.now()
        # 1. Selected service lines to pause
        selected_lines = log.service_line_ids.filtered(lambda l: l.is_group_selected and l.line_status != 'completed')
        if not selected_lines:
            raise UserError(_("Please select at least 1 service using the checkbox to stop."))

        reason_text = self.pause_reason_id.name if self.pause_reason_id else ''

        for line in selected_lines:
            if line.is_timer_running:
                line.with_context(skip_status_wizard=True).action_pause_timer()
            else:
                line.write({
                    'line_status': 'paused',
                    'is_timer_paused': True,
                    'is_timer_running': False,
                    'is_pause_running': True,
                    'pause_timer_start': now,
                })
            line_vals = {
                'pause_reason': reason_text,
                'pause_notes': self.notes or '',
                'is_group_selected': False,
            }
            if 'service_idle_reason_id' in line._fields:
                line_vals['service_idle_reason_id'] = self.pause_reason_id.id if self.pause_reason_id else False
            line.write(line_vals)
            line._compute_time_diff()
            line._compute_pause_duration()
            line._compute_pause_reason_display()
            if hasattr(line, '_compute_stop_reason'):
                line._compute_stop_reason()

        # 2. Check remaining running lines on the status log
        remaining_running = log.service_line_ids.filtered(lambda l: l.is_timer_running or l.line_status == 'working')

        if not remaining_running:
            # All lines on this job card are now paused! Pause the collective timer & job
            w_delta = 0.0
            if log.is_timer_running and log.timer_last_start:
                w_delta = max(0.0, (now - log.timer_last_start).total_seconds())
            new_acc = (log.accumulated_seconds or 0.0) + w_delta

            log_vals = {
                'status': 'paused',
                'job_status': 'paused',
                'is_job_stop_reason': False,
                'pause_reason': False,
                'pause_reason_id': False,
                'pause_notes': self.notes or '',
                'is_timer_running': False,
                'timer_last_start': False,
                'timer_end': now,
                'accumulated_seconds': new_acc,
                'is_pause_running': True,
                'pause_timer_start': now if not log.is_pause_running else (log.pause_timer_start or now),
                'is_current_activity': True,
            }
            log.write(log_vals)

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
                        'current_pause_reason': reason_text,
                        'status_notes': self.notes or '',
                    }
                    if log.job_id:
                        emp_vals['current_job_id'] = log.job_id.id
                    if log.service_line_id:
                        emp_vals['current_service_line_id'] = log.service_line_id.id
                log.employee_id.sudo().write(emp_vals)
        else:
            # Other services are still working! Re-calculate collective timer split
            for rrun in remaining_running:
                rrun.write({
                    'is_collective': len(remaining_running) > 1,
                    'collective_member_count': len(remaining_running),
                })
            log.write({
                'status': 'job',
                'job_status': 'working',
                'is_job_stop_reason': False,
                'pause_reason': False,
                'pause_reason_id': False,
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
        log._compute_pause_reason_display()
        log._compute_display_status()
        log._compute_display_name()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.status.log',
            'res_id': log.id,
            'view_mode': 'form',
            'view_id': self.env.ref('car_repair_industry.view_employee_work_status_form').id,
            'target': 'current',
        }

    def action_cancel(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window_close'}
