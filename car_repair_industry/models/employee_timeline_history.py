# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class EmployeeTimelineHistory(models.Model):
    _name = 'employee.timeline.history'
    _description = 'Employee Timeline History'
    _order = 'start_datetime desc, id desc'
    _rec_name = 'display_name'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade', index=True)
    status = fields.Selection([
        ('assigned', 'Assigned'),
        ('working', 'Working'),
        ('paused', 'Stop'),
        ('completed', 'Completed'),
        ('idle', 'Idle'),
        ('job', 'Active Job'),
        ('waiting_car', 'Waiting for Car'),
        ('parts_unavailable', 'Parts Arrival / Not Available'),
        ('tools_issue', 'Tools Issue'),
        ('approval_pending', 'Customer Approval Pending'),
    ], string='Status', required=True, default='completed')
    job_status = fields.Selection([
        ('assigned', 'Assigned'),
        ('working', 'Working'),
        ('paused', 'Stop'),
        ('completed', 'Completed'),
        ('idle', 'Idle'),
    ], string='Job Status', default='completed')

    display_status = fields.Char(
        string='Status',
        compute='_compute_display_status',
        store=True,
    )

    @api.depends('status', 'job_status', 'idle_reason')
    def _compute_display_status(self):
        for rec in self:
            if rec.status == 'idle' or rec.job_status == 'idle' or rec.idle_reason:
                rec.display_status = 'Idle'
            elif rec.status == 'completed' or rec.job_status == 'completed':
                rec.display_status = 'Completed'
            else:
                rec.display_status = 'Completed' if rec.end_datetime else 'Idle'

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

    pause_reason = fields.Char(string='Pause Reason')
    pause_reason_id = fields.Many2one('job.card.idle.reason', string='Pause Reason')
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

    @api.depends(
        'pause_reason',
        'pause_reason_id',
        'pause_reason_id.name',
        'status',
        'job_status',
        'idle_reason',
        'pause_notes',
        'notes',
        'status_log_id',
        'status_log_id.pause_reason_display',
        'service_line_ids.line_status',
        'service_line_ids.stop_reason',
        'service_line_ids.service_idle_reason_id',
        'service_line_ids.service_idle_reason_id.name',
        'service_line_ids.pause_reason'
    )
    def _compute_pause_reason_display(self):
        reason_map = {
            'waiting_parts': 'Waiting for Parts',
            'waiting_approval': 'Waiting for Customer Approval',
            'waiting_qc': 'Waiting for QC',
            'assistance_required': 'Assistance Required',
            'tools_issue': 'Tool / Equipment Unavailable',
            'other': 'Other',
        }
        idle_map = {
            'training': '🎓 Training',
            'meeting': '👥 Meeting',
            'break_lunch': '☕ Break / Lunch',
        }
        for rec in self:
            if rec.status == 'idle' or rec.job_status == 'idle' or rec.idle_reason:
                rec.idle_reason_display = idle_map.get(rec.idle_reason, 'Idle')
                rec.pause_reason_display = '—'
            elif rec.status == 'completed' or rec.job_status == 'completed':
                if rec.pause_reason_id:
                    rec.pause_reason_display = rec.pause_reason_id.name
                elif rec.pause_reason and rec.pause_reason in reason_map:
                    rec.pause_reason_display = reason_map[rec.pause_reason]
                elif rec.pause_reason and rec.pause_reason not in ('—', False, 'Stop', 'Paused', '✅ Completed'):
                    rec.pause_reason_display = rec.pause_reason
                elif rec.status_log_id and rec.status_log_id.pause_reason_display:
                    rec.pause_reason_display = rec.status_log_id.pause_reason_display
                else:
                    rec.pause_reason_display = False
                rec.idle_reason_display = '—'
            elif rec.status == 'paused' or rec.job_status == 'paused':
                if rec.pause_reason_id:
                    rec.pause_reason_display = rec.pause_reason_id.name
                elif rec.pause_reason and rec.pause_reason in reason_map:
                    rec.pause_reason_display = reason_map[rec.pause_reason]
                elif rec.pause_reason and rec.pause_reason not in ('Stop', 'Paused', '—'):
                    rec.pause_reason_display = rec.pause_reason
                elif rec.status_log_id and rec.status_log_id.pause_reason_display:
                    rec.pause_reason_display = rec.status_log_id.pause_reason_display
                else:
                    slines = rec.service_line_ids
                    if not slines and rec.status_log_id:
                        slines = rec.status_log_id.service_line_ids
                    if not slines and rec.job_id:
                        slines = rec.job_id.service_line_ids.filtered(lambda l: not rec.employee_id or l.employee_id == rec.employee_id)
                    active_services = slines.filtered(lambda l: l.line_status != 'completed')
                    service_reasons = []
                    for sline in active_services:
                        s_r = (
                            (sline.service_idle_reason_id.name if sline.service_idle_reason_id else False)
                            or (sline.pause_reason_id.name if hasattr(sline, 'pause_reason_id') and sline.pause_reason_id else False)
                            or (reason_map.get(sline.pause_reason, sline.pause_reason) if sline.pause_reason else False)
                            or (sline.stop_reason if sline.stop_reason and sline.stop_reason not in ('Stop', 'Paused', '—') else False)
                        )
                        if s_r:
                            service_reasons.append(s_r.strip())
                    if active_services and len(service_reasons) == len(active_services):
                        unique_reasons = {r.lower(): r for r in service_reasons}
                        if len(unique_reasons) > 1:
                            rec.pause_reason_display = 'Other'
                        elif len(unique_reasons) == 1:
                            rec.pause_reason_display = list(unique_reasons.values())[0]
                        else:
                            rec.pause_reason_display = False
                    else:
                        rec.pause_reason_display = False
                rec.idle_reason_display = '—'
            else:
                if rec.pause_reason_id:
                    rec.pause_reason_display = rec.pause_reason_id.name
                elif rec.pause_reason and rec.pause_reason in reason_map:
                    rec.pause_reason_display = reason_map[rec.pause_reason]
                elif rec.status_log_id and rec.status_log_id.pause_reason_display:
                    rec.pause_reason_display = rec.status_log_id.pause_reason_display
                else:
                    rec.pause_reason_display = False
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
    vin_sn = fields.Char(
        string='Chassis Number',
        related='job_id.vin_sn',
        store=True,
        readonly=True,
    )
    kilometers_num = fields.Char(
        string='KMS',
        related='job_id.kilometers_num',
        store=True,
        readonly=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='employee_id.department_id',
        store=True,
        readonly=True,
    )
    service_line_ids = fields.Many2many(
        'fleet.repair.service.line',
        string='Service Tasks',
        compute='_compute_service_line_ids',
    )
    worked_hours = fields.Float(
        string='Worked Hours',
        compute='_compute_worked_hours',
        store=True,
        digits=(16, 2),
    )
    pause_duration = fields.Float(
        string='Pause Duration',
        compute='_compute_pause_duration',
        store=True,
        digits=(16, 2),
    )
    has_paused_services = fields.Boolean(
        string='Has Paused Services',
        compute='_compute_has_paused_services',
    )
    collective_duration = fields.Float(
        string='Working Duration',
        compute='_compute_collective_duration',
    )
    is_collective_timer_running = fields.Boolean(string='Working Timer Running', default=False)
    is_pause_running = fields.Boolean(string='Pause Running', default=False)
    is_timer_running = fields.Boolean(string='Timer Running', default=False)
    collective_selected_count = fields.Integer(string='Selected Count', default=0)
    collective_timer_last_start = fields.Datetime(string='Working Last Start')
    collective_accumulated_seconds = fields.Float(string='Working Accumulated Seconds', default=0.0)
    collective_target_hours = fields.Float(string='Target Hours', default=0.0)
    collective_target_seconds = fields.Float(string='Target Seconds', default=0.0)
    collective_remaining_seconds = fields.Float(string='Collective Remaining Seconds', default=0.0)
    timer_mode = fields.Selection([
        ('countdown', 'Countdown'),
        ('stopwatch', 'Stopwatch'),
    ], string='Timer Mode', default='stopwatch')
    pause_timer_start = fields.Datetime(string='Pause Timer Start')
    timer_start = fields.Datetime(string='Timer Start', compute='_compute_timer_aliases', store=True, readonly=False)
    timer_last_start = fields.Datetime(string='Timer Last Start')
    timer_end = fields.Datetime(string='Timer End', compute='_compute_timer_aliases', store=True, readonly=False)
    is_timer_paused = fields.Boolean(string='Is Timer Paused', default=False)
    alloted_fru = fields.Integer(string='Alloted FRU', default=0)
    time_diff = fields.Float(string='Duration', compute='_compute_time_diff')
    product_id = fields.Many2one('product.product', string='Service', related='service_line_id.product_id', store=True, readonly=True)

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

    @api.depends('job_id', 'job_id.service_line_ids', 'service_line_id', 'status_log_id', 'employee_id')
    def _compute_service_line_ids(self):
        for rec in self:
            lines = self.env['fleet.repair.service.line']
            if rec.status_log_id and rec.status_log_id.service_line_ids:
                lines = rec.status_log_id.service_line_ids
            elif rec.job_id and rec.employee_id:
                lines = rec.job_id.service_line_ids.filtered(
                    lambda l: l.employee_id == rec.employee_id or (rec.status_log_id and l.status_log_id == rec.status_log_id)
                )
                if not lines:
                    lines = rec.job_id.service_line_ids
            elif rec.job_id:
                lines = rec.job_id.service_line_ids
            elif rec.service_line_id:
                lines = rec.service_line_id
            rec.service_line_ids = lines

    @api.depends('accumulated_seconds', 'duration')
    def _compute_worked_hours(self):
        for rec in self:
            if rec.accumulated_seconds:
                rec.worked_hours = round(rec.accumulated_seconds / 3600.0, 2)
            elif rec.service_line_ids:
                s_hours = sum(l.hours or (l.accumulated_seconds / 3600.0 if l.accumulated_seconds else 0.0) for l in rec.service_line_ids)
                rec.worked_hours = round(s_hours, 2)
            else:
                rec.worked_hours = round(rec.duration or 0.0, 2)

    @api.depends('pause_accumulated_seconds')
    def _compute_pause_duration(self):
        for rec in self:
            if rec.pause_accumulated_seconds:
                rec.pause_duration = round(rec.pause_accumulated_seconds / 3600.0, 2)
            elif rec.service_line_ids:
                p_sec = sum(l.pause_accumulated_seconds or 0.0 for l in rec.service_line_ids)
                rec.pause_duration = round(p_sec / 3600.0, 2)
            else:
                rec.pause_duration = 0.0

    @api.depends('pause_reason', 'pause_duration')
    def _compute_has_paused_services(self):
        for rec in self:
            rec.has_paused_services = bool(
                rec.pause_reason or
                (rec.pause_duration and rec.pause_duration > 0) or
                any(l.line_status == 'paused' for l in rec.service_line_ids)
            )

    @api.depends('worked_hours', 'accumulated_seconds')
    def _compute_collective_duration(self):
        for rec in self:
            rec.collective_duration = rec.worked_hours or (rec.accumulated_seconds / 3600.0 if rec.accumulated_seconds else 0.0)

    @api.depends('start_datetime', 'end_datetime')
    def _compute_timer_aliases(self):
        for rec in self:
            rec.timer_start = rec.start_datetime or False
            rec.timer_end = rec.end_datetime or False

    @api.depends('duration', 'worked_hours')
    def _compute_time_diff(self):
        for rec in self:
            rec.time_diff = rec.worked_hours or rec.duration or 0.0

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
        """Creates a timeline history record for the employee.
        Timeline history strictly only stores 'completed' and 'idle' records."""
        now = fields.Datetime.now()
        emp_id = employee_id.id if hasattr(employee_id, 'id') else employee_id
        if not emp_id:
            return False

        job_status = vals.get('job_status')
        # Strictly restrict timeline history to only idle and completed
        if status not in ('idle', 'completed') and job_status not in ('idle', 'completed'):
            return False

        job_id = vals.get('job_id') or False
        if hasattr(job_id, 'id'):
            job_id = job_id.id

        # Prevent duplicate completed records for the same employee and job card
        if job_id and (status == 'completed' or job_status == 'completed'):
            existing_completed = self.search([
                ('employee_id', '=', emp_id),
                ('job_id', '=', job_id),
                '|', ('status', '=', 'completed'), ('job_status', '=', 'completed'),
            ], order='accumulated_seconds desc, id desc', limit=1)
            if existing_completed:
                update_vals = {
                    'status': 'completed',
                    'job_status': 'completed',
                    'end_datetime': vals.get('end_datetime') or now,
                }
                new_acc = vals.get('accumulated_seconds') or 0.0
                if new_acc > (existing_completed.accumulated_seconds or 0.0):
                    update_vals['accumulated_seconds'] = new_acc
                new_pause = vals.get('pause_accumulated_seconds') or 0.0
                if new_pause > (existing_completed.pause_accumulated_seconds or 0.0):
                    update_vals['pause_accumulated_seconds'] = new_pause
                if vals.get('notes'):
                    update_vals['notes'] = vals.get('notes')
                if vals.get('status_log_id') and not existing_completed.status_log_id:
                    update_vals['status_log_id'] = vals.get('status_log_id')
                if vals.get('service_name') and not existing_completed.service_name:
                    update_vals['service_name'] = vals.get('service_name')
                if vals.get('start_datetime') and (not existing_completed.start_datetime or vals['start_datetime'] < existing_completed.start_datetime):
                    update_vals['start_datetime'] = vals['start_datetime']
                existing_completed.write(update_vals)
                return existing_completed

        # Check if an open timeline record already exists for this employee
        open_prev = self.search([
            ('employee_id', '=', emp_id),
            ('end_datetime', '=', False),
        ], order='id desc')

        # If an open idle record already matches, update it instead of creating a duplicate
        if status == 'idle' or job_status == 'idle':
            matching_open = open_prev.filtered(lambda r: r.status == 'idle' or r.job_status == 'idle')
            if matching_open:
                target = matching_open[0]
                update_vals = {}
                if vals.get('idle_reason') and target.idle_reason != vals.get('idle_reason'):
                    update_vals['idle_reason'] = vals.get('idle_reason')
                if vals.get('notes') and target.notes != vals.get('notes'):
                    update_vals['notes'] = vals.get('notes')
                if vals.get('accumulated_seconds'):
                    update_vals['accumulated_seconds'] = vals.get('accumulated_seconds')
                if update_vals:
                    target.write(update_vals)
                return target

        # Close any open previous timeline record for this employee
        for prev in open_prev:
            prev.write({
                'end_datetime': now,
            })

        log_vals = {
            'employee_id': emp_id,
            'status': status,
            'job_status': job_status or status,
            'start_datetime': vals.get('start_datetime') or now,
            'end_datetime': vals.get('end_datetime') or False,
            'job_id': job_id,
            'service_line_id': vals.get('service_line_id') or False,
            'service_name': vals.get('service_name') or False,
            'pause_reason': vals.get('pause_reason') or False,
            'pause_reason_id': vals.get('pause_reason_id') or False,
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
        # 1. Clean up any records from employee timeline history that are neither completed nor idle
        self.env.cr.execute("""
            DELETE FROM employee_timeline_history 
            WHERE (status IS NULL OR status NOT IN ('idle', 'completed'))
              AND (job_status IS NULL OR job_status NOT IN ('idle', 'completed'));
        """)
        # 2. Fix records that have idle_reason set but status was not idle
        self.env.cr.execute("""
            UPDATE employee_timeline_history
            SET status = 'idle', job_status = 'idle'
            WHERE idle_reason IS NOT NULL AND status != 'idle';
        """)
        # 3. Deduplicate completed job records: keep only 1 record per (employee_id, job_id)
        self.env.cr.execute("""
            DELETE FROM employee_timeline_history
            WHERE id NOT IN (
                SELECT DISTINCT ON (employee_id, job_id) id
                FROM employee_timeline_history
                WHERE job_id IS NOT NULL AND (status = 'completed' OR job_status = 'completed')
                ORDER BY employee_id, job_id, accumulated_seconds DESC, id DESC
            )
            AND job_id IS NOT NULL AND (status = 'completed' OR job_status = 'completed');
        """)
        # 4. Deduplicate idle records: keep only 1 record per (employee_id, start_datetime)
        self.env.cr.execute("""
            DELETE FROM employee_timeline_history
            WHERE id NOT IN (
                SELECT DISTINCT ON (employee_id, start_datetime) id
                FROM employee_timeline_history
                WHERE status = 'idle'
                ORDER BY employee_id, start_datetime, id DESC
            )
            AND status = 'idle';
        """)
        # 5. Seed missing completed status logs from hr_employee_status_log (strictly 1 per employee and job)
        self.env.cr.execute("""
            INSERT INTO employee_timeline_history (
                employee_id, status, job_status, pause_reason, pause_notes, idle_reason, notes,
                job_id, service_line_id, start_datetime, end_datetime,
                accumulated_seconds, pause_accumulated_seconds, status_log_id, create_date, write_date
            )
            SELECT DISTINCT ON (l.employee_id, l.job_id)
                l.employee_id,
                'completed',
                'completed',
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
            WHERE (l.job_status = 'completed' OR l.status = 'completed')
              AND l.job_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM employee_timeline_history eth 
                  WHERE eth.employee_id = l.employee_id AND eth.job_id = l.job_id
              )
            ORDER BY l.employee_id, l.job_id, l.accumulated_seconds DESC, l.id DESC;
        """)
        # 6. Seed missing idle logs
        self.env.cr.execute("""
            INSERT INTO employee_timeline_history (
                employee_id, status, job_status, pause_reason, pause_notes, idle_reason, notes,
                job_id, service_line_id, start_datetime, end_datetime,
                accumulated_seconds, pause_accumulated_seconds, status_log_id, create_date, write_date
            )
            SELECT 
                l.employee_id,
                'idle',
                'idle',
                l.pause_reason,
                l.pause_notes,
                COALESCE(l.idle_reason, 'no_job'),
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
            WHERE (l.status = 'idle' OR l.job_status = 'idle')
              AND NOT EXISTS (
                  SELECT 1 FROM employee_timeline_history eth 
                  WHERE eth.employee_id = l.employee_id 
                    AND eth.status = 'idle' 
                    AND eth.start_datetime = l.start_datetime
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
