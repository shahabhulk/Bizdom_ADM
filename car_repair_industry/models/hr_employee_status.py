# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    work_status = fields.Selection([
        ('job', 'Active Job'),
        ('assigned', 'Assigned'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('waiting_car', 'Waiting for Car'),
        ('parts_unavailable', 'Parts Arrival / Not Available'),
        ('tools_issue', 'Tools Issue'),
        ('approval_pending', 'Customer Approval Pending'),
        ('idle', 'Idle')
    ], string='Current Status', default='idle', tracking=True)

    current_status_start = fields.Datetime(string='Status Start Time')
    has_active_status_log = fields.Boolean(
        string='Has Active Status Log',
        compute='_compute_active_status_log'
    )
    current_job_id = fields.Many2one('fleet.repair', string='Current Job Card')
    current_license_plate = fields.Many2one(
        'fleet.vehicle',
        string='Licence No',
        related='current_job_id.license_plate',
        store=True,
        readonly=True
    )
    current_service_line_id = fields.Many2one('fleet.repair.service.line', string='Current Service Line')
    current_status_duration = fields.Float(
        string='Status Duration (Hours)',
        compute='_compute_current_status_duration'
    )
    status_notes = fields.Char(string='Status Notes')
    status_log_ids = fields.One2many(
        'hr.employee.status.log', 'employee_id', string='Status History'
    )
    service_line_ids = fields.One2many(
        'fleet.repair.service.line', 'employee_id', string='Assigned Services'
    )

    # Active Service Timer Fields for Employee Kanban
    has_active_service_timer = fields.Boolean(
        string='Has Active Service Timer',
        compute='_compute_active_service_timer_info'
    )
    active_timer_last_start = fields.Datetime(
        string='Active Timer Last Start',
        compute='_compute_active_service_timer_info'
    )
    active_timer_accumulated_seconds = fields.Float(
        string='Active Accumulated Seconds',
        compute='_compute_active_service_timer_info'
    )
    active_service_time_diff = fields.Float(
        string='Active Duration (Hours)',
        compute='_compute_active_service_timer_info'
    )
    active_service_name = fields.Char(
        string='Active Service Name',
        compute='_compute_active_service_timer_info'
    )
    active_timer_fru_status = fields.Selection(
        [('green', 'Normal'), ('yellow', 'Warning'), ('red', 'Overtime')],
        string='Active Timer FRU Status',
        compute='_compute_active_service_timer_info',
        default='green'
    )
    current_pause_reason = fields.Selection([
        ('waiting_parts', 'Waiting for Parts'),
        ('waiting_approval', 'Waiting for Approval'),
        ('waiting_qc', 'Waiting for QC'),
        ('assistance_required', 'Assistance Required'),
        ('tools_issue', 'Tool / Equipment Unavailable'),
        ('other', 'Other'),
    ], string='Current Pause Reason', compute='_compute_active_service_timer_info')
    current_car_model = fields.Char(string='Current Car Model', compute='_compute_active_service_timer_info')
    current_pause_time_display = fields.Char(string='Current Pause Time', compute='_compute_active_service_timer_info')
    current_pause_duration = fields.Float(string='Current Pause Duration (Hours)', compute='_compute_active_service_timer_info')
    pause_timer_start = fields.Datetime(string='Pause Timer Start', compute='_compute_active_service_timer_info')
    pause_accumulated_seconds = fields.Float(string='Pause Accumulated Seconds', compute='_compute_active_service_timer_info')
    is_pause_running = fields.Boolean(string='Is Pause Running', compute='_compute_active_service_timer_info')
    current_job_name = fields.Char(string='Current Job Card Name', compute='_compute_active_service_timer_info')
    current_job_card_label = fields.Char(string='Job Card Label', compute='_compute_active_service_timer_info')
    current_car_display = fields.Char(string='Current Car Display', compute='_compute_active_service_timer_info')
    current_pause_icon = fields.Char(string='Pause Icon', compute='_compute_active_service_timer_info')

    # Safe alias / fallback fields for any widgets querying timer fields on employee
    timer_start = fields.Datetime(string='Timer Start', compute='_compute_active_service_timer_info')
    timer_last_start = fields.Datetime(string='Timer Last Start', compute='_compute_active_service_timer_info')
    timer_end = fields.Datetime(string='Timer End', compute='_compute_active_service_timer_info')
    is_timer_running = fields.Boolean(string='Is Timer Running', compute='_compute_active_service_timer_info')
    is_timer_paused = fields.Boolean(string='Is Timer Paused', compute='_compute_active_service_timer_info')
    accumulated_seconds = fields.Float(string='Accumulated Seconds', compute='_compute_active_service_timer_info')
    alloted_fru = fields.Integer(string='Alloted FRU', compute='_compute_active_service_timer_info')

    # Idle Status & Timer Tracking
    idle_reason = fields.Selection([
        ('training', 'Training'),
        ('learning', 'Learning'),
        ('meeting', 'Meeting'),
        ('break_lunch', 'Break / Lunch'),
    ], string='Idle Reason', tracking=True)
    is_idle_running = fields.Boolean(string='Is Idle Timer Running', default=False)
    idle_timer_start = fields.Datetime(string='Idle Timer Start')
    idle_accumulated_seconds = fields.Float(string='Idle Accumulated Seconds', default=0.0)
    idle_duration = fields.Float(string='Idle Duration (Hours)', compute='_compute_idle_duration')
    idle_reason_display = fields.Char(string='Idle Reason Display', compute='_compute_idle_reason_display')

    @api.depends('is_idle_running', 'idle_timer_start', 'idle_accumulated_seconds', 'work_status')
    def _compute_idle_duration(self):
        now = fields.Datetime.now()
        for emp in self:
            if emp.work_status == 'idle' or emp.is_idle_running:
                total_sec = emp.idle_accumulated_seconds or 0.0
                if emp.is_idle_running and emp.idle_timer_start:
                    delta = now - emp.idle_timer_start
                    total_sec += max(0, delta.total_seconds())
                emp.idle_duration = total_sec / 3600.0
            else:
                emp.idle_duration = 0.0

    @api.depends('idle_reason')
    def _compute_idle_reason_display(self):
        reason_map = {
            'training': '🎓 Training',
            'learning': '📚 Learning',
            'meeting': '👥 Meeting',
            'break_lunch': '☕ Break / Lunch',
        }
        for emp in self:
            emp.idle_reason_display = reason_map.get(emp.idle_reason, 'Idle')

    @api.depends(
        'work_status',
        'current_pause_reason',
        'service_line_ids.is_timer_running',
        'service_line_ids.accumulated_seconds',
        'service_line_ids.timer_last_start',
        'status_log_ids.pause_reason',
        'status_log_ids.job_status',
        'status_log_ids.status',
        'status_log_ids.is_timer_running',
        'status_log_ids.is_pause_running',
        'status_log_ids.pause_timer_start',
        'status_log_ids.pause_accumulated_seconds',
        'is_idle_running',
        'idle_reason'
    )
    def _compute_active_service_timer_info(self):
        for emp in self:
            running_lines = self.env['fleet.repair.service.line'].search([
                ('employee_id', '=', emp.id),
                ('is_timer_running', '=', True),
                ('repair_id.state', 'not in', ['done', 'invoiced', 'cancel'])
            ], order='timer_last_start desc, id desc')

            paused_lines = self.env['fleet.repair.service.line'].search([
                ('employee_id', '=', emp.id),
                ('is_timer_paused', '=', True),
                ('repair_id.state', 'not in', ['done', 'invoiced', 'cancel'])
            ], order='timer_end desc, id desc')

            assigned_lines = self.env['fleet.repair.service.line'].search([
                ('employee_id', '=', emp.id),
                ('repair_id.state', 'not in', ['done', 'invoiced', 'cancel'])
            ], order='write_date desc, id desc')

            completed_logs = self.env['hr.employee.status.log'].search([
                ('employee_id', '=', emp.id),
                ('job_status', '=', 'completed')
            ], order='end_datetime desc, write_date desc, id desc')
            completed_sline_ids = set()
            for clog in completed_logs:
                completed_sline_ids.update(clog.service_line_ids.ids)

            pending_assigned_lines = assigned_lines.filtered(
                lambda l: l.id not in completed_sline_ids and (not l.status_log_id or l.status_log_id.job_status != 'completed')
            )

            # Auto-reconcile assigned work status if employee has assigned work on open job cards
            if not running_lines and not paused_lines and pending_assigned_lines and not emp.is_idle_running and emp.work_status in ('idle', False):
                emp.work_status = 'assigned'
                if not emp.current_job_id:
                    emp.current_job_id = pending_assigned_lines[0].repair_id
                if not emp.current_service_line_id:
                    emp.current_service_line_id = pending_assigned_lines[0]
            elif not running_lines and not paused_lines and not pending_assigned_lines and not emp.is_idle_running:
                latest_log = emp.status_log_ids and emp.status_log_ids[0]
                if emp.work_status == 'completed' or (latest_log and latest_log.job_status == 'completed'):
                    emp.work_status = 'completed'

            if running_lines:
                rline = running_lines[0]
                emp.has_active_service_timer = True
                emp.active_timer_last_start = rline.timer_last_start
                emp.active_timer_accumulated_seconds = rline.accumulated_seconds or 0.0
                emp.active_service_time_diff = rline.time_diff or 0.0
                emp.active_service_name = rline.product_id.name if rline.product_id else (rline.name or '')
                emp.active_timer_fru_status = rline.fru_status or 'green'
                emp.current_pause_reason = False
                emp.timer_start = rline.timer_start
                emp.timer_last_start = rline.timer_last_start
                emp.timer_end = rline.timer_end
                emp.is_timer_running = True
                emp.is_timer_paused = False
                emp.accumulated_seconds = rline.accumulated_seconds or 0.0
                emp.alloted_fru = rline.alloted_fru or 0
                if not emp.current_job_id and rline.repair_id:
                    emp.current_job_id = rline.repair_id
                emp.pause_timer_start = False
                emp.pause_accumulated_seconds = 0.0
                emp.is_pause_running = False
                emp.current_pause_duration = 0.0
                emp.current_pause_time_display = '00:00:00'
            elif emp.work_status == 'completed':
                emp.has_active_service_timer = False
                emp.active_timer_last_start = False
                emp.is_timer_running = False
                emp.is_timer_paused = False
                emp.is_pause_running = False
                emp.current_pause_reason = False
                emp.current_pause_icon = False
                emp.pause_timer_start = False
                emp.pause_accumulated_seconds = 0.0
                emp.current_pause_duration = 0.0
                emp.current_pause_time_display = '00:00:00'
                emp.active_timer_fru_status = 'green'

                clog = completed_logs[0] if completed_logs else False
                if clog:
                    target_job = clog.job_id
                    target_sline = clog.service_line_ids[0] if clog.service_line_ids else emp.current_service_line_id
                    acc_sec = clog.accumulated_seconds or 0.0
                    emp.active_timer_accumulated_seconds = acc_sec
                    emp.active_service_time_diff = acc_sec / 3600.0
                    emp.accumulated_seconds = acc_sec
                    emp.alloted_fru = target_sline.alloted_fru if target_sline else 0
                    if target_job:
                        emp.current_job_id = target_job
                    if target_sline:
                        emp.current_service_line_id = target_sline
                        emp.active_service_name = target_sline.product_id.name if target_sline.product_id else (target_sline.name or '')
                else:
                    emp.active_timer_accumulated_seconds = 0.0
                    emp.active_service_time_diff = 0.0
                    emp.accumulated_seconds = 0.0
            elif emp.work_status == 'idle' and (not pending_assigned_lines or emp.is_idle_running):
                emp.has_active_service_timer = False
                emp.active_timer_last_start = False
                emp.is_timer_running = False
                emp.active_timer_accumulated_seconds = 0.0
                emp.active_service_time_diff = 0.0
                emp.active_service_name = False
                emp.active_timer_fru_status = 'green'
                emp.timer_start = False
                emp.timer_last_start = False
                emp.timer_end = False
                emp.is_timer_paused = False
                emp.accumulated_seconds = 0.0
                emp.alloted_fru = 0
                emp.current_job_name = False
                emp.current_job_card_label = False
                emp.current_car_model = False
                emp.current_car_display = False
                emp.current_pause_reason = False
                emp.current_pause_icon = False
                emp.pause_timer_start = False
                emp.pause_accumulated_seconds = 0.0
                emp.is_pause_running = False
                emp.current_pause_duration = 0.0
                emp.current_pause_time_display = '00:00:00'
                continue
            else:
                emp.has_active_service_timer = False
                emp.active_timer_last_start = False
                emp.is_timer_running = False
                # If assigned, paused or stopped on a job, retain the service line's accumulated duration & name
                target_sline = emp.current_service_line_id
                if not target_sline or not target_sline.exists():
                    if pending_assigned_lines:
                        target_sline = pending_assigned_lines[0]
                    elif assigned_lines:
                        target_sline = assigned_lines[0]
                if target_sline and target_sline.exists():
                    emp.active_timer_accumulated_seconds = target_sline.accumulated_seconds or 0.0
                    emp.active_service_time_diff = target_sline.time_diff or 0.0
                    emp.active_service_name = target_sline.product_id.name if target_sline.product_id else (target_sline.name or '')
                    emp.active_timer_fru_status = target_sline.fru_status or 'green'
                    emp.timer_start = target_sline.timer_start
                    emp.timer_last_start = target_sline.timer_last_start
                    emp.timer_end = target_sline.timer_end
                    emp.is_timer_paused = target_sline.is_timer_paused
                    emp.accumulated_seconds = target_sline.accumulated_seconds or 0.0
                    emp.alloted_fru = target_sline.alloted_fru or 0
                    if not emp.current_job_id and target_sline.repair_id:
                        emp.current_job_id = target_sline.repair_id
                else:
                    emp.active_timer_accumulated_seconds = 0.0
                    emp.active_service_time_diff = 0.0
                    emp.active_service_name = False
                    emp.active_timer_fru_status = 'green'
                    emp.timer_start = False
                    emp.timer_last_start = False
                    emp.timer_end = False
                    emp.is_timer_paused = False
                    emp.accumulated_seconds = 0.0
                    emp.alloted_fru = 0

                latest_log = self.env['hr.employee.status.log'].search([
                    ('employee_id', '=', emp.id),
                    ('job_id', '!=', False),
                    ('end_datetime', '=', False),
                ], order='write_date desc, id desc', limit=1)
                if latest_log:
                    if latest_log.pause_reason:
                        emp.current_pause_reason = latest_log.pause_reason
                    else:
                        emp.current_pause_reason = False
                    if not emp.current_job_id and latest_log.job_id:
                        emp.current_job_id = latest_log.job_id
                else:
                    emp.current_pause_reason = False

            # Model, Job Name & Pause Time metrics for Kanban
            if emp.current_job_id:
                jc_num = emp.current_job_id.sequence or emp.current_job_id.name or str(emp.current_job_id.id)
                emp.current_job_name = f"#{jc_num}"
                emp.current_job_card_label = f"Job Card: #{jc_num}"
                brand = emp.current_job_id.fleet_id.name if emp.current_job_id.fleet_id else ''
                model = emp.current_job_id.model_name.name if emp.current_job_id.model_name else ''
                car_model = f"{brand} {model}".strip() if (brand and model and brand.lower() not in model.lower()) else (model or brand)
                emp.current_car_model = car_model
                plate = emp.current_job_id.license_plate.license_plate if emp.current_job_id.license_plate else (emp.current_license_plate or '')
                if plate and car_model:
                    emp.current_car_display = f"{plate} - {car_model}"
                elif plate:
                    emp.current_car_display = plate
                elif car_model:
                    emp.current_car_display = car_model
                else:
                    emp.current_car_display = ''

                if not emp.active_service_name:
                    emp_slines = emp.current_job_id.service_line_ids.filtered(lambda l: l.employee_id.id == emp.id)
                    if emp_slines:
                        emp.active_service_name = emp_slines[0].product_id.name if emp_slines[0].product_id else (emp_slines[0].name or '')
                    elif emp.current_job_id.service_line_ids:
                        emp.active_service_name = emp.current_job_id.service_line_ids[0].product_id.name if emp.current_job_id.service_line_ids[0].product_id else (emp.current_job_id.service_line_ids[0].name or '')
            else:
                emp.current_job_name = ''
                emp.current_job_card_label = ''
                emp.current_car_model = ''
                emp.current_car_display = emp.current_license_plate or ''

            # Pause Icon
            if emp.current_pause_reason == 'waiting_parts':
                emp.current_pause_icon = '📦'
            elif emp.current_pause_reason == 'waiting_approval':
                emp.current_pause_icon = '📄'
            elif emp.current_pause_reason == 'tools_issue':
                emp.current_pause_icon = '🛠'
            elif emp.current_pause_reason == 'waiting_qc':
                emp.current_pause_icon = '🟣'
            elif emp.current_pause_reason == 'assistance_required':
                emp.current_pause_icon = '🟠'
            else:
                emp.current_pause_icon = ''

            paused_logs = emp.status_log_ids.filtered(
                lambda l: (l.job_status == 'paused' or l.status == 'paused' or bool(l.pause_reason)) and not l.end_datetime
            )
            if not paused_logs:
                paused_logs = emp.status_log_ids.filtered(
                    lambda l: l.job_status == 'paused' or l.status == 'paused' or bool(l.pause_reason)
                )

            is_paused = (emp.work_status == 'paused' or bool(emp.current_pause_reason)) and bool(paused_logs)
            if is_paused:
                plog = paused_logs[0]
                pause_start = plog.pause_timer_start
                pause_accum = plog.pause_accumulated_seconds or 0.0

                if not pause_start:
                    if plog.timer_end:
                        pause_start = plog.timer_end
                    elif plog.start_datetime:
                        pause_start = plog.start_datetime + timedelta(seconds=(plog.accumulated_seconds or 0.0))
                    else:
                        pause_start = plog.write_date or plog.create_date or fields.Datetime.now()

                emp.pause_timer_start = pause_start
                emp.pause_accumulated_seconds = pause_accum
                emp.is_pause_running = True

                now = fields.Datetime.now()
                total_pause_sec = pause_accum + max(0, (now - pause_start).total_seconds()) if pause_start else 0.0
                emp.current_pause_duration = total_pause_sec / 3600.0
                s = max(0, int(round(total_pause_sec)))
                emp.current_pause_time_display = f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"
            elif emp.work_status == 'paused':
                pause_start = emp.current_status_start or fields.Datetime.now()
                emp.pause_timer_start = pause_start
                emp.pause_accumulated_seconds = 0.0
                emp.is_pause_running = True
                now = fields.Datetime.now()
                total_pause_sec = max(0, (now - pause_start).total_seconds())
                emp.current_pause_duration = total_pause_sec / 3600.0
                s = max(0, int(round(total_pause_sec)))
                emp.current_pause_time_display = f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"
            else:
                emp.pause_timer_start = False
                emp.pause_accumulated_seconds = 0.0
                emp.is_pause_running = False
                emp.current_pause_duration = 0.0
                emp.current_pause_time_display = '00:00:00'

    is_my_team = fields.Boolean(
        string='Is in My Team',
        compute='_compute_is_my_team',
        search='_search_is_my_team'
    )

    def _compute_is_my_team(self):
        user = self.env.user
        admin_users = self.env['res.users'].sudo().search(['|', ('login', '=', 'admin'), ('id', '=', 2)])
        admin_user_ids = set(admin_users.ids)
        admin_emps = self.env['hr.employee'].sudo().search([
            '|', '|',
            ('user_id', 'in', admin_users.ids),
            ('name', '=ilike', 'administrator'),
            ('name', '=ilike', 'admin')
        ])
        admin_emp_ids = set(admin_emps.ids)

        service_mgr_group = self.env.ref('car_repair_industry.group_fleet_repair_service_manager', raise_if_not_found=False)
        commercial_dir_group = self.env.ref('car_repair_industry.group_fleet_repair_directeur_commercial', raise_if_not_found=False)
        mgr_group_ids = [g.id for g in (service_mgr_group, commercial_dir_group) if g]
        manager_users = self.env['res.users'].sudo().search([('groups_id', 'in', mgr_group_ids)]) if mgr_group_ids else self.env['res.users']

        all_emps_sudo = self.env['hr.employee'].sudo().search([])
        manager_parents = all_emps_sudo.mapped('parent_id')
        dept_managers = self.env['hr.department'].sudo().search([]).mapped('manager_id')
        job_managers = all_emps_sudo.filtered(lambda e: (e.job_title and 'manager' in e.job_title.lower()) or (e.name and 'manager' in e.name.lower()))
        group_managers = all_emps_sudo.filtered(lambda e: e.user_id and e.user_id.id in manager_users.ids)

        all_managers = manager_parents | dept_managers | job_managers | group_managers
        manager_emp_ids = set(all_managers.ids)

        current_emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        current_emp_id = current_emp.id if current_emp else False

        for emp in self:
            # Exclude administrator
            if (
                emp.id in admin_emp_ids or
                (emp.user_id and emp.user_id.id in admin_user_ids) or
                (emp.name and emp.name.strip().lower() in ('administrator', 'admin'))
            ):
                emp.is_my_team = False
            # Exclude manager
            elif emp.id in manager_emp_ids or (emp.job_title and 'manager' in emp.job_title.lower()):
                emp.is_my_team = False
            # Exclude himself
            elif (current_emp_id and emp.id == current_emp_id) or (emp.user_id and emp.user_id.id == user.id):
                emp.is_my_team = False
            else:
                emp.is_my_team = True

    def _search_is_my_team(self, operator, value):
        user = self.env.user
        admin_users = self.env['res.users'].sudo().search(['|', ('login', '=', 'admin'), ('id', '=', 2)])
        admin_emps = self.env['hr.employee'].sudo().search([
            '|', '|',
            ('user_id', 'in', admin_users.ids),
            ('name', '=ilike', 'administrator'),
            ('name', '=ilike', 'admin')
        ])

        service_mgr_group = self.env.ref('car_repair_industry.group_fleet_repair_service_manager', raise_if_not_found=False)
        commercial_dir_group = self.env.ref('car_repair_industry.group_fleet_repair_directeur_commercial', raise_if_not_found=False)
        mgr_group_ids = [g.id for g in (service_mgr_group, commercial_dir_group) if g]
        manager_users = self.env['res.users'].sudo().search([('groups_id', 'in', mgr_group_ids)]) if mgr_group_ids else self.env['res.users']

        all_emps_sudo = self.env['hr.employee'].sudo().search([])
        manager_parents = all_emps_sudo.mapped('parent_id')
        dept_managers = self.env['hr.department'].sudo().search([]).mapped('manager_id')
        job_managers = all_emps_sudo.filtered(lambda e: (e.job_title and 'manager' in e.job_title.lower()) or (e.name and 'manager' in e.name.lower()))
        group_managers = all_emps_sudo.filtered(lambda e: e.user_id and e.user_id.id in manager_users.ids)

        all_managers = manager_parents | dept_managers | job_managers | group_managers

        current_emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)])

        excluded_emps = admin_emps | all_managers | current_emp
        domain = [('id', 'not in', excluded_emps.ids)] if excluded_emps else [(1, '=', 1)]

        positive = (operator in ('=', '==', 'ilike', 'like') and bool(value)) or (operator in ('!=', '<>') and not value)
        return domain if positive else ['!'] + domain

    @api.depends('status_log_ids.is_timer_running', 'status_log_ids.end_datetime', 'work_status')
    def _compute_active_status_log(self):
        for emp in self:
            open_running_log = self.env['hr.employee.status.log'].search([
                ('employee_id', '=', emp.id),
                ('end_datetime', '=', False),
                ('is_timer_running', '=', True),
            ], limit=1)
            emp.has_active_status_log = bool(open_running_log)

    @api.depends('current_status_start', 'work_status', 'has_active_status_log', 'is_idle_running')
    def _compute_current_status_duration(self):
        now = fields.Datetime.now()
        for emp in self:
            if (emp.has_active_status_log or emp.is_idle_running) and emp.current_status_start:
                delta = now - emp.current_status_start
                emp.current_status_duration = round(delta.total_seconds() / 3600.0, 2)
            else:
                emp.current_status_duration = 0.0

    def action_set_status(self, new_status, job_id=False, service_line_id=False, product_id=False, notes=False):
        """Changes the employee's work status, closes open log, and starts a new status log."""
        now = fields.Datetime.now()
        for emp in self:
            # 1. Close open log record that is currently active/running
            open_logs = self.env['hr.employee.status.log'].search([
                ('employee_id', '=', emp.id),
                ('end_datetime', '=', False),
                '|', ('is_timer_running', '=', True), ('status', '!=', 'job')
            ])
            if service_line_id:
                open_logs = open_logs.filtered(lambda l: not l.service_line_id or l.service_line_id.id != service_line_id)
            for log in open_logs:
                log.end_datetime = now
                if log.is_timer_running:
                    if log.timer_last_start:
                        delta = now - log.timer_last_start
                        log.accumulated_seconds += delta.total_seconds()
                    log.timer_last_start = False
                    log.timer_end = now
                    log.is_timer_running = False
                    log.is_timer_paused = False
                    log._compute_time_diff()
                    log._compute_duration()

            # If moving away from 'job', pause any running service timers for this employee
            if new_status != 'job':
                running_lines = self.env['fleet.repair.service.line'].search([
                    ('employee_id', '=', emp.id),
                    ('is_timer_running', '=', True),
                ])
                for line in running_lines:
                    line.with_context(skip_status_wizard=True).action_pause_timer()
            else:
                # Rule: If assigning active job, check if other previous work is live and running
                domain = [
                    ('employee_id', '=', emp.id),
                    ('is_timer_running', '=', True),
                    ('repair_id.state', 'not in', ['done', 'invoiced', 'cancel'])
                ]
                if service_line_id:
                    domain.append(('id', '!=', service_line_id))
                running_lines = self.env['fleet.repair.service.line'].search(domain)
                if running_lines:
                    raise ValidationError(_("Let the previous work be over since its live and timer is running! Please pause the current timer first before assigning a new job."))

            # Determine Job Card ID, Product ID, and Service Line ID
            target_job_id = job_id
            target_service_line_id = service_line_id
            target_product_id = product_id

            if new_status != 'idle':
                if not target_service_line_id and emp.current_service_line_id:
                    target_service_line_id = emp.current_service_line_id.id
                if not target_job_id and target_service_line_id:
                    s_line = self.env['fleet.repair.service.line'].browse(target_service_line_id)
                    target_job_id = s_line.repair_id.id if s_line.repair_id else False
                if not target_job_id and emp.current_job_id:
                    target_job_id = emp.current_job_id.id

            # If product_id is provided and target_job_id exists, find or create the service line on the job card
            if target_job_id and target_product_id and not target_service_line_id:
                repair = self.env['fleet.repair'].browse(target_job_id)
                prod = self.env['product.product'].browse(target_product_id)
                matching = repair.service_line_ids.filtered(
                    lambda l: l.product_id.id == prod.id and (not l.employee_id or l.employee_id.id == emp.id)
                )
                if not matching:
                    matching = repair.service_line_ids.filtered(lambda l: l.product_id.id == prod.id)
                if matching:
                    target_service_line_id = matching[0].id
                    if not matching[0].employee_id or matching[0].employee_id.id != emp.id:
                        matching[0].sudo().write({'employee_id': emp.id})
                else:
                    dept = emp.department_id if emp.department_id else repair.department_id
                    if not dept:
                        dept = self.env['hr.department'].search([('model_ids.model', '=', 'fleet.repair.service.line')], limit=1) or self.env['hr.department'].search([], limit=1)
                    new_sline = self.env['fleet.repair.service.line'].with_context(skip_status_log_sync=True).sudo().create({
                        'repair_id': repair.id,
                        'product_id': prod.id,
                        'name': prod.name,
                        'employee_id': emp.id,
                        'department_id': dept.id if dept else False,
                        'unit_price': prod.list_price or 0.0,
                    })
                    target_service_line_id = new_sline.id

            if target_service_line_id and not target_product_id:
                sline_obj = self.env['fleet.repair.service.line'].browse(target_service_line_id)
                if sline_obj.product_id:
                    target_product_id = sline_obj.product_id.id

            s_name = False
            if target_product_id:
                prod_obj = self.env['product.product'].browse(target_product_id)
                s_name = prod_obj.name
            elif target_service_line_id:
                sline_obj = self.env['fleet.repair.service.line'].browse(target_service_line_id)
                s_name = sline_obj.product_id.name if sline_obj.product_id else (sline_obj.name or '')

            # Close any open status logs for this employee
            open_logs = self.env['hr.employee.status.log'].search([
                ('employee_id', '=', emp.id),
                ('end_datetime', '=', False),
            ])
            for olog in open_logs:
                delta = 0.0
                if olog.is_timer_running and olog.timer_last_start:
                    delta = (now - olog.timer_last_start).total_seconds()
                olog.write({
                    'end_datetime': now,
                    'timer_end': now if olog.is_timer_running else False,
                    'is_timer_running': False,
                    'is_timer_paused': False,
                    'timer_last_start': False,
                    'is_current_activity': False,
                    'accumulated_seconds': (olog.accumulated_seconds or 0.0) + delta,
                })

            # 2. Create or reuse log entry with running timer
            log_vals = {
                'employee_id': emp.id,
                'status': new_status,
                'start_datetime': now,
                'end_datetime': False,
                'is_current_activity': True,
                'job_id': target_job_id or False,
                'product_id': target_product_id or False,
                'service_line_id': target_service_line_id or False,
                'service_name': s_name or False,
                'notes': notes or False,
                'timer_start': now,
                'timer_last_start': now,
                'timer_end': False,
                'is_timer_running': True,
                'is_timer_paused': False,
            }
            existing_sline_log = False
            if target_service_line_id:
                existing_sline_log = self.env['hr.employee.status.log'].search([
                    ('service_line_id', '=', target_service_line_id)
                ], limit=1)

            if existing_sline_log:
                existing_sline_log.write(log_vals)
                new_log = existing_sline_log
            else:
                log_vals['accumulated_seconds'] = 0.0
                new_log = self.env['hr.employee.status.log'].create(log_vals)

            # Record into employee.timeline.history
            self.env['employee.timeline.history'].create_activity_log(
                emp.id,
                status=new_status,
                job_id=target_job_id or False,
                service_line_id=target_service_line_id or False,
                service_name=s_name or False,
                notes=notes or False,
                start_datetime=now,
                status_log_id=new_log.id,
            )

            # 3. Update employee state
            emp_vals = {
                'work_status': new_status,
                'current_status_start': now,
                'status_notes': notes or False,
            }
            if new_status != 'idle':
                emp_vals['current_job_id'] = target_job_id or False
                emp_vals['current_service_line_id'] = target_service_line_id or False
                emp_vals['is_idle_running'] = False
                emp_vals['idle_reason'] = False
                emp_vals['idle_timer_start'] = False
            else:
                emp_vals['current_job_id'] = False
                emp_vals['current_service_line_id'] = False
            emp.write(emp_vals)

            # 4. If new status is 'job' and service_line_id provided, assign employee & start timer
            if new_status == 'job' and target_service_line_id:
                s_line = self.env['fleet.repair.service.line'].browse(target_service_line_id)
                s_line.write({'employee_id': emp.id})
                if not self.env.context.get('skip_service_timer_start') and not s_line.is_timer_running:
                    s_line.action_start_timer()
                new_log.write({
                    'alloted_fru': s_line.alloted_fru,
                    'timer_start': s_line.timer_start or now,
                    'timer_last_start': s_line.timer_last_start or now,
                    'accumulated_seconds': s_line.accumulated_seconds or 0.0,
                })


    def action_open_employee_work_lines(self):
        """Opens the dedicated list view of work & status lines for this employee."""
        self.ensure_one()
        active_slines = self.env['fleet.repair.service.line'].search([
            ('employee_id', '=', self.id),
            ('repair_id.state', 'not in', ['done', 'invoiced', 'cancel'])
        ])
        if active_slines:
            active_slines._sync_to_employee_status_log()

        # Remove completed logs so this model only acts as a temporary live tracker of ongoing work
        if not self.env.context.get('skip_complete_unlink'):
            completed_logs = self.env['hr.employee.status.log'].search([
                ('employee_id', '=', self.id),
                '|', ('job_status', '=', 'completed'), ('status', '=', 'completed')
            ])
            if completed_logs:
                completed_logs.with_context(skip_service_line_sync=True).unlink()

        lead_user_id = False
        if self.coach_id and self.coach_id.user_id:
            lead_user_id = self.coach_id.user_id.id
        elif self.parent_id and self.parent_id.user_id:
            lead_user_id = self.parent_id.user_id.id
        elif self.user_id:
            lead_user_id = self.user_id.id
        else:
            lead_user_id = self.env.user.id

        return {
            'name': _(f"Work & Status Lines ({self.name})"),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.status.log',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('car_repair_industry.view_employee_work_status_list').id, 'list'),
                (self.env.ref('car_repair_industry.view_employee_work_status_form').id, 'form'),
            ],
            'domain': [
                ('employee_id', '=', self.id),
                ('job_status', '!=', 'completed'),
                ('status', '!=', 'completed'),
            ],
            'search_view_id': [self.env.ref('car_repair_industry.view_hr_employee_status_log_search').id, 'search'],
            'context': {
                'default_employee_id': self.id,
                'default_team_lead_id': lead_user_id,
                'search_default_employee_id': self.id,
            },
        }

    def action_open_status_wizard(self, default_status=False, default_repair_id=False, default_service_line_id=False):
        """Opens the Assign Job / Change Status wizard pre-populated for this employee."""
        self.ensure_one()
        lead_id = False
        if self.coach_id and self.coach_id.user_id:
            lead_id = self.coach_id.user_id.id
        elif self.parent_id and self.parent_id.user_id:
            lead_id = self.parent_id.user_id.id
        elif self.user_id:
            lead_id = self.user_id.id
        else:
            lead_id = self.env.user.id

        current_repair = default_repair_id
        if not current_repair:
            if self.current_job_id and self.current_job_id.state not in ['done', 'invoiced', 'cancel']:
                current_repair = self.current_job_id.id

        target_status = default_status or self.work_status or 'parts_unavailable'

        ctx = {
            'default_employee_id': self.id,
            'default_team_lead_id': lead_id,
            'default_status': target_status,
            'default_repair_id': current_repair,
        }
        if default_service_line_id:
            ctx['default_service_line_id'] = default_service_line_id
        elif self.current_service_line_id:
            ctx['default_service_line_id'] = self.current_service_line_id.id

        form_view = self.env.ref('car_repair_industry.view_assign_job_wizard_form', raise_if_not_found=False)
        return {
            'name': _('Manage Employee Status & Job Assignment'),
            'type': 'ir.actions.act_window',
            'res_model': 'assign.job.wizard',
            'view_mode': 'form',
            'views': [(form_view.id if form_view else False, 'form')],
            'target': 'new',
            'context': ctx,
        }

    def action_start_idle(self, idle_reason, notes=False):
        """Starts an idle session for this employee with the given reason, pausing any running work."""
        self.ensure_one()
        now = fields.Datetime.now()

        reason_labels = {
            'training': 'Training',
            'learning': 'Learning',
            'meeting': 'Meeting',
            'break_lunch': 'Break / Lunch',
        }
        reason_text = reason_labels.get(idle_reason, 'Idle')
        log_notes = f"{reason_text} - {notes}" if notes else reason_text

        # 1. Update employee state FIRST to idle
        self.write({
            'work_status': 'idle',
            'idle_reason': idle_reason,
            'is_idle_running': True,
            'idle_timer_start': now,
            'idle_accumulated_seconds': 0.0,
            'current_status_start': now,
            'status_notes': log_notes,
            'current_job_id': False,
            'current_service_line_id': False,
            'current_pause_reason': False,
            'current_car_display': False,
            'current_license_plate': False,
            'current_car_model': False,
            'current_job_name': False,
            'current_job_card_label': False,
        })

        # 2. Pause active service line timers for this employee
        running_slines = self.env['fleet.repair.service.line'].search([
            ('employee_id', '=', self.id),
            ('is_timer_running', '=', True),
        ])
        for sline in running_slines:
            sline.with_context(skip_status_wizard=True, skip_emp_status_sync=True, skip_status_log_sync=True).action_pause_timer()

        # 3. Close any open status logs for this employee
        open_logs = self.env['hr.employee.status.log'].search([
            ('employee_id', '=', self.id),
            ('end_datetime', '=', False),
        ])
        for log in open_logs:
            delta = 0.0
            if log.is_timer_running and log.timer_last_start:
                delta = (now - log.timer_last_start).total_seconds()
            log.write({
                'end_datetime': now,
                'timer_end': now if log.is_timer_running else False,
                'is_timer_running': False,
                'is_timer_paused': False,
                'timer_last_start': False,
                'is_current_activity': False,
                'accumulated_seconds': (log.accumulated_seconds or 0.0) + delta,
            })

        # Also ensure all other logs for this employee have is_current_activity=False
        all_other = self.env['hr.employee.status.log'].search([
            ('employee_id', '=', self.id),
            ('is_current_activity', '=', True)
        ])
        if all_other:
            all_other.write({'is_current_activity': False})

        # 4. Create a new status log for the idle session
        new_idle_log = self.env['hr.employee.status.log'].create({
            'employee_id': self.id,
            'status': 'idle',
            'idle_reason': idle_reason,
            'notes': log_notes,
            'start_datetime': now,
            'end_datetime': False,
            'is_current_activity': True,
            'timer_start': now,
            'timer_last_start': now,
            'is_timer_running': True,
            'is_timer_paused': False,
            'accumulated_seconds': 0.0,
        })

        # Record into employee.timeline.history
        self.env['employee.timeline.history'].create_activity_log(
            self.id,
            status='idle',
            idle_reason=idle_reason,
            notes=log_notes,
            start_datetime=now,
            status_log_id=new_idle_log.id,
        )

    def action_end_idle(self):
        """Ends the running idle session for this employee."""
        self.ensure_one()
        now = fields.Datetime.now()
        open_idle_logs = self.env['hr.employee.status.log'].search([
            ('employee_id', '=', self.id),
            ('status', '=', 'idle'),
            ('end_datetime', '=', False),
        ])
        for log in open_idle_logs:
            vals = {
                'end_datetime': now,
                'is_current_activity': False,
            }
            if log.is_timer_running:
                if log.timer_last_start:
                    delta = (now - log.timer_last_start).total_seconds()
                    vals['accumulated_seconds'] = (log.accumulated_seconds or 0.0) + delta
                vals['timer_last_start'] = False
                vals['timer_end'] = now
                vals['is_timer_running'] = False
                vals['is_timer_paused'] = False
            log.write(vals)

        # Close open idle in employee.timeline.history
        open_timeline_idle = self.env['employee.timeline.history'].search([
            ('employee_id', '=', self.id),
            ('status', '=', 'idle'),
            ('end_datetime', '=', False),
        ])
        if open_timeline_idle:
            open_timeline_idle.write({'end_datetime': now})

        self.write({
            'is_idle_running': False,
            'idle_timer_start': False,
            'idle_accumulated_seconds': 0.0,
            'idle_reason': False,
            'status_notes': False,
        })

    def action_open_idle_wizard(self):
        """Opens the Set Idle Wizard for this employee."""
        self.ensure_one()
        return {
            'name': _('Set Idle Status'),
            'type': 'ir.actions.act_window',
            'res_model': 'set.idle.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_employee_id': self.id,
            }
        }

    def action_reset_all_employee_timers(self):
        """Resets all timers (idle, paused, active service) for this employee."""
        now = fields.Datetime.now()
        for emp in self:
            emp.write({
                'is_idle_running': False,
                'idle_timer_start': False,
                'idle_accumulated_seconds': 0.0,
                'idle_reason': False,
                'current_pause_reason': False,
                'active_timer_last_start': False,
                'active_timer_accumulated_seconds': 0.0,
                'has_active_service_timer': False,
                'work_status': 'assigned' if emp.current_job_id else 'idle',
                'current_status_start': False,
            })
            active_logs = self.env['hr.employee.status.log'].search([
                ('employee_id', '=', emp.id),
                '|', ('end_datetime', '=', False),
                     ('job_status', 'in', ['working', 'paused']),
            ])
            for log in active_logs:
                log.action_reset_all_employee_timers()
        return True

    def action_reset_to_assigned(self):
        """Resets employee and active logs to assigned status."""
        for emp in self:
            emp.write({
                'work_status': 'assigned',
                'current_pause_reason': False,
                'has_active_service_timer': False,
                'active_timer_last_start': False,
                'current_status_start': fields.Datetime.now(),
            })
            active_logs = self.env['hr.employee.status.log'].search([
                ('employee_id', '=', emp.id),
                '|', ('end_datetime', '=', False),
                     ('job_status', 'in', ['working', 'paused']),
            ])
            active_logs.action_reset_to_assigned()
        return True


