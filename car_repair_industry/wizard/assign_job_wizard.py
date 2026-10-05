# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class AssignJobWizard(models.TransientModel):
    _name = 'assign.job.wizard'
    _description = 'Assign Job & Manage Employee Status'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    team_lead_id = fields.Many2one(
        'res.users',
        string='Team Lead',
        compute='_compute_team_lead_id',
        store=True,
        readonly=False
    )
    status = fields.Selection([
        ('job', 'Active Job'),
        ('assigned', 'Assigned'),
        ('waiting_car', 'Waiting for Car'),
        ('parts_unavailable', 'Parts Arrival / Not Available'),
        ('tools_issue', 'Tools Issue'),
        ('approval_pending', 'Customer Approval Pending'),
        ('idle', 'Idle')
    ], string='Status', required=True, default='job')

    repair_id = fields.Many2one(
        'fleet.repair',
        string='Job Card',
        domain="['|', ('id', '=', repair_id), '&', ('state', 'not in', ['done', 'invoiced', 'cancel']), ('team_lead_id', '=', team_lead_id)]"
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='employee_id.department_id',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Service',
        domain="[('type', '=', 'service'), '|', ('department_id', '=', False), ('department_id', '=', department_id)]",
    )
    service_line_id = fields.Many2one(
        'fleet.repair.service.line',
        string='Service Line',
    )
    notes = fields.Text(string='Notes / Downtime Reason')

    # Active Service Lines & Timer Information for the Employee
    active_service_line_ids = fields.Many2many(
        'fleet.repair.service.line',
        string='Active Service Lines',
        compute='_compute_active_service_info'
    )
    has_active_timer = fields.Boolean(
        string='Has Active Timer',
        compute='_compute_active_service_info'
    )
    active_timer_job_name = fields.Char(
        string='Active Job Card Name',
        compute='_compute_active_service_info'
    )
    active_timer_service_name = fields.Char(
        string='Active Service Name',
        compute='_compute_active_service_info'
    )
    timer_start = fields.Datetime(
        string='Timer Start',
        compute='_compute_active_service_info'
    )
    timer_last_start = fields.Datetime(
        string='Timer Last Start',
        compute='_compute_active_service_info'
    )
    timer_end = fields.Datetime(
        string='Timer End',
        compute='_compute_active_service_info'
    )
    is_timer_running = fields.Boolean(
        string='Timer Running',
        compute='_compute_active_service_info'
    )
    is_timer_paused = fields.Boolean(
        string='Timer Paused',
        compute='_compute_active_service_info'
    )
    accumulated_seconds = fields.Float(
        string='Accumulated Seconds',
        compute='_compute_active_service_info'
    )
    alloted_fru = fields.Integer(
        string='Alloted FRU',
        compute='_compute_active_service_info'
    )
    time_diff = fields.Float(
        string='Active Timer',
        compute='_compute_active_service_info'
    )
    active_timer_display = fields.Char(
        string='Current Active Timer',
        compute='_compute_active_service_info'
    )
    status_duration_info = fields.Char(
        string='Status Duration Info',
        compute='_compute_active_service_info'
    )

    @api.depends('employee_id')
    def _compute_active_service_info(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.employee_id:
                # Find all service lines assigned to this employee on active (open) Job Cards
                lines = self.env['fleet.repair.service.line'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('repair_id.state', 'not in', ['done', 'invoiced', 'cancel'])
                ], order='is_timer_running desc, id desc')
                rec.active_service_line_ids = [(6, 0, lines.ids)]

                # Check if any service line has an active running timer
                running_lines = lines.filtered(lambda l: l.is_timer_running)
                if running_lines:
                    rline = running_lines[0]
                    rec.has_active_timer = True
                    rec.is_timer_running = True
                    rec.is_timer_paused = False
                    rec.timer_start = rline.timer_start
                    rec.timer_last_start = rline.timer_last_start
                    rec.timer_end = False
                    rec.accumulated_seconds = rline.accumulated_seconds or 0.0
                    rec.alloted_fru = rline.alloted_fru or 0
                    rec.active_timer_job_name = rline.repair_id.sequence or rline.repair_id.name or f"JC #{rline.repair_id.id}"
                    rec.active_timer_service_name = rline.product_id.name if rline.product_id else (rline.name or '')

                    total_sec = rec.accumulated_seconds
                    if rline.timer_last_start:
                        total_sec += (now - rline.timer_last_start).total_seconds()
                    rec.time_diff = round(total_sec / 3600.0, 4)

                    hours = int(total_sec // 3600)
                    minutes = int((total_sec % 3600) // 60)
                    seconds = int(total_sec % 60)
                    rec.active_timer_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    rec.status_duration_info = False
                else:
                    rec.has_active_timer = False
                    rec.is_timer_running = False
                    rec.is_timer_paused = False
                    rec.timer_start = False
                    rec.timer_last_start = False
                    rec.timer_end = False
                    rec.accumulated_seconds = 0.0
                    rec.alloted_fru = 0
                    rec.time_diff = 0.0
                    rec.active_timer_job_name = False
                    rec.active_timer_service_name = False
                    rec.active_timer_display = "No Active Timer"
                    if rec.employee_id.current_status_start:
                        delta = now - rec.employee_id.current_status_start
                        duration_hrs = round(delta.total_seconds() / 3600.0, 2)
                        status_label = dict(rec.employee_id._fields['work_status'].selection).get(rec.employee_id.work_status, 'Idle')
                        rec.status_duration_info = f"{status_label} for {duration_hrs} hrs"
                    else:
                        rec.status_duration_info = False
            else:
                rec.active_service_line_ids = [(5, 0, 0)]
                rec.has_active_timer = False
                rec.is_timer_running = False
                rec.is_timer_paused = False
                rec.timer_start = False
                rec.timer_last_start = False
                rec.timer_end = False
                rec.accumulated_seconds = 0.0
                rec.alloted_fru = 0
                rec.time_diff = 0.0
                rec.active_timer_job_name = False
                rec.active_timer_service_name = False
                rec.active_timer_display = ""
                rec.status_duration_info = False

    @api.depends('employee_id')
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

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        emp_id = res.get('employee_id') or self.env.context.get('default_employee_id')
        if emp_id:
            emp = self.env['hr.employee'].browse(emp_id)
            if not res.get('repair_id') and not self.env.context.get('default_repair_id'):
                if emp.current_job_id and emp.current_job_id.state not in ['done', 'invoiced', 'cancel']:
                    res['repair_id'] = emp.current_job_id.id
                else:
                    running = self.env['fleet.repair.service.line'].search([
                        ('employee_id', '=', emp.id),
                        ('repair_id.state', 'not in', ['done', 'invoiced', 'cancel'])
                    ], order='is_timer_running desc, id desc', limit=1)
                    if running:
                        res['repair_id'] = running.repair_id.id
                        if not res.get('service_line_id') and not self.env.context.get('default_service_line_id'):
                            res['service_line_id'] = running.id

            if not res.get('service_line_id') and not self.env.context.get('default_service_line_id'):
                if emp.current_service_line_id:
                    res['service_line_id'] = emp.current_service_line_id.id
        return res

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
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

        if self.employee_id:
            if not self.repair_id:
                ctx_repair = self.env.context.get('default_repair_id')
                if ctx_repair:
                    self.repair_id = ctx_repair
                elif self.employee_id.current_job_id and self.employee_id.current_job_id.state not in ['done', 'invoiced', 'cancel']:
                    self.repair_id = self.employee_id.current_job_id
                else:
                    running = self.env['fleet.repair.service.line'].search([
                        ('employee_id', '=', self.employee_id.id),
                        ('repair_id.state', 'not in', ['done', 'invoiced', 'cancel'])
                    ], order='is_timer_running desc, id desc', limit=1)
                    if running:
                        self.repair_id = running.repair_id
                        if not self.service_line_id:
                            self.service_line_id = running
            if not self.service_line_id:
                ctx_sline = self.env.context.get('default_service_line_id')
                if ctx_sline:
                    self.service_line_id = ctx_sline
                elif self.employee_id.current_service_line_id:
                    self.service_line_id = self.employee_id.current_service_line_id
        else:
            self.repair_id = False
            self.service_line_id = False

    @api.onchange('product_id', 'repair_id')
    def _onchange_product_id(self):
        if self.product_id and self.repair_id:
            matching = self.repair_id.service_line_ids.filtered(
                lambda l: l.product_id == self.product_id and (not l.employee_id or l.employee_id == self.employee_id)
            )
            self.service_line_id = matching[0] if matching else False
        elif not self.product_id:
            self.service_line_id = False

    @api.onchange('repair_id')
    def _onchange_repair_id(self):
        if self.repair_id and self.employee_id:
            emp_lines = self.env['fleet.repair.service.line'].search([
                ('repair_id', '=', self.repair_id.id),
                ('employee_id', '=', self.employee_id.id)
            ])
            if emp_lines and (not self.service_line_id or self.service_line_id not in emp_lines):
                self.service_line_id = emp_lines[0]
                if emp_lines[0].product_id:
                    self.product_id = emp_lines[0].product_id
        elif self.service_line_id and self.service_line_id.repair_id != self.repair_id:
            self.service_line_id = False
            self.product_id = False

    def action_open_job_card(self):
        self.ensure_one()
        if not self.repair_id:
            raise UserError(_("Please select a Job Card first."))
        if self.status:
            self.employee_id.action_set_status(
                new_status=self.status,
                job_id=self.repair_id.id,
                service_line_id=self.service_line_id.id if self.service_line_id else False,
                product_id=self.product_id.id if self.product_id else False,
                notes=self.notes
            )
        return {
            'name': _('Job Card'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.repair',
            'res_id': self.repair_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_apply_status(self):
        self.ensure_one()
        if self.status == 'job':
            if not self.repair_id:
                raise UserError(_("Please select a Job Card to assign the technician."))
            if not self.product_id and not self.service_line_id:
                raise UserError(_("Please select a Service to assign."))

            # Rule: check if employee already has an active running timer
            domain = [
                ('employee_id', '=', self.employee_id.id),
                ('is_timer_running', '=', True),
                ('repair_id.state', 'not in', ['done', 'invoiced', 'cancel'])
            ]
            if self.service_line_id:
                domain.append(('id', '!=', self.service_line_id.id))
            running_lines = self.env['fleet.repair.service.line'].search(domain)
            if running_lines:
                raise ValidationError(_("Let the previous work be over since its live and timer is running! Please pause the current timer first before assigning a new job."))

        target_repair_id = self.repair_id.id if self.repair_id else False
        target_sline_id = self.service_line_id.id if self.service_line_id else False
        target_product_id = self.product_id.id if self.product_id else False

        # If not idle and not provided, fallback to employee's current job/service
        if self.status != 'idle':
            if not target_sline_id and self.employee_id.current_service_line_id:
                target_sline_id = self.employee_id.current_service_line_id.id
            if not target_repair_id and target_sline_id:
                sline_rec = self.env['fleet.repair.service.line'].browse(target_sline_id)
                target_repair_id = sline_rec.repair_id.id if sline_rec.repair_id else False
            if not target_repair_id and self.employee_id.current_job_id:
                target_repair_id = self.employee_id.current_job_id.id

        self.employee_id.action_set_status(
            new_status=self.status,
            job_id=target_repair_id,
            service_line_id=target_sline_id,
            product_id=target_product_id,
            notes=self.notes
        )
        return {'type': 'ir.actions.act_window_close'}

