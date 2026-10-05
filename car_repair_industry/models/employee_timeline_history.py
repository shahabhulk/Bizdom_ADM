# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class EmployeeTimelineHistory(models.Model):
    _name = 'employee.timeline.history'
    _description = 'Employee Timeline History'
    _order = 'start_datetime desc, id desc'
    _rec_name = 'display_name'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade', index=True)
    status = fields.Selection([
        ('job', 'Active Job'),
        ('working', 'Working'),
        ('assigned', 'Assigned'),
        ('paused', 'Paused'),
        ('waiting_car', 'Waiting for Car'),
        ('parts_unavailable', 'Parts Arrival / Not Available'),
        ('tools_issue', 'Tools Issue'),
        ('approval_pending', 'Customer Approval Pending'),
        ('idle', 'Idle'),
        ('completed', 'Completed'),
    ], string='Status', required=True, default='assigned')
    job_status = fields.Selection([
        ('assigned', 'Assigned'),
        ('working', 'Working'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
    ], string='Job Status', default='assigned')

    display_status = fields.Char(
        string='Status',
        compute='_compute_display_status',
        store=True,
    )

    @api.depends('status', 'job_status', 'pause_reason')
    def _compute_display_status(self):
        status_dict = dict(self._fields['status'].selection)
        for rec in self:
            if rec.status == 'idle':
                rec.display_status = 'Idle'
            elif rec.status == 'completed' or rec.job_status == 'completed':
                rec.display_status = 'Completed'
            elif rec.status == 'paused' or rec.job_status == 'paused' or rec.pause_reason:
                rec.display_status = 'Paused'
            elif rec.status in ('working', 'job') or rec.job_status == 'working':
                rec.display_status = 'Working'
            elif rec.status == 'assigned' or rec.job_status == 'assigned':
                rec.display_status = 'Assigned'
            else:
                rec.display_status = status_dict.get(rec.status, rec.status or 'Assigned')

    @api.depends('employee_id.name', 'display_status', 'job_id.sequence', 'job_id.name', 'start_datetime')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.employee_id:
                parts.append(rec.employee_id.name)
            if rec.display_status:
                parts.append(rec.display_status)
            if rec.job_id:
                parts.append(rec.job_id.sequence or rec.job_id.name or f"JC #{rec.job_id.id}")
            if rec.start_datetime:
                parts.append(fields.Datetime.to_string(rec.start_datetime))
            rec.display_name = " - ".join(parts) if parts else (_("Timeline Event #%s") % (rec.id or ''))

    display_name = fields.Char(string='Name', compute='_compute_display_name', store=True)

    pause_reason = fields.Selection([
        ('waiting_parts', '📦 Waiting for Parts'),
        ('waiting_approval', '👤 Waiting for Customer Approval'),
        ('waiting_qc', '🟣 Waiting for QC'),
        ('assistance_required', '🟠 Assistance Required'),
        ('tools_issue', '🛠 Tool / Equipment Unavailable'),
        ('other', '⚪ Other'),
    ], string='Pause Reason')
    pause_notes = fields.Text(string='Pause Notes')
    pause_reason_display = fields.Char(string='Pause Reason', compute='_compute_pause_reason_display')

    idle_reason = fields.Selection([
        ('no_job', 'No Job'),
        ('training', 'Training'),
        ('meeting', 'Meeting'),
        ('break_lunch', 'Break / Lunch'),
        ('learning', 'No Job'),
    ], string='Idle Reason')
    idle_reason_display = fields.Char(string='Idle Reason', compute='_compute_pause_reason_display')

    @api.depends('pause_reason', 'status', 'job_status', 'idle_reason', 'pause_notes', 'notes')
    def _compute_pause_reason_display(self):
        reason_map = {
            'waiting_parts': '🟡 Waiting for Parts',
            'waiting_approval': '🔵 Waiting for Customer Approval',
            'waiting_qc': '🟣 Waiting for QC',
            'assistance_required': '🟠 Assistance Required',
            'tools_issue': '🔷 Tool / Equipment Unavailable',
            'other': '⚪ Other',
        }
        idle_map = {
            'no_job': '📋 No Job',
            'training': '🎓 Training',
            'learning': '📋 No Job',
            'meeting': '👥 Meeting',
            'break_lunch': '☕ Break / Lunch',
        }
        for rec in self:
            if rec.status == 'idle':
                rec.idle_reason_display = idle_map.get(rec.idle_reason, rec.notes or 'Idle')
                rec.pause_reason_display = '—'
            elif rec.pause_reason and rec.pause_reason in reason_map:
                rec.pause_reason_display = reason_map[rec.pause_reason]
                rec.idle_reason_display = '—'
            elif rec.pause_reason:
                pause_dict = dict(self._fields['pause_reason'].selection) if 'pause_reason' in self._fields else {}
                rec.pause_reason_display = pause_dict.get(rec.pause_reason, rec.pause_reason)
                rec.idle_reason_display = '—'
            elif rec.job_status == 'completed' or rec.status == 'completed':
                rec.pause_reason_display = '✅ Completed'
                rec.idle_reason_display = '—'
            elif rec.job_status == 'working' or rec.status in ('working', 'job'):
                rec.pause_reason_display = '🔧 Working'
                rec.idle_reason_display = '—'
            elif rec.job_status == 'paused' or rec.status == 'paused':
                rec.pause_reason_display = '⚪ Other'
                rec.idle_reason_display = '—'
            elif rec.job_status == 'assigned' or rec.status == 'assigned':
                rec.pause_reason_display = '📋 Assigned'
                rec.idle_reason_display = '—'
            else:
                rec.pause_reason_display = '—'
                rec.idle_reason_display = '—'

    job_id = fields.Many2one('fleet.repair', string='Job Card', index=True)
    service_line_id = fields.Many2one('fleet.repair.service.line', string='Service Line')
    service_name = fields.Char(string='Service / Work')
    license_plate = fields.Many2one(
        'fleet.vehicle',
        string='License Plate',
        related='job_id.license_plate',
        store=True,
        readonly=True,
    )
    fleet_id = fields.Many2one(
        'fleet.vehicle.model.brand',
        string='Car',
        related='job_id.fleet_id',
        store=True,
        readonly=True,
    )
    model_name = fields.Many2one(
        'fleet.vehicle.model',
        string='Model',
        related='job_id.model_name',
        store=True,
        readonly=True,
    )

    start_datetime = fields.Datetime(string='Start Time', default=fields.Datetime.now, required=True, index=True)
    end_datetime = fields.Datetime(string='End Time', index=True)
    duration = fields.Float(string='Duration (Hours)', compute='_compute_duration', store=True)
    duration_display = fields.Char(string='Duration', compute='_compute_time_metrics')
    worked_time_display = fields.Char(string='Worked Time', compute='_compute_time_metrics')
    pause_time_display = fields.Char(string='Pause Time', compute='_compute_time_metrics')
    total_elapsed_display = fields.Char(string='Total Elapsed', compute='_compute_time_metrics')
    accumulated_seconds = fields.Float(string='Worked Seconds', default=0.0)
    pause_accumulated_seconds = fields.Float(string='Pause Seconds', default=0.0)
    notes = fields.Text(string='Notes')
    status_log_id = fields.Many2one('hr.employee.status.log', string='Status Log', ondelete='set null')

    @api.depends('start_datetime', 'end_datetime')
    def _compute_duration(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.start_datetime:
                end_t = rec.end_datetime or now
                rec.duration = max(0.0, (end_t - rec.start_datetime).total_seconds() / 3600.0)
            else:
                rec.duration = 0.0

    @api.depends('start_datetime', 'end_datetime', 'accumulated_seconds', 'pause_accumulated_seconds', 'status')
    def _compute_time_metrics(self):
        now = fields.Datetime.now()
        for rec in self:
            end_t = rec.end_datetime or now
            start_t = rec.start_datetime or end_t
            total_sec = max(0, (end_t - start_t).total_seconds())

            if rec.status == 'paused' or rec.job_status == 'paused':
                pause_sec = total_sec
                worked_sec = rec.accumulated_seconds or 0.0
            elif rec.status in ('working', 'job') or rec.job_status == 'working':
                worked_sec = total_sec
                pause_sec = rec.pause_accumulated_seconds or 0.0
            elif rec.status == 'idle':
                worked_sec = 0.0
                pause_sec = 0.0
            elif rec.status == 'completed' or rec.job_status == 'completed':
                worked_sec = rec.accumulated_seconds or total_sec
                pause_sec = rec.pause_accumulated_seconds or 0.0
            else:
                worked_sec = rec.accumulated_seconds or 0.0
                pause_sec = rec.pause_accumulated_seconds or 0.0

            def _fmt(sec):
                s = max(0, int(round(sec)))
                h = s // 3600
                m = (s % 3600) // 60
                sec_left = s % 60
                return f"{h:02d}:{m:02d}:{sec_left:02d}"

            rec.duration_display = _fmt(total_sec)
            rec.worked_time_display = _fmt(worked_sec)
            rec.pause_time_display = _fmt(pause_sec)
            rec.total_elapsed_display = _fmt(total_sec)

    @api.model
    def create_activity_log(self, employee_id, status, **vals):
        """Creates a timeline history record for the employee and closes any open previous activity."""
        now = fields.Datetime.now()
        emp_id = employee_id.id if hasattr(employee_id, 'id') else employee_id
        if not emp_id:
            return False

        job_id = vals.get('job_id') or False
        if hasattr(job_id, 'id'):
            job_id = job_id.id

        # Check if an open timeline record already exists for this employee
        open_prev = self.search([
            ('employee_id', '=', emp_id),
            ('end_datetime', '=', False),
        ], order='id desc')

        # If an open record already matches the SAME status for the SAME job, update it instead of creating a duplicate!
        status_family = ('working', 'job') if status in ('working', 'job') else (status,)
        matching_open = open_prev.filtered(
            lambda r: r.status in status_family and ((not job_id and not r.job_id) or (r.job_id and r.job_id.id == job_id))
        )
        if matching_open:
            target = matching_open[0]
            update_vals = {}
            if vals.get('pause_reason') and target.pause_reason != vals.get('pause_reason'):
                update_vals['pause_reason'] = vals.get('pause_reason')
            if vals.get('pause_notes') and target.pause_notes != vals.get('pause_notes'):
                update_vals['pause_notes'] = vals.get('pause_notes')
            if vals.get('idle_reason') and target.idle_reason != vals.get('idle_reason'):
                update_vals['idle_reason'] = vals.get('idle_reason')
            if vals.get('service_name') and not target.service_name:
                update_vals['service_name'] = vals.get('service_name')
            if vals.get('accumulated_seconds'):
                update_vals['accumulated_seconds'] = vals.get('accumulated_seconds')
            if vals.get('pause_accumulated_seconds'):
                update_vals['pause_accumulated_seconds'] = vals.get('pause_accumulated_seconds')
            if vals.get('status_log_id') and not target.status_log_id:
                update_vals['status_log_id'] = vals.get('status_log_id')
            if update_vals:
                target.write(update_vals)
            return target

        # Close any open previous timeline record for this employee with a DIFFERENT status
        for prev in open_prev:
            prev.write({
                'end_datetime': now,
            })

        log_vals = {
            'employee_id': emp_id,
            'status': status,
            'job_status': vals.get('job_status') or ('working' if status in ('working', 'job') else status),
            'start_datetime': vals.get('start_datetime') or now,
            'end_datetime': vals.get('end_datetime') or False,
            'job_id': job_id,
            'service_line_id': vals.get('service_line_id') or False,
            'service_name': vals.get('service_name') or False,
            'pause_reason': vals.get('pause_reason') or False,
            'pause_notes': vals.get('pause_notes') or False,
            'idle_reason': vals.get('idle_reason') or False,
            'notes': vals.get('notes') or False,
            'accumulated_seconds': vals.get('accumulated_seconds') or 0.0,
            'pause_accumulated_seconds': vals.get('pause_accumulated_seconds') or 0.0,
            'status_log_id': vals.get('status_log_id') or False,
        }
        return self.create(log_vals)

    def init(self):
        super().init()
        # Seed existing status logs into employee timeline history if not present
        self.env.cr.execute("""
            INSERT INTO employee_timeline_history (
                employee_id, status, job_status, pause_reason, pause_notes, idle_reason, notes,
                job_id, service_line_id, start_datetime, end_datetime,
                accumulated_seconds, pause_accumulated_seconds, status_log_id, create_date, write_date
            )
            SELECT 
                l.employee_id,
                l.status,
                l.job_status,
                l.pause_reason,
                l.pause_notes,
                l.idle_reason,
                l.notes,
                l.job_id,
                l.service_line_id,
                l.start_datetime,
                l.end_datetime,
                COALESCE(l.accumulated_seconds, 0.0),
                COALESCE(l.pause_accumulated_seconds, 0.0),
                l.id,
                COALESCE(l.create_date, NOW() AT TIME ZONE 'UTC'),
                COALESCE(l.write_date, NOW() AT TIME ZONE 'UTC')
            FROM hr_employee_status_log l
            WHERE NOT EXISTS (
                SELECT 1 FROM employee_timeline_history eth WHERE eth.status_log_id = l.id
            );
        """)

    def action_open_repair_order(self):
        self.ensure_one()
        if not self.job_id:
            return False
        return {
            'name': _('Job Card #%s') % (self.job_id.sequence or self.job_id.name or self.job_id.id),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.repair',
            'res_id': self.job_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