class HrEmployeeStatusLog(models.Model):
    _name = 'hr.employee.status.log'
    _description = 'Employee Workshop Status Log'
    _order = 'start_datetime desc, id desc'
    _rec_name = 'display_name'

    @api.depends('employee_id.name', 'status', 'job_id.sequence', 'job_id.name', 'product_id.name', 'service_name')
    def _compute_display_name(self):
        status_dict = dict(self._fields['status'].selection)
        for rec in self:
            parts = []
            if rec.employee_id:
                parts.append(rec.employee_id.name)
            if rec.status:
                parts.append(status_dict.get(rec.status, rec.status))
            if rec.job_id:
                parts.append(rec.job_id.sequence or rec.job_id.name or f"JC #{rec.job_id.id}")
            if rec.service_name:
                parts.append(rec.service_name)
            elif rec.product_id:
                parts.append(rec.product_id.name)
            rec.display_name = " - ".join(parts) if parts else (_("Status Log #%s") % (rec.id or ''))

    display_name = fields.Char(string='Name', compute='_compute_display_name', store=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    status = fields.Selection([
        ('job', 'Active Job'),
        ('assigned', 'Assigned'),
        ('paused', 'Paused'),
        ('waiting_car', 'Waiting for Car'),
        ('parts_unavailable', 'Parts Arrival / Not Available'),
        ('tools_issue', 'Tools Issue'),
        ('approval_pending', 'Customer Approval Pending'),
        ('idle', 'Idle')
    ], string='Status', required=True)
    display_status = fields.Char(
        string='Status',
        compute='_compute_display_status',
        store=True,
    )

    @api.depends('job_id', 'status', 'job_status', 'pause_reason', 'is_timer_running', 'is_timer_paused', 'accumulated_seconds', 'end_datetime')
    def _compute_display_status(self):
        pause_dict = dict(self._fields['pause_reason'].selection) if 'pause_reason' in self._fields else {}
        for rec in self:
            if rec.job_id or rec.status == 'job':
                if rec.job_status == 'completed':
                    rec.display_status = 'Completed'
                elif rec.is_timer_running or rec.job_status == 'working':
                    rec.display_status = 'Working'
                elif rec.pause_reason or rec.job_status == 'paused' or rec.status == 'paused' or rec.is_timer_paused:
                    rec.display_status = 'Paused'
                elif (rec.accumulated_seconds or 0.0) > 0 and rec.end_datetime:
                    rec.display_status = 'Completed'
                elif rec.job_status == 'assigned':
                    rec.display_status = 'Assigned'
                else:
                    rec.display_status = 'Working'
            else:
                status_dict = dict(self._fields['status'].selection)
                rec.display_status = status_dict.get(rec.status, rec.status or 'Idle')
    job_status = fields.Selection([
        ('assigned', 'Assigned'),
        ('working', 'Working'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
    ], string='Job Status', default='assigned')
    pause_reason = fields.Selection([
        ('waiting_parts', '📦 Waiting for Parts'),
        ('waiting_approval', '👤 Waiting for Customer Approval'),
        ('waiting_qc', '🟣 Waiting for QC'),
        ('assistance_required', '🟠 Assistance Required'),
        ('tools_issue', '🛠 Tool / Equipment Unavailable'),
        ('other', '⚪ Other'),
    ], string='Pause Reason')
    pause_notes = fields.Text(string='Pause Notes')
    idle_reason = fields.Selection([
        ('training', 'Training'),
        ('learning', 'Learning'),
        ('meeting', 'Meeting'),
        ('break_lunch', 'Break / Lunch'),
    ], string='Idle Reason')
    worked_time_display = fields.Char(string='Worked Time', compute='_compute_time_metrics')
    pause_time_display = fields.Char(string='Pause Time', compute='_compute_time_metrics')
    pause_duration = fields.Float(string='Pause Duration (Hours)', compute='_compute_time_metrics')
    total_elapsed_display = fields.Char(string='Total Elapsed', compute='_compute_time_metrics')
    pause_reason_display = fields.Char(string='Pause Reason', compute='_compute_pause_reason_display')
    pause_timer_start = fields.Datetime(string='Pause Timer Start')
    pause_accumulated_seconds = fields.Float(string='Pause Accumulated Seconds', default=0.0)
    is_pause_running = fields.Boolean(string='Is Pause Running', default=False)

    @api.depends('accumulated_seconds', 'timer_last_start', 'is_timer_running', 'start_datetime', 'end_datetime', 'job_status', 'status', 'pause_reason', 'service_line_ids.accumulated_seconds', 'is_collective_timer_running', 'collective_timer_last_start', 'is_pause_running', 'pause_timer_start', 'pause_accumulated_seconds')
    def _compute_time_metrics(self):
        now = fields.Datetime.now()
        for rec in self:
            worked_sec = rec.accumulated_seconds or 0.0
            if not worked_sec and rec.service_line_ids:
                sline_accum = sum(l.accumulated_seconds or 0.0 for l in rec.service_line_ids)
                if sline_accum > 0:
                    worked_sec = sline_accum

            if rec.is_timer_running and rec.timer_last_start:
                worked_sec += max(0, (now - rec.timer_last_start).total_seconds())
            elif rec.is_collective_timer_running and rec.collective_timer_last_start:
                worked_sec += max(0, (now - rec.collective_timer_last_start).total_seconds())

            if rec.start_datetime:
                end_time = rec.end_datetime or now
                total_sec = max(0, (end_time - rec.start_datetime).total_seconds())
            else:
                total_sec = worked_sec

            if total_sec < worked_sec:
                total_sec = worked_sec

            if rec.is_pause_running and rec.pause_timer_start:
                pause_sec = (rec.pause_accumulated_seconds or 0.0) + max(0, (now - rec.pause_timer_start).total_seconds())
            elif rec.pause_accumulated_seconds and not rec.is_pause_running:
                pause_sec = rec.pause_accumulated_seconds
            else:
                pause_sec = max(0, total_sec - worked_sec)

            if (rec.is_timer_running or rec.is_collective_timer_running or rec.job_status == 'working') and pause_sec == 0:
                total_sec = worked_sec

            def _fmt(sec):
                s = max(0, int(round(sec)))
                h = s // 3600
                m = (s % 3600) // 60
                sec_left = s % 60
                return f"{h:02d}:{m:02d}:{sec_left:02d}"

            rec.worked_time_display = _fmt(worked_sec)
            rec.pause_time_display = _fmt(pause_sec)
            rec.pause_duration = pause_sec / 3600.0
            rec.total_elapsed_display = _fmt(total_sec)

    @api.depends('pause_reason', 'job_status', 'is_timer_running', 'status', 'pause_notes', 'idle_reason')
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
            'training': '🎓 Training',
            'learning': '📚 Learning',
            'meeting': '👥 Meeting',
            'break_lunch': '☕ Break / Lunch',
        }
        for rec in self:
            if rec.status == 'idle':
                rec.pause_reason_display = idle_map.get(rec.idle_reason, rec.notes or 'Idle')
            elif rec.pause_reason and rec.pause_reason in reason_map:
                rec.pause_reason_display = reason_map[rec.pause_reason]
            elif rec.pause_reason:
                pause_dict = dict(self._fields['pause_reason'].selection) if 'pause_reason' in self._fields else {}
                rec.pause_reason_display = pause_dict.get(rec.pause_reason, rec.pause_reason)
            elif rec.job_status == 'completed':
                rec.pause_reason_display = '✅ Completed'
            elif rec.job_status == 'working' or rec.is_timer_running:
                rec.pause_reason_display = '🔧 Working'
            elif rec.job_status == 'paused' or rec.status == 'paused':
                # Infer pause reason if it was not explicitly stored
                notes_lower = ((rec.pause_notes or '') + ' ' + (rec.notes or '')).lower()
                if 'brake' in notes_lower or 'part' in notes_lower:
                    rec.pause_reason_display = '🟡 Waiting for Parts'
                elif 'approv' in notes_lower:
                    rec.pause_reason_display = '🔵 Waiting for Customer Approval'
                elif 'qc' in notes_lower:
                    rec.pause_reason_display = '🟣 Waiting for QC'
                elif 'assist' in notes_lower:
                    rec.pause_reason_display = '🟠 Assistance Required'
                elif 'tool' in notes_lower or 'equip' in notes_lower:
                    rec.pause_reason_display = '🔷 Tool / Equipment Unavailable'
                elif rec.status == 'parts_unavailable':
                    rec.pause_reason_display = '🟡 Waiting for Parts'
                elif rec.status == 'approval_pending':
                    rec.pause_reason_display = '🔵 Waiting for Customer Approval'
                elif rec.status == 'tools_issue':
                    rec.pause_reason_display = '🔷 Tool / Equipment Unavailable'
                elif rec.status == 'waiting_car':
                    rec.pause_reason_display = 'Waiting for Car'
                elif rec.pause_notes:
                    rec.pause_reason_display = rec.pause_notes
                else:
                    rec.pause_reason_display = '⚪ Other'
            elif rec.job_status == 'assigned':
                rec.pause_reason_display = '📋 Assigned'
            else:
                rec.pause_reason_display = '—'

    is_current_activity = fields.Boolean(
        string='Current Activity',
        default=True,
        index=True,
        help='Indicates whether this is the active current activity of the employee.'
    )

    def init(self):
        super().init()
        self.env.cr.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'hr_employee_status_log' 
                    AND column_name = 'is_current_activity'
                ) THEN
                    UPDATE hr_employee_status_log SET is_current_activity = FALSE;
                    UPDATE hr_employee_status_log 
                    SET is_current_activity = TRUE 
                    WHERE id IN (
                        SELECT DISTINCT ON (employee_id) id 
                        FROM hr_employee_status_log 
                        ORDER BY employee_id, start_datetime DESC, id DESC
                    );
                    UPDATE hr_employee_status_log
                    SET end_datetime = COALESCE(write_date, start_datetime, NOW() AT TIME ZONE 'UTC')
                    WHERE is_current_activity = FALSE AND end_datetime IS NULL;
                END IF;
            END $$;
        """)

    @api.model
    def _update_employee_current_activity(self, employee_id=None):
        """Ensures that for each employee, only their single active current status log
        has is_current_activity=True, and all previous/historical logs have is_current_activity=False.
        Also closes any orphan open logs from previous activities."""
        employees = self.env['hr.employee'].browse(employee_id) if employee_id else self.env['hr.employee'].search([])

        for emp in employees:
            logs = self.search([('employee_id', '=', emp.id)], order='start_datetime desc, id desc')
            if not logs:
                continue

            current_log = False
            if emp.work_status == 'idle':
                idle_logs = logs.filtered(lambda l: l.status == 'idle' and not l.end_datetime)
                if idle_logs:
                    current_log = idle_logs[0]
            elif emp.current_job_id:
                job_logs = logs.filtered(lambda l: l.job_id.id == emp.current_job_id.id and not l.end_datetime)
                if job_logs:
                    current_log = job_logs[0]

            if not current_log:
                open_logs = logs.filtered(lambda l: not l.end_datetime)
                if open_logs:
                    current_log = open_logs[0]

            if not current_log:
                current_log = logs[0]

            if not current_log.is_current_activity:
                current_log.write({'is_current_activity': True})

            other_logs = logs - current_log
            for olog in other_logs:
                vals = {}
                if olog.is_current_activity:
                    vals['is_current_activity'] = False
                if not olog.end_datetime:
                    vals['end_datetime'] = current_log.start_datetime or olog.write_date or fields.Datetime.now()
                    vals['is_timer_running'] = False
                    vals['is_pause_running'] = False
                    vals['timer_last_start'] = False
                if vals:
                    olog.write(vals)

    def action_view_full_history(self):
        """Opens the complete timeline history for this employee in employee.timeline.history."""
        emp = self.employee_id or (self.env['hr.employee'].browse(self.env.context.get('default_employee_id')) if self.env.context.get('default_employee_id') else False)
        domain = [('employee_id', '=', emp.id)] if emp else []
        name = _(f"Timeline History ({emp.name})") if emp else _("Employee Timeline History")
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'employee.timeline.history',
            'view_mode': 'list,pivot,graph,form',
            'views': [
                (self.env.ref('car_repair_industry.view_employee_timeline_history_list').id, 'list'),
                (self.env.ref('car_repair_industry.view_employee_timeline_history_form').id, 'form'),
            ],
            'domain': domain,
            'search_view_id': [self.env.ref('car_repair_industry.view_employee_timeline_history_search').id, 'search'],
            'context': {
                'default_employee_id': emp.id if emp else False,
            },
        }

    start_datetime = fields.Datetime(string='Start Time', default=fields.Datetime.now, required=True)
    end_datetime = fields.Datetime(string='End Time')
    duration = fields.Float(string='Duration (Hours)', compute='_compute_duration', store=True)
    team_lead_id = fields.Many2one(
        'res.users',
        string='Team Lead',
        compute='_compute_team_lead_id',
        store=True,
        readonly=False,
    )
    job_id = fields.Many2one(
        'fleet.repair',
        string='Job Card',
        domain="['|', ('id', '=', job_id), '&', ('state', 'not in', ['done', 'invoiced', 'cancel']), ('team_lead_id', '=', team_lead_id)]",
    )
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
    service_line_ids = fields.One2many(
        'fleet.repair.service.line',
        'status_log_id',
        string='Service Lines',
        compute='_compute_service_line_ids',
        inverse='_inverse_service_line_ids',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Service',
        domain=[('type', '=', 'service')],
        compute='_compute_product_id',
        store=True,
        readonly=False,
    )
    service_line_id = fields.Many2one(
        'fleet.repair.service.line',
        string='Service Line',
    )
    is_collective = fields.Boolean(
        related='service_line_id.is_collective',
        string='In Collective Timer',
        readonly=True,
    )
    collective_member_count = fields.Integer(
        related='service_line_id.collective_member_count',
        string='Collective Member Count',
        readonly=True,
    )
    service_name = fields.Char(string='Service Name', compute='_compute_service_name', store=True, readonly=False)
    notes = fields.Text(string='Notes')
    is_collective_timer_running = fields.Boolean(
        string='Collective Timer Running',
        compute='_compute_collective_timer_info',
    )
    collective_selected_count = fields.Integer(
        string='Selected Services Count',
        compute='_compute_collective_timer_info',
    )
    collective_timer_last_start = fields.Datetime(
        string='Collective Timer Last Start',
        compute='_compute_collective_timer_info',
    )
    collective_accumulated_seconds = fields.Float(
        string='Collective Accumulated Seconds',
        compute='_compute_collective_timer_info',
    )
    collective_duration = fields.Float(
        string='Collective Duration',
        compute='_compute_collective_timer_info',
    )
    collective_target_hours = fields.Float(
        string='Collective Target Hours',
        compute='_compute_collective_timer_info',
        digits=(16, 2),
    )
    collective_target_seconds = fields.Float(
        string='Collective Target Seconds',
        compute='_compute_collective_timer_info',
    )
    collective_remaining_seconds = fields.Float(
        string='Collective Remaining Seconds',
        compute='_compute_collective_timer_info',
    )

    @api.depends(
        'service_line_ids.is_group_selected',
        'service_line_ids.is_timer_running',
        'service_line_ids.is_collective',
        'service_line_ids.timer_last_start',
        'service_line_ids.accumulated_seconds',
        'service_line_ids.hours',
        'service_line_ids.subtotal'
    )
    def _compute_collective_timer_info(self):
        for rec in self:
            selected = rec.service_line_ids.filtered(lambda l: l.is_group_selected)
            rec.collective_selected_count = len(selected)
            collective_running = rec.service_line_ids.filtered(lambda l: l.is_timer_running and l.is_collective)
            rec.is_collective_timer_running = bool(collective_running)

            target_lines = collective_running if collective_running else selected
            if target_lines:
                running_starts = [l.timer_last_start for l in target_lines if l.timer_last_start]
                rec.collective_timer_last_start = min(running_starts) if running_starts else False
                rec.collective_accumulated_seconds = sum(l.accumulated_seconds for l in target_lines)
                target_hrs = sum((l.hours or ((l.alloted_fru * 5.0 / 60.0) if l.alloted_fru else 0.0) or ((l.subtotal or 0.0) / 2400.0)) for l in target_lines)
                rec.collective_target_hours = round(target_hrs, 2)
                rec.collective_target_seconds = round(target_hrs * 3600.0)
            else:
                rec.collective_timer_last_start = False
                rec.collective_accumulated_seconds = 0.0
                rec.collective_target_hours = 0.0
                rec.collective_target_seconds = 0.0

            total_sec = rec.collective_accumulated_seconds or 0.0
            if rec.is_collective_timer_running and rec.collective_timer_last_start:
                delta = fields.Datetime.now() - rec.collective_timer_last_start
                total_sec += delta.total_seconds()
            rec.collective_duration = total_sec / 3600.0
            rec.collective_remaining_seconds = rec.collective_target_seconds - total_sec

    def action_start_collective_timer(self):
        self.ensure_one()
        selected_lines = self.service_line_ids.filtered(lambda l: l.is_group_selected)
        if not selected_lines:
            active_lines = self.service_line_ids.filtered(lambda l: not (l.timer_end and not l.is_timer_running and not l.is_timer_paused and (l.accumulated_seconds or 0) > 0))
            selected_lines = active_lines or self.service_line_ids
            selected_lines.write({'is_group_selected': True})
        if not selected_lines:
            raise UserError(_("Please select at least 1 service line using the checkboxes to start a collective timer."))

        other_running = self.env['fleet.repair.service.line'].search([
            ('employee_id', '=', self.employee_id.id),
            ('is_timer_running', '=', True),
            ('id', 'not in', selected_lines.ids),
            ('repair_id.state', 'not in', ['done', 'invoiced', 'cancel'])
        ])
        if other_running:
            raise UserError(_("Another service timer is currently running for this technician. Please pause it first."))

        now = fields.Datetime.now()
        n_members = len(selected_lines)
        for line in selected_lines:
            line.write({
                'is_collective': True,
                'collective_member_count': n_members,
            })
            line.with_context(allow_collective_start=True, skip_timeline_sync=True).action_start_timer()
            line._compute_time_diff()

        pause_delta = 0.0
        if self.is_pause_running and self.pause_timer_start:
            pause_delta = max(0, (now - self.pause_timer_start).total_seconds())

        vals = {
            'status': 'job',
            'job_status': 'working',
            'pause_reason': False,
            'is_current_activity': True,
            'is_timer_running': True,
            'timer_start': self.timer_start or now,
            'timer_last_start': now,
            'end_datetime': False,
            'is_pause_running': False,
            'pause_timer_start': False,
            'pause_accumulated_seconds': (self.pause_accumulated_seconds or 0.0) + pause_delta,
        }
        self.write(vals)

        # Record into employee.timeline.history
        self.env['employee.timeline.history'].create_activity_log(
            self.employee_id.id,
            status='working',
            job_id=self.job_id.id if self.job_id else False,
            service_line_id=self.service_line_id.id if self.service_line_id else False,
            service_name=self.service_name or '',
            start_datetime=now,
            status_log_id=self.id,
            accumulated_seconds=self.accumulated_seconds or 0.0,
        )

        if self.employee_id:
            self.employee_id.sudo().write({
                'work_status': 'job',
                'current_pause_reason': False,
                'current_job_id': self.job_id.id if self.job_id else False,
            })
        self.service_line_ids.with_context(skip_timeline_sync=True)._sync_to_employee_status_log()

    def action_pause_collective_timer(self):
        self.ensure_one()
        now = fields.Datetime.now()
        running_lines = self.service_line_ids.filtered(lambda l: l.is_timer_running)
        for line in running_lines:
            line.action_pause_timer()
        self.write({
            'status': 'paused',
            'job_status': 'paused',
            'is_pause_running': True,
            'pause_timer_start': now,
            'is_current_activity': True,
        })
        if self.employee_id:
            self.employee_id.sudo().write({
                'work_status': 'paused',
                'current_pause_reason': self.pause_reason or False,
            })
        self.service_line_ids._sync_to_employee_status_log()

    def action_open_pause_wizard(self):
        self.ensure_one()
        now = fields.Datetime.now()
        # Immediately pause running service line timers so no work seconds accumulate in the background
        running_lines = self.service_line_ids.filtered(lambda l: l.is_timer_running)
        for line in running_lines:
            line.with_context(skip_timeline_sync=True).action_pause_timer()

        # Update status log to paused state immediately
        if self.is_timer_running and self.timer_last_start:
            delta = (now - self.timer_last_start).total_seconds()
            self.accumulated_seconds = (self.accumulated_seconds or 0.0) + delta

        default_reason = self.pause_reason or 'waiting_parts'
        self.write({
            'status': 'paused',
            'job_status': 'paused',
            'is_timer_running': False,
            'timer_last_start': False,
            'timer_end': now,
            'is_pause_running': True,
            'pause_timer_start': now,
            'pause_reason': default_reason,
            'is_current_activity': True,
        })
        if self.employee_id:
            self.employee_id.sudo().write({
                'work_status': 'paused',
                'current_pause_reason': default_reason,
            })

        return {
            'name': _('Pause Job'),
            'type': 'ir.actions.act_window',
            'res_model': 'pause.job.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('car_repair_industry.view_pause_job_wizard_form').id,
            'target': 'new',
            'context': {
                'default_status_log_id': self.id,
                'default_pause_reason': default_reason,
                'default_notes': self.pause_notes or '',
            }
        }

    def action_complete_job(self):
        self.ensure_one()
        now = fields.Datetime.now()
        # Stop all running service lines without triggering sync (which would overwrite our status)
        running_lines = self.service_line_ids.filtered(lambda l: l.is_timer_running)
        for line in running_lines:
            if line.timer_last_start:
                delta = now - line.timer_last_start
                run_sec = delta.total_seconds()
                if line.is_collective and (line.collective_member_count or 1) > 1:
                    run_sec = run_sec / float(line.collective_member_count)
                line.accumulated_seconds += run_sec
            line.with_context(skip_status_log_sync=True).write({
                'timer_last_start': False,
                'timer_end': now,
                'is_timer_running': False,
                'is_timer_paused': False,
            })
            line._compute_time_diff()
            line._sync_to_work_lines()

        # Also mark all paused lines as no longer paused (job is done)
        paused_lines = self.service_line_ids.filtered(lambda l: l.is_timer_paused)
        if paused_lines:
            paused_lines.with_context(skip_status_log_sync=True).write({
                'is_timer_paused': False,
            })

        # Calculate total accumulated time for the status log
        total_accumulated = sum(self.service_line_ids.mapped('accumulated_seconds') or [0.0])

        # Update the status log directly without calling _sync which would override status
        log_vals = {
            'job_status': 'completed',
            'status': 'completed',
            'end_datetime': now,
            'is_timer_running': False,
            'is_timer_paused': False,
            'accumulated_seconds': total_accumulated,
            'pause_reason': False,
            'pause_notes': False,
            'is_current_activity': False,
        }
        if self.is_pause_running and self.pause_timer_start:
            delta = now - self.pause_timer_start
            log_vals['pause_accumulated_seconds'] = (self.pause_accumulated_seconds or 0.0) + max(0, delta.total_seconds())
        log_vals['is_pause_running'] = False
        log_vals['pause_timer_start'] = False
        self.with_context(skip_service_timer_sync=True, skip_status_log_sync=True).write(log_vals)

        # Record into employee.timeline.history
        self.env['employee.timeline.history'].create_activity_log(
            self.employee_id.id,
            status='completed',
            job_id=self.job_id.id if self.job_id else False,
            service_line_id=self.service_line_id.id if self.service_line_id else False,
            service_name=self.service_name or '',
            start_datetime=now,
            end_datetime=now,
            accumulated_seconds=total_accumulated,
            status_log_id=self.id,
        )

        # Update the employee record
        if self.employee_id:
            first_sline = self.service_line_ids[0] if self.service_line_ids else False
            self.employee_id.sudo().write({
                'work_status': 'completed',
                'current_job_id': self.job_id.id if self.job_id else False,
                'current_service_line_id': first_sline.id if first_sline else False,
                'current_pause_reason': False,
                'is_idle_running': False,
                'idle_reason': False,
                'idle_timer_start': False,
            })

        emp = self.employee_id
        if emp:
            # Transition to the employee work lines list view.
            # We skip unlinking during this RPC to prevent Odoo FormController from throwing FetchRecordError ("Records cannot be found / might have been deleted").
            # The list view domain immediately filters it out (job_status != 'completed'), so it disappears from the live work board instantly.
            return emp.with_context(skip_complete_unlink=True).action_open_employee_work_lines()
        return {'type': 'ir.actions.act_window_close'}

    def action_select_all_group(self):
        self.ensure_one()
        self.service_line_ids.write({'is_group_selected': True})
        self._compute_collective_timer_info()

    def action_unselect_all_group(self):
        self.ensure_one()
        self.service_line_ids.write({'is_group_selected': False})
        self._compute_collective_timer_info()

    @api.depends('job_id', 'job_id.service_line_ids', 'job_id.service_line_ids.employee_id', 'employee_id')
    def _compute_service_line_ids(self):
        for rec in self:
            if rec.job_id and rec.employee_id:
                rec.service_line_ids = rec.job_id.service_line_ids.filtered(
                    lambda l: l.status_log_id == rec or l.employee_id == rec.employee_id
                )
            elif rec.job_id:
                rec.service_line_ids = rec.job_id.service_line_ids
            elif rec.id:
                rec.service_line_ids = self.env['fleet.repair.service.line'].search([('status_log_id', '=', rec.id)])
            else:
                rec.service_line_ids = self.env['fleet.repair.service.line']

    def _inverse_service_line_ids(self):
        for rec in self:
            for line in rec.service_line_ids:
                if not line.id or isinstance(line.id, models.NewId):
                    continue
                vals = {}
                if rec.job_id and line.repair_id != rec.job_id:
                    vals['repair_id'] = rec.job_id.id
                if rec.employee_id and line.employee_id != rec.employee_id:
                    vals['employee_id'] = rec.employee_id.id
                if rec.department_id and line.department_id != rec.department_id:
                    vals['department_id'] = rec.department_id.id
                if line.status_log_id != rec:
                    vals['status_log_id'] = rec.id
                if vals:
                    line.sudo().write(vals)

    @api.onchange('service_line_ids')
    def _onchange_service_line_ids(self):
        self._compute_collective_timer_info()
        if self.employee_id:
            for line in self.service_line_ids:
                if not line.employee_id or line.employee_id != self.employee_id:
                    line.employee_id = self.employee_id
                if self.employee_id.department_id and line.department_id != self.employee_id.department_id:
                    line.department_id = self.employee_id.department_id
                if self.job_id and line.repair_id != self.job_id:
                    line.repair_id = self.job_id
        if not self.service_line_id and self.service_line_ids:
            self.service_line_id = self.service_line_ids[0]
            if self.service_line_ids[0].product_id:
                self.product_id = self.service_line_ids[0].product_id
                self.service_name = self.service_line_ids[0].product_id.name

    def action_add_service_line(self):
        self.ensure_one()
        if not self.job_id:
            raise UserError(_("Please select a Job Card before adding a service."))
        return {
            'name': _('Add Services from Product Masters'),
            'type': 'ir.actions.act_window',
            'res_model': 'select.service.product.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('car_repair_industry.view_select_service_product_wizard_form').id,
            'target': 'new',
            'context': {
                'default_status_log_id': self.id,
            }
        }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        emp_id = res.get('employee_id') or self.env.context.get('default_employee_id')
        if not emp_id and self.env.context.get('active_model') == 'hr.employee':
            emp_id = self.env.context.get('active_id')
        if not emp_id and self.env.user:
            user_emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
            if user_emp:
                emp_id = user_emp.id
        if emp_id:
            res['employee_id'] = emp_id
            if 'team_lead_id' in fields_list or not res.get('team_lead_id'):
                emp = self.env['hr.employee'].browse(emp_id)
                lead = False
                if emp.coach_id and emp.coach_id.user_id:
                    lead = emp.coach_id.user_id.id
                elif emp.parent_id and emp.parent_id.user_id:
                    lead = emp.parent_id.user_id.id
                elif emp.user_id:
                    lead = emp.user_id.id
                else:
                    lead = self.env.user.id
                res['team_lead_id'] = lead
        return res

    @api.depends('employee_id', 'employee_id.coach_id', 'employee_id.coach_id.user_id', 'employee_id.parent_id', 'employee_id.parent_id.user_id')
    def _compute_team_lead_id(self):
        for rec in self:
            lead = False
            if rec.employee_id:
                if rec.employee_id.coach_id and rec.employee_id.coach_id.user_id:
                    lead = rec.employee_id.coach_id.user_id
                elif rec.employee_id.parent_id and rec.employee_id.parent_id.user_id:
                    lead = rec.employee_id.parent_id.user_id
                elif rec.employee_id.user_id:
                    lead = rec.employee_id.user_id
            if not lead:
                lead = self.env.user
            rec.team_lead_id = lead

    @api.depends('service_line_id', 'service_line_id.product_id')
    def _compute_product_id(self):
        for rec in self:
            if rec.service_line_id and rec.service_line_id.product_id:
                rec.product_id = rec.service_line_id.product_id
            elif not rec.product_id:
                rec.product_id = False

    @api.onchange('employee_id')
    def _onchange_employee_id_team_lead(self):
        lead = False
        if self.employee_id:
            if self.employee_id.coach_id and self.employee_id.coach_id.user_id:
                lead = self.employee_id.coach_id.user_id
            elif self.employee_id.parent_id and self.employee_id.parent_id.user_id:
                lead = self.employee_id.parent_id.user_id
            elif self.employee_id.user_id:
                lead = self.employee_id.user_id
        if not lead:
            lead = self.env.user
        self.team_lead_id = lead
        if self.job_id and self.employee_id:
            dept = self.employee_id.department_id
            self.service_line_ids = self.job_id.service_line_ids.filtered(
                lambda l: l.employee_id == self.employee_id and (not dept or l.department_id == dept)
            )
        elif self.job_id:
            self.service_line_ids = self.job_id.service_line_ids
        else:
            self.service_line_ids = False
        if self.service_line_id and self.employee_id and self.service_line_id.employee_id != self.employee_id:
            self.service_line_id = False
            self.product_id = False
            self.service_name = False

    @api.onchange('product_id', 'job_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.service_name = self.product_id.name
            if self.job_id:
                emp = self.employee_id or (self.env['hr.employee'].browse(self.env.context.get('default_employee_id')) if self.env.context.get('default_employee_id') else False)
                matching = self.job_id.service_line_ids.filtered(
                    lambda l: l.product_id == self.product_id and (not l.employee_id or (emp and l.employee_id == emp))
                )
                self.service_line_id = matching[0] if matching else False
        else:
            self.service_name = False
            self.service_line_id = False

    @api.onchange('job_id')
    def _onchange_job_id(self):
        if self.job_id and self.service_line_id and self.service_line_id.repair_id != self.job_id:
            self.service_line_id = False
            self.service_name = False
        if self.job_id and self.employee_id:
            dept = self.employee_id.department_id
            self.service_line_ids = self.job_id.service_line_ids.filtered(
                lambda l: l.employee_id == self.employee_id and (not dept or l.department_id == dept)
            )
        elif self.job_id:
            self.service_line_ids = self.job_id.service_line_ids
        else:
            self.service_line_ids = False

    @api.onchange('service_line_id')
    def _onchange_service_line_id(self):
        if self.service_line_id:
            if self.service_line_id.product_id:
                self.product_id = self.service_line_id.product_id
            self.service_name = self.service_line_id.product_id.name if self.service_line_id.product_id else (self.service_line_id.name or '')
            if not self.job_id and self.service_line_id.repair_id:
                self.job_id = self.service_line_id.repair_id

    @api.depends('service_line_ids', 'service_line_ids.product_id.name', 'service_line_ids.name', 'product_id', 'product_id.name', 'service_line_id')
    def _compute_service_name(self):
        for log in self:
            if log.service_line_ids:
                service_names = list(dict.fromkeys(filter(None, [l.product_id.name or l.name for l in log.service_line_ids])))
                if len(service_names) > 1:
                    log.service_name = f"{service_names[0]} (+{len(service_names) - 1} services)"
                elif len(service_names) == 1:
                    log.service_name = service_names[0]
                elif log.product_id:
                    log.service_name = log.product_id.name
                elif not log.service_name:
                    log.service_name = ''
            elif log.product_id:
                log.service_name = log.product_id.name
            elif log.service_line_id:
                log.service_name = log.service_line_id.product_id.name if log.service_line_id.product_id else (log.service_line_id.name or '')
            elif not log.service_name:
                log.service_name = ''

    def _sync_to_service_line(self, vals=None):
        """Reflects changes made in hr.employee.status.log directly onto fleet.repair.service.line."""
        if self.env.context.get('skip_service_line_sync'):
            return
        vals = vals or {}
        for log in self:
            sline = log.service_line_id
            # 1. If no service_line_id, find or create it on the job card
            if not sline and log.job_id and log.product_id:
                repair = log.job_id
                prod = log.product_id
                emp = log.employee_id
                matching = repair.service_line_ids.filtered(
                    lambda l: l.product_id.id == prod.id and (not l.employee_id or (emp and l.employee_id.id == emp.id))
                )
                if matching:
                    sline = matching[0]
                    if emp and (not sline.employee_id or sline.employee_id.id != emp.id):
                        sline.sudo().write({'employee_id': emp.id})
                else:
                    dept = emp.department_id if (emp and emp.department_id) else repair.department_id
                    if not dept:
                        dept = self.env['hr.department'].search([('model_ids.model', '=', 'fleet.repair.service.line')], limit=1) or self.env['hr.department'].search([], limit=1)
                    sline = self.env['fleet.repair.service.line'].with_context(skip_status_log_sync=True).sudo().create({
                        'repair_id': repair.id,
                        'product_id': prod.id,
                        'name': prod.name,
                        'employee_id': emp.id if emp else False,
                        'department_id': dept.id if dept else False,
                        'unit_price': prod.list_price or 200.0,
                        'alloted_fru': log.alloted_fru or prod.alloted_fru or 0,
                    })
                log.with_context(skip_service_line_sync=True).sudo().write({'service_line_id': sline.id})

            if not sline:
                continue

            # 2. Reflect updates to service_line_id
            sline_updates = {}
            if log.employee_id and (not sline.employee_id or sline.employee_id.id != log.employee_id.id):
                sline_updates['employee_id'] = log.employee_id.id
            if log.product_id and (not sline.product_id or sline.product_id.id != log.product_id.id):
                sline_updates['product_id'] = log.product_id.id
                sline_updates['name'] = log.product_id.name
                if not sline.alloted_fru and log.product_id.alloted_fru:
                    sline_updates['alloted_fru'] = log.product_id.alloted_fru
                if log.product_id.list_price:
                    sline_updates['unit_price'] = log.product_id.list_price
            if log.job_id and sline.repair_id and sline.repair_id.id != log.job_id.id:
                sline_updates['repair_id'] = log.job_id.id

            for f in ('timer_start', 'timer_last_start', 'timer_end', 'is_timer_running', 'is_timer_paused', 'accumulated_seconds', 'fru_status'):
                if hasattr(sline, f) and getattr(sline, f) != getattr(log, f):
                    sline_updates[f] = getattr(log, f)

            if sline_updates:
                sline.with_context(skip_status_log_sync=True, skip_service_line_sync=True).sudo().write(sline_updates)
                sline._compute_time_diff()
                sline._sync_to_work_lines()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            emp_id = vals.get('employee_id') or self.env.context.get('default_employee_id')
            if not emp_id and self.env.context.get('active_model') == 'hr.employee':
                emp_id = self.env.context.get('active_id')
            if not emp_id and self.env.user:
                user_emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
                if user_emp:
                    emp_id = user_emp.id
            if not emp_id:
                any_emp = self.env['hr.employee'].sudo().search([], limit=1)
                if any_emp:
                    emp_id = any_emp.id
            if emp_id and not vals.get('employee_id'):
                vals['employee_id'] = emp_id

            if 'service_line_ids' in vals and isinstance(vals['service_line_ids'], (list, tuple)):
                cleaned_cmds = []
                for cmd in vals['service_line_ids']:
                    if isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == 0:
                        line_vals = dict(cmd[2])
                        j_id = vals.get('job_id')
                        e_id = emp_id
                        if j_id and not line_vals.get('repair_id'):
                            line_vals['repair_id'] = j_id
                        if e_id and not line_vals.get('employee_id'):
                            line_vals['employee_id'] = e_id
                        if e_id and not line_vals.get('department_id'):
                            emp_rec = self.env['hr.employee'].browse(e_id)
                            if emp_rec.department_id:
                                line_vals['department_id'] = emp_rec.department_id.id
                        if line_vals.get('product_id') and not line_vals.get('name'):
                            p_rec = self.env['product.product'].browse(line_vals['product_id'])
                            line_vals['name'] = p_rec.name
                        new_sline = self.env['fleet.repair.service.line'].sudo().create(line_vals)
                        cleaned_cmds.append((4, new_sline.id))
                        if not vals.get('service_line_id'):
                            vals['service_line_id'] = new_sline.id
                            if new_sline.product_id:
                                vals['product_id'] = new_sline.product_id.id
                                vals['service_name'] = new_sline.product_id.name
                    else:
                        cleaned_cmds.append(cmd)
                vals.pop('service_line_ids', None)

            if vals.get('product_id'):
                prod = self.env['product.product'].browse(vals['product_id'])
                if not vals.get('service_name'):
                    vals['service_name'] = prod.name
                if vals.get('job_id') and not vals.get('service_line_id'):
                    repair = self.env['fleet.repair'].browse(vals['job_id'])
                    matching = repair.service_line_ids.filtered(
                        lambda l: l.product_id.id == prod.id and (not l.employee_id or (emp_id and l.employee_id.id == emp_id))
                    )
                    if matching:
                        s_line = matching[0]
                        if emp_id and (not s_line.employee_id or s_line.employee_id.id != emp_id):
                            s_line.sudo().write({'employee_id': emp_id})
                        vals['service_line_id'] = s_line.id
                    else:
                        emp = self.env['hr.employee'].browse(emp_id) if emp_id else False
                        if not emp and repair.service_employee_id:
                            emp = repair.service_employee_id
                        if not emp:
                            emp = self.env['hr.employee'].sudo().search([], limit=1)
                        dept = emp.department_id if (emp and emp.department_id) else (repair.department_id if repair else False)
                        if not dept:
                            dept = self.env['hr.department'].search([('model_ids.model', '=', 'fleet.repair.service.line')], limit=1) or self.env['hr.department'].search([], limit=1)
                        s_line = self.env['fleet.repair.service.line'].with_context(skip_status_log_sync=True).sudo().create({
                            'repair_id': repair.id,
                            'product_id': prod.id,
                            'name': prod.name,
                            'employee_id': emp.id,
                            'department_id': dept.id if dept else False,
                            'unit_price': prod.list_price or 200.0,
                            'alloted_fru': vals.get('alloted_fru') or prod.alloted_fru or 0,
                        })
                        vals['service_line_id'] = s_line.id

        records = super().create(vals_list)
        if not self.env.context.get('skip_service_line_sync'):
            records._sync_to_service_line()
        return records

    def write(self, vals):
        if 'service_line_ids' in vals and isinstance(vals['service_line_ids'], (list, tuple)):
            for rec in self:
                j_id = vals.get('job_id') or (rec.job_id.id if rec.job_id else False)
                e_id = vals.get('employee_id') or (rec.employee_id.id if rec.employee_id else False)
                cleaned_cmds = []
                for cmd in vals['service_line_ids']:
                    if isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == 0:
                        line_vals = dict(cmd[2])
                        if j_id and not line_vals.get('repair_id'):
                            line_vals['repair_id'] = j_id
                        if e_id and not line_vals.get('employee_id'):
                            line_vals['employee_id'] = e_id
                        if e_id and not line_vals.get('department_id'):
                            emp_rec = self.env['hr.employee'].browse(e_id)
                            if emp_rec.department_id:
                                line_vals['department_id'] = emp_rec.department_id.id
                        if line_vals.get('product_id') and not line_vals.get('name'):
                            p_rec = self.env['product.product'].browse(line_vals['product_id'])
                            line_vals['name'] = p_rec.name
                        new_sline = self.env['fleet.repair.service.line'].sudo().create(line_vals)
                        cleaned_cmds.append((4, new_sline.id))
                        if not rec.service_line_id and not vals.get('service_line_id'):
                            vals['service_line_id'] = new_sline.id
                            if new_sline.product_id:
                                vals['product_id'] = new_sline.product_id.id
                                vals['service_name'] = new_sline.product_id.name
                    elif isinstance(cmd, (list, tuple)) and len(cmd) >= 2 and cmd[0] == 4 and e_id:
                        sline = self.env['fleet.repair.service.line'].sudo().browse(cmd[1])
                        if sline.exists():
                            sline.sudo().write({'employee_id': e_id})
                            if not rec.service_line_id and not vals.get('service_line_id'):
                                vals['service_line_id'] = sline.id
                                if sline.product_id:
                                    vals['product_id'] = sline.product_id.id
                                    vals['service_name'] = sline.product_id.name
                    elif isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == 6 and e_id:
                        slines = self.env['fleet.repair.service.line'].sudo().browse(cmd[2])
                        for sline in slines:
                            sline.sudo().write({'employee_id': e_id})
                        if slines and not rec.service_line_id and not vals.get('service_line_id'):
                            vals['service_line_id'] = slines[0].id
                            if slines[0].product_id:
                                vals['product_id'] = slines[0].product_id.id
                                vals['service_name'] = slines[0].product_id.name
                    elif isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == 1:
                        self.env['fleet.repair.service.line'].sudo().browse(cmd[1]).write(cmd[2])
                        cleaned_cmds.append(cmd)
                    elif isinstance(cmd, (list, tuple)) and len(cmd) >= 2 and cmd[0] == 2:
                        self.env['fleet.repair.service.line'].sudo().browse(cmd[1]).unlink()
                    else:
                        cleaned_cmds.append(cmd)
            vals.pop('service_line_ids', None)

        if vals.get('product_id'):
            prod = self.env['product.product'].browse(vals['product_id'])
            if not vals.get('service_name'):
                vals['service_name'] = prod.name
            if not vals.get('service_line_id'):
                for rec in self:
                    if not rec.service_line_id:
                        job = self.env['fleet.repair'].browse(vals.get('job_id', rec.job_id.id)) if (vals.get('job_id') or rec.job_id) else False
                        emp_id = vals.get('employee_id') or rec.employee_id.id or self.env.context.get('default_employee_id')
                        if not emp_id and self.env.context.get('active_model') == 'hr.employee':
                            emp_id = self.env.context.get('active_id')
                        if job:
                            matching = job.service_line_ids.filtered(
                                lambda l: l.product_id.id == prod.id and (not l.employee_id or (emp_id and l.employee_id.id == emp_id))
                            )
                            if matching:
                                s_line = matching[0]
                                if emp_id and (not s_line.employee_id or s_line.employee_id.id != emp_id):
                                    s_line.sudo().write({'employee_id': emp_id})
                                vals['service_line_id'] = s_line.id
                            else:
                                emp = self.env['hr.employee'].browse(emp_id) if emp_id else False
                                if not emp and job.service_employee_id:
                                    emp = job.service_employee_id
                                if not emp:
                                    emp = self.env['hr.employee'].sudo().search([], limit=1)
                                dept = emp.department_id if (emp and emp.department_id) else (job.department_id if job else False)
                                if not dept:
                                    dept = self.env['hr.department'].search([('model_ids.model', '=', 'fleet.repair.service.line')], limit=1) or self.env['hr.department'].search([], limit=1)
                                s_line = self.env['fleet.repair.service.line'].with_context(skip_status_log_sync=True).sudo().create({
                                    'repair_id': job.id,
                                    'product_id': prod.id,
                                    'name': prod.name,
                                    'employee_id': emp.id,
                                    'department_id': dept.id if dept else False,
                                    'unit_price': prod.list_price or 200.0,
                                    'alloted_fru': vals.get('alloted_fru') or prod.alloted_fru or 0,
                                })
                                vals['service_line_id'] = s_line.id

        res = super().write(vals)

        if not self.env.context.get('skip_service_line_sync'):
            self._sync_to_service_line(vals)

        return res



    # Timer Fields for List View Stopwatch Widget
    timer_start = fields.Datetime('Start Timer')
    timer_end = fields.Datetime('End Timer')
    timer_last_start = fields.Datetime('Last Start Timer')
    is_timer_running = fields.Boolean('Timer Running', default=False)
    is_timer_paused = fields.Boolean('Timer Paused', default=False)
    accumulated_seconds = fields.Float('Accumulated Seconds', default=0.0)
    alloted_fru = fields.Integer(string='Alloted FRU', default=0)
    time_diff = fields.Float(
        string='Timer',
        compute='_compute_time_diff',
        store=True,
    )
    fru_status = fields.Selection(
        [('green', 'Normal'), ('yellow', 'Warning'), ('red', 'Overtime')],
        string='FRU Status',
        default='green',
    )

    @api.depends('timer_start', 'timer_end', 'is_timer_running', 'is_timer_paused', 'accumulated_seconds', 'timer_last_start')
    def _compute_time_diff(self):
        for rec in self:
            if rec.is_timer_running:
                # Timer field should only be populated once the timer is paused or stopped
                rec.time_diff = 0.0
            else:
                total_sec = rec.accumulated_seconds or 0.0
                rec.time_diff = total_sec / 3600.0

    @api.model
    def web_search_read(self, *args, **kwargs):
        domain = kwargs.get('domain') or (args[0] if args else None)
        emp_id = self.env.context.get('default_employee_id')
        if not emp_id and domain:
            for leaf in domain:
                if isinstance(leaf, (list, tuple)) and len(leaf) == 3 and leaf[0] == 'employee_id' and leaf[1] == '=':
                    emp_id = leaf[2]
                    break
        if emp_id:
            active_slines = self.env['fleet.repair.service.line'].search([
                ('employee_id', '=', emp_id),
                ('repair_id.state', 'not in', ['done', 'invoiced', 'cancel'])
            ])
            if active_slines:
                active_slines._sync_to_employee_status_log()
        return super().web_search_read(*args, **kwargs)

    @api.depends('accumulated_seconds', 'timer_last_start', 'is_timer_running', 'start_datetime', 'end_datetime', 'service_line_id')
    def _compute_duration(self):
        now = fields.Datetime.now()
        for rec in self:
            total_sec = rec.accumulated_seconds or 0.0
            if rec.is_timer_running and rec.timer_last_start:
                delta = now - rec.timer_last_start
                total_sec += delta.total_seconds()
            elif not total_sec and not rec.service_line_id:
                if rec.start_datetime and rec.end_datetime:
                    delta = rec.end_datetime - rec.start_datetime
                    total_sec = delta.total_seconds()
                elif rec.start_datetime:
                    delta = now - rec.start_datetime
                    total_sec = delta.total_seconds()
            rec.duration = total_sec / 3600.0

    def action_start_timer(self):
        """Starts or resumes timer on this work line."""
        self.ensure_one()
        # Rule check: Cannot start timer if another timer is already running for this employee
        running_other = self.env['hr.employee.status.log'].search([
            ('employee_id', '=', self.employee_id.id),
            ('id', '!=', self.id),
            ('is_timer_running', '=', True),
        ])
        if running_other:
            raise ValidationError(_("Let the previous work be over since its live and timer is running! Please pause the current timer first."))

        now = fields.Datetime.now()
        if not self.timer_start:
            self.timer_start = now
        self.timer_last_start = now
        self.is_timer_running = True
        self.is_timer_paused = False
        self.status = 'job'
        self.job_status = 'working'
        self.pause_reason = False
        if self.is_pause_running and self.pause_timer_start:
            delta = now - self.pause_timer_start
            self.pause_accumulated_seconds = (self.pause_accumulated_seconds or 0.0) + max(0, delta.total_seconds())
        self.is_pause_running = False
        self.pause_timer_start = False

        if self.service_line_id:
            if not self.service_line_id.is_timer_running:
                self.service_line_id.action_start_timer()

        # Close any open idle sessions for this employee
        open_idle = self.env['hr.employee.status.log'].search([
            ('employee_id', '=', self.employee_id.id),
            ('status', '=', 'idle'),
            ('end_datetime', '=', False),
        ])
        for ilog in open_idle:
            ilog.write({
                'end_datetime': now,
                'timer_end': now,
                'is_timer_running': False,
                'is_timer_paused': False,
            })

        self.employee_id.write({
            'work_status': 'job',
            'is_idle_running': False,
            'idle_reason': False,
            'idle_timer_start': False,
            'current_pause_reason': False,
            'current_job_id': self.job_id.id if self.job_id else False,
            'current_service_line_id': self.service_line_id.id if self.service_line_id else False,
            'current_status_start': self.timer_start or now,
        })
        self._compute_time_diff()
        self._compute_duration()
        return {
            'timer_start': fields.Datetime.to_string(self.timer_start) if self.timer_start else False,
            'timer_last_start': fields.Datetime.to_string(self.timer_last_start) if self.timer_last_start else False,
            'timer_end': False,
            'is_timer_running': True,
            'is_timer_paused': False,
            'accumulated_seconds': self.accumulated_seconds,
            'time_diff': self.time_diff,
            'duration': self.duration,
        }

    def action_reset_timer(self):
        """Resets timer on this line."""
        self.ensure_one()
        self.write({
            'timer_start': False,
            'timer_last_start': False,
            'timer_end': False,
            'is_timer_running': False,
            'is_timer_paused': False,
            'accumulated_seconds': 0.0,
            'time_diff': 0.0,
            'duration': 0.0,
            'fru_status': 'green',
        })
        if self.service_line_id:
            self.service_line_id.action_reset_timer()
        return {
            'timer_start': False,
            'timer_last_start': False,
            'timer_end': False,
            'is_timer_running': False,
            'is_timer_paused': False,
            'accumulated_seconds': 0.0,
            'time_diff': 0.0,
            'duration': 0.0,
            'fru_status': 'green',
        }

    def action_reset_all_employee_timers(self):
        """Resets all timers associated with this log and the employee:
        - Service line timers (worked hours, accumulated seconds, start/end dates)
        - Collective timer
        - Pause timer, pause duration, and pause reason
        - Employee's active service and idle timers
        """
        now = fields.Datetime.now()
        for rec in self:
            # 1. Reset all service lines linked to this log
            if rec.service_line_ids:
                rec.service_line_ids.action_reset_timer()
            if rec.service_line_id:
                rec.service_line_id.action_reset_timer()

            # Also reset any service lines on the job card assigned to this employee
            if rec.job_id and rec.employee_id:
                job_slines = rec.job_id.service_line_ids.filtered(
                    lambda l: l.employee_id.id == rec.employee_id.id
                )
                if job_slines:
                    job_slines.action_reset_timer()

            # 2. Reset collective and pause timers on the status log
            rec.write({
                'is_timer_running': False,
                'is_timer_paused': False,
                'timer_start': False,
                'timer_last_start': False,
                'timer_end': False,
                'accumulated_seconds': 0.0,
                'duration': 0.0,
                'time_diff': 0.0,
                'is_collective_timer_running': False,
                'collective_timer_last_start': False,
                'collective_accumulated_seconds': 0.0,
                'is_pause_running': False,
                'pause_timer_start': False,
                'pause_accumulated_seconds': 0.0,
                'pause_duration': 0.0,
                'pause_reason': False,
                'pause_notes': False,
                'start_datetime': now,
                'end_datetime': False,
                'status': 'assigned' if rec.job_id else 'idle',
                'job_status': 'assigned' if rec.job_id else False,
            })

            # 3. Reset employee's timers and idle state
            if rec.employee_id:
                emp = rec.employee_id
                emp.sudo().write({
                    'is_idle_running': False,
                    'idle_timer_start': False,
                    'idle_accumulated_seconds': 0.0,
                    'idle_reason': False,
                    'current_pause_reason': False,
                    'active_timer_last_start': False,
                    'active_timer_accumulated_seconds': 0.0,
                    'has_active_service_timer': False,
                    'work_status': 'assigned' if rec.job_id else 'idle',
                    'current_status_start': False,
                })

                # Close any lingering open idle logs for this employee
                open_idle = self.env['hr.employee.status.log'].search([
                    ('employee_id', '=', emp.id),
                    ('status', '=', 'idle'),
                    ('end_datetime', '=', False),
                    ('id', '!=', rec.id),
                ])
                open_idle.write({
                    'end_datetime': now,
                    'is_timer_running': False,
                    'is_timer_paused': False,
                })

            rec._compute_time_metrics()
            rec._compute_display_status()
        return True

    def action_reset_to_assigned(self, reset_worked_hours=False):
        """Resets the status of this job/log and the employee back to 'Assigned'."""
        now = fields.Datetime.now()
        for rec in self:
            # 1. Stop any running service line timers (and optionally reset hours)
            for sline in rec.service_line_ids:
                if reset_worked_hours:
                    sline.action_reset_timer()
                else:
                    if sline.is_timer_running:
                        if sline.timer_last_start:
                            delta = now - sline.timer_last_start
                            sline.accumulated_seconds += delta.total_seconds()
                        sline.write({
                            'timer_last_start': False,
                            'is_timer_running': False,
                            'is_timer_paused': False,
                        })
                        sline._compute_time_diff()

            # 2. Reset log status back to assigned and clear pause state
            vals = {
                'status': 'assigned',
                'job_status': 'assigned',
                'is_timer_running': False,
                'is_timer_paused': False,
                'is_collective_timer_running': False,
                'collective_timer_last_start': False,
                'is_pause_running': False,
                'pause_timer_start': False,
                'pause_reason': False,
                'pause_notes': False,
                'end_datetime': False,
            }
            if reset_worked_hours:
                vals.update({
                    'timer_start': False,
                    'timer_last_start': False,
                    'timer_end': False,
                    'accumulated_seconds': 0.0,
                    'duration': 0.0,
                    'time_diff': 0.0,
                    'pause_accumulated_seconds': 0.0,
                    'pause_duration': 0.0,
                    'collective_accumulated_seconds': 0.0,
                    'start_datetime': now,
                })
            rec.write(vals)

            # 3. Update employee work status back to assigned
            if rec.employee_id:
                emp_vals = {
                    'work_status': 'assigned',
                    'current_pause_reason': False,
                    'has_active_service_timer': False,
                    'active_timer_last_start': False,
                    'current_status_start': now,
                }
                if reset_worked_hours:
                    emp_vals.update({
                        'active_timer_accumulated_seconds': 0.0,
                    })
                rec.employee_id.sudo().write(emp_vals)

            rec._compute_time_metrics()
            rec._compute_display_status()
        return True

    def action_pause_timer(self):
        """Pauses timer on this work line."""
        self.ensure_one()
        now = fields.Datetime.now()
        if self.is_timer_running and self.timer_last_start:
            delta = now - self.timer_last_start
            self.accumulated_seconds += delta.total_seconds()
        self.timer_last_start = False
        self.is_timer_running = False
        self.is_timer_paused = True
        self.status = 'paused'
        self.job_status = 'paused'

        if self.service_line_id and self.service_line_id.is_timer_running:
            self.service_line_id.with_context(skip_status_wizard=True).action_pause_timer()

        if self.employee_id:
            self.employee_id.sudo().write({
                'work_status': 'paused',
                'current_pause_reason': self.pause_reason or False,
            })

        self._compute_time_diff()
        self._compute_duration()
        result = {
            'timer_start': fields.Datetime.to_string(self.timer_start) if self.timer_start else False,
            'timer_last_start': False,
            'timer_end': fields.Datetime.to_string(self.timer_end) if self.timer_end else False,
            'is_timer_running': False,
            'is_timer_paused': True,
            'accumulated_seconds': self.accumulated_seconds,
            'time_diff': self.time_diff,
            'duration': self.duration,
        }
        return result

    def action_stop_timer(self):
        """Stops/completes timer on this line."""
        self.ensure_one()
        now = fields.Datetime.now()
        if self.is_timer_running and self.timer_last_start:
            delta = now - self.timer_last_start
            self.accumulated_seconds += delta.total_seconds()
        self.timer_last_start = False
        self.timer_end = now
        self.end_datetime = now
        self.is_timer_running = False
        self.is_timer_paused = False

        if self.service_line_id and self.service_line_id.is_timer_running:
            self.service_line_id.with_context(skip_status_wizard=True).action_stop_timer()

        self._compute_time_diff()
        self._compute_duration()
        result = {
            'timer_start': fields.Datetime.to_string(self.timer_start) if self.timer_start else False,
            'timer_last_start': False,
            'timer_end': fields.Datetime.to_string(self.timer_end) if self.timer_end else False,
            'is_timer_running': False,
            'is_timer_paused': False,
            'accumulated_seconds': self.accumulated_seconds,
            'time_diff': self.time_diff,
            'duration': self.duration,
        }
        return result

    def action_open_repair_order(self):
        """Opens Job Card related to this work line."""
        self.ensure_one()
        if not self.job_id:
            raise UserError(_("No Job Card associated with this line."))
        return {
            'name': _('Job Card'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.repair',
            'res_id': self.job_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _resolve_employee_from_context(self, *args, **kwargs):
        """Resolves target hr.employee from context, self records, active_id, or args."""
        emp_id = self.env.context.get('default_employee_id')
        if emp_id:
            emp = self.env['hr.employee'].browse(emp_id).exists()
            if emp:
                return emp

        # Check self (recordset)
        if self:
            for rec in self:
                if hasattr(rec, 'employee_id') and rec.employee_id:
                    return rec.employee_id

        # Check args (e.g. if passed as args=[[5]] or args=[5])
        if args:
            raw_ids = args[0]
            if isinstance(raw_ids, (list, tuple)) and raw_ids:
                logs = self.browse(raw_ids).exists()
                for log in logs:
                    if log.employee_id:
                        return log.employee_id
            elif isinstance(raw_ids, int):
                log = self.browse(raw_ids).exists()
                if log and log.employee_id:
                    return log.employee_id

        active_id = self.env.context.get('active_id')
        active_model = self.env.context.get('active_model')
        if active_id:
            if active_model == 'hr.employee':
                emp = self.env['hr.employee'].browse(active_id).exists()
                if emp:
                    return emp
            else:
                log = self.browse(active_id).exists()
                if log and log.employee_id:
                    return log.employee_id

        active_ids = self.env.context.get('active_ids')
        if active_ids:
            if active_model == 'hr.employee':
                emp = self.env['hr.employee'].browse(active_ids[0]).exists()
                if emp:
                    return emp
            else:
                logs = self.browse(active_ids).exists()
                for log in logs:
                    if log.employee_id:
                        return log.employee_id

        domain = self.env.context.get('active_domain') or []
        if isinstance(domain, list):
            for leaf in domain:
                if isinstance(leaf, (list, tuple)) and len(leaf) == 3 and leaf[0] == 'employee_id' and leaf[1] == '=':
                    emp = self.env['hr.employee'].browse(leaf[2]).exists()
                    if emp:
                        return emp

        current_emp = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        if current_emp:
            return current_emp
        return self.env['hr.employee']

    def action_open_status_wizard_for_employee(self, *args, **kwargs):
        """Opens wizard from list view header."""
        emp = self._resolve_employee_from_context(*args, **kwargs)
        if not emp:
            raise UserError(_("No employee selected."))
        return emp.action_open_status_wizard()

    def action_open_idle_wizard_for_employee(self, *args, **kwargs):
        """Opens Idle wizard from list view header."""
        emp = self._resolve_employee_from_context(*args, **kwargs)
        if not emp:
            raise UserError(_("No employee selected."))
        return emp.action_open_idle_wizard()

    def action_open_idle_wizard(self, *args, **kwargs):
        """Opens Idle wizard from record or list view row."""
        return self.action_open_idle_wizard_for_employee(*args, **kwargs)

    def unlink(self):
        """When work status logs are deleted, pause any running service timers,
        unlink linked job card service lines, and sync employee status."""
        employees = self.mapped('employee_id')
        if not self.env.context.get('skip_status_log_sync') and not self.env.context.get('skip_service_line_sync'):
            service_lines = self.mapped('service_line_id').filtered(lambda l: l.is_timer_running)
            for sline in service_lines:
                sline.with_context(skip_status_wizard=True, skip_status_log_sync=True).action_pause_timer()

        sline_ids = [rec.service_line_id.id for rec in self if rec.service_line_id]

        res = super().unlink()

        if sline_ids and not self.env.context.get('skip_service_line_sync') and not self.env.context.get('skip_status_log_sync'):
            for s_id in set(sline_ids):
                other_logs = self.sudo().search([('service_line_id', '=', s_id)])
                if not other_logs:
                    sline = self.env['fleet.repair.service.line'].sudo().browse(s_id).exists()
                    if sline:
                        sline.with_context(skip_status_log_sync=True, skip_service_line_sync=True).unlink()

        for emp in employees:
            remaining_active = self.search([
                ('employee_id', '=', emp.id),
                ('end_datetime', '=', False)
            ], order='start_datetime desc, id desc', limit=1)
            if remaining_active:
                emp.write({
                    'work_status': remaining_active.status,
                    'current_job_id': remaining_active.job_id.id if remaining_active.job_id else False,
                    'current_service_line_id': remaining_active.service_line_id.id if remaining_active.service_line_id else False,
                    'current_status_start': remaining_active.timer_start or remaining_active.start_datetime or fields.Datetime.now(),
                    'status_notes': remaining_active.notes or False,
                })
            else:
                running_slines = self.env['fleet.repair.service.line'].search([
                    ('employee_id', '=', emp.id),
                    ('is_timer_running', '=', True)
                ])
                for rline in running_slines:
                    rline.with_context(skip_status_wizard=True).action_pause_timer()

                emp.write({
                    'work_status': 'idle',
                    'current_job_id': False,
                    'current_service_line_id': False,
                    'current_status_start': False,
                    'status_notes': False,
                })
        return res

