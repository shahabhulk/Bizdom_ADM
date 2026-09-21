# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from datetime import date, time, datetime
from odoo import tools
from pytz import timezone
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, SQL
import re
import logging

_logger = logging.getLogger(__name__)


class FleetRepair(models.Model):
    _name = 'fleet.repair'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Car Repair"
    _rec_name = 'sequence'
    _order = 'id desc'

    license_plate = fields.Many2one(
        'fleet.vehicle',
        string='License Plate',
        store=True,
        readonly=False,
        required=True,
        help='License plate number / vehicle selection.')

    def _auto_init(self):
        cr = self.env.cr
        cr.execute("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'fleet_repair' AND column_name = 'license_plate'
        """)
        res = cr.fetchone()
        if res and res[0] in ('character varying', 'text', 'varchar'):
            # Match existing string license plates to fleet_vehicle IDs
            cr.execute("""
                UPDATE fleet_repair fr
                SET license_plate = (
                    SELECT fv.id::text 
                    FROM fleet_vehicle fv 
                    WHERE LOWER(fv.license_plate) = LOWER(fr.license_plate) 
                    ORDER BY fv.id DESC LIMIT 1
                )
                WHERE fr.license_plate IS NOT NULL 
                AND fr.license_plate !~ '^[0-9]+$';
            """)
            # Clear any remaining non-numeric string values
            cr.execute("""
                UPDATE fleet_repair 
                SET license_plate = NULL 
                WHERE license_plate IS NOT NULL AND license_plate !~ '^[0-9]+$';
            """)
            # Convert column type to integer
            cr.execute("""
                ALTER TABLE fleet_repair 
                ALTER COLUMN license_plate TYPE integer 
                USING (
                    CASE 
                        WHEN license_plate ~ '^[0-9]+$' THEN license_plate::integer 
                        ELSE NULL 
                    END
                );
            """)

        cr.execute("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'fleet_repair' AND column_name = 'promised_date'
        """)
        res_promised = cr.fetchone()
        if res_promised and res_promised[0] in ('timestamp without time zone', 'timestamp'):
            cr.execute("""
                ALTER TABLE fleet_repair 
                ALTER COLUMN promised_date TYPE date 
                USING promised_date::date;
            """)

        super()._auto_init()
    vin_sn = fields.Char(
        string='Chassis Number',
        store=True,
        readonly=False,
        required=True,
        help='VIN/Chassis number. Will create or update fleet.vehicle when entered.')

    model_name = fields.Many2one(
        'fleet.vehicle.model',
        string="Model",
        domain="[('brand_id', '=', fleet_id)]",
        store=True,
        required=True
    )

    kilometers_num = fields.Char(string="KMS", required=True)
    name = fields.Char(string='Subject')
    sequence = fields.Char(string='Sequence', readonly=True, copy=False)
    client_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    client_phone = fields.Char(related='client_id.phone', store=True, readonly=False, string='Phone',
                               inverse='_inverse_client_phone', required=True)
    client_mobile = fields.Char(related='client_id.mobile', store=True, readonly=False, string='Mobile',
                                inverse='_inverse_client_phone')
    client_email = fields.Char(related='client_id.email', store=True, readonly=False, string='Email',
                               inverse='_inverse_client_email', required=True)
    client_address = fields.Char(related='client_id.contact_address', store=True, readonly=False, string='Address',
                                 inverse='_inverse_client_address')
    receipt_date = fields.Datetime(string='JC Date', default=fields.Datetime.now, readonly=True)
    contact_name = fields.Char(string='Contact Name')
    phone = fields.Char(string='Contact Number')
    fleet_id = fields.Many2one('fleet.vehicle.model.brand', 'Car', required=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle')
    # license_plate = fields.Char('License Plate', help='License plate number of the vehicle (ie: plate number for a car)')
    # vin_sn = fields.Char('Chassis Number', help='Unique number written on the vehicle motor (VIN/SN number)')
    model_id = fields.Many2one('fleet.vehicle.model', 'Model', help='Model of the vehicle')
    fuel_type = fields.Selection([('diesel', 'Diesel'),
                                  ('gasoline', 'Gasoline'),
                                  ('full_hybrid', 'Full Hybrid'),
                                  ('plug_in_hybrid_diesel', 'Plug-in Hybrid Diesel'),
                                  ('plug_in_hybrid_gasoline', 'Plug-in Hybrid Gasoline'),
                                  ('cng', 'CNG'),
                                  ('lpg', 'LPG'),
                                  ('hydrogen', 'Hydrogen'),
                                  ('electric', 'Electric'), ('hybrid', 'Hybrid')], 'Fuel Type',
                                 help='Fuel Used by the vehicle')
    guarantee = fields.Selection(
        [('yes', 'Yes'), ('no', 'No')], string='Under Guarantee?')
    guarantee_type = fields.Selection(
        [('paid', 'paid'), ('free', 'Free')], string='Guarantee Type')
    service_type = fields.Many2one('service.type', string='Nature of Service')
    user_id = fields.Many2one('res.users', string='Service Advisor', required=True, tracking=True)
    priority = fields.Selection([('0', 'Low'), ('1', 'Normal'), ('2', 'High')], 'Priority')
    description = fields.Text(string='Notes')
    service_detail = fields.Text(string='Repair Details')
    state = fields.Selection([
        ('draft', 'Received'),
        ('diagnosis', 'In Diagnosis'),
        ('diagnosis_complete', 'Diagnosis Complete'),
        ('quote', 'Quotation Sent'),
        ('saleorder', 'Quotation Approved'),
        ('workorder', 'Work in Progress'),
        ('work_completed', 'Work Completed'),
        ('invoiced', 'Invoiced'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], 'Status', default="draft", readonly=False, copy=False, help="Gives the status of the fleet repairing.",
        index=True, tracking=False)
    diagnose_id = fields.Many2one('fleet.diagnose', string='Car Diagnose', copy=False)
    workorder_id = fields.Many2one('fleet.workorder', string='Car Work Order', copy=False)
    sale_order_id = fields.Many2one('sale.order', string='Sales Order', copy=False)
    invoice_order_id = fields.Many2one('account.move', copy=False)
    fleet_repair_line = fields.One2many('fleet.repair.line', 'fleet_repair_id', string="Car Lines")
    service_detail_line = fields.One2many('service.detail.line', 'service_detail_id', string='Service Lines')
    workorder_count = fields.Integer(string='Work Orders', compute='_compute_workorder_id')
    dig_count = fields.Integer(string='Diagnosis Orders', compute='_compute_dignosis_id')
    quotation_count = fields.Integer(string="Quotations", compute='_compute_quotation_id')
    saleorder_count = fields.Integer(string="Sale Order", compute='_compute_saleorder_id')
    inv_count = fields.Integer(string="Invoice", compute='_compute_inv_count')
    confirm_sale_order = fields.Boolean('is confirm')
    images_ids = fields.One2many('ir.attachment', 'car_repair_id', 'Images')
    parent_id = fields.Many2one('fleet.repair', string='Parent Repair', index=True)

    child_ids = fields.One2many('fleet.repair', 'parent_id', string="Sub-Repair")

    repair_checklist_ids = fields.Many2many('fleet.repair.checklist', 'checkbox_checklist_rel',
                                            'id', 'checklist_id',
                                            string='Repair Checklist')
    client_description = fields.Char(string="Notes")
    rating = fields.Selection([('0', 'Low'), ('1', 'Normal'), ('2', 'High')], string="Rating")
    timesheet_ids = fields.One2many('account.analytic.line', 'repair_id', string="Timesheet")
    fleet_work_line_ids = fields.One2many('fleet.repair.work.line', 'repair_id', string="Work Lines")
    planned_hours = fields.Float("Initially Planned Hours", tracking=True)
    subtask_planned_hours = fields.Float("Sub-tasks Planned Hours", compute='_compute_subtask_planned_hours',
                                         help="Sum of the hours allocated for all the sub-tasks (and their own sub-tasks) linked to this task. Usually less than or equal to the allocated hours of this task.")

    job_card_display = fields.Char(
        string='Job Card',
        compute='_compute_job_card_display',
        store=False
    )

    product_line_ids = fields.One2many('fleet.repair.product.line', 'repair_id', string='Product Lines')
    service_line_ids = fields.One2many('fleet.repair.service.line', 'repair_id', string='Service Lines')
    # amount_total = fields.Monetary(string="Total Amount", compute="_compute_amount_total", store=True)
    # currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    amount_parts = fields.Monetary(string='Parts Total', compute='_compute_total', store=True)
    amount_service = fields.Monetary(string='Service Total', compute='_compute_total', store=True)
    amount_untaxed = fields.Monetary(string='Untaxed Amount', compute='_compute_total', store=True)
    amount_total = fields.Monetary(string='Total', compute='_compute_total', store=True)
    invoice_paid_amount = fields.Monetary(
        string='Paid Amount',
        currency_field='currency_id',
        compute='_compute_invoice_paid_amount',
    )
    company_id = fields.Many2one('res.company', store=True, copy=False,
                                 string="Company",
                                 default=lambda self: self.env.user.company_id.id)
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",

        related='company_id.currency_id',
        store=True,
        readonly=True
    )

    promised_date = fields.Date(string="Promised Date", required=True)
    # csat_rating = fields.Selection(
    #     [
    #         ("0", "No comments"),
    #         ("1", "Very Unsatisfied"),
    #         ("2", "Unsatisfied"),
    #         ("3", "Neutral"),
    #         ("4", "Satisfied"),
    #         ("5", "Very Satisfied"),
    #     ],
    #     string="Customer Satisfaction",
    #     default="0",
    # )

    # This field will control the decoration color
    delivery_status_color = fields.Selection([
        ('green', 'Delivered'),
        ('yellow', 'On Track'),
        ('red', 'Delayed')
    ], compute="_compute_delivery_status_color", store=True, string="Signal")
    project_id = fields.Many2one('project.project', string='Project', copy=False, readonly=True)

    service_employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        compute='_compute_service_employee_id',
        store=True,
    )

    @api.depends('service_line_ids.employee_id', 'service_line_ids.is_timer_running')
    def _compute_service_employee_id(self):
        for rec in self:
            active_line = rec.service_line_ids.filtered(lambda l: l.is_timer_running and l.employee_id)
            if active_line:
                rec.service_employee_id = active_line[0].employee_id
            else:
                first_emp = False
                for line in rec.service_line_ids:
                    if line.employee_id:
                        first_emp = line.employee_id
                        break
                rec.service_employee_id = first_emp

    active_service_employee_ids = fields.Many2many(
        'hr.employee',
        'fleet_repair_active_service_employee_rel',
        'repair_id',
        'employee_id',
        string='Active Technicians',
        compute='_compute_active_service_info',
        store=True,
    )
    has_active_service_timer = fields.Boolean(
        string='Active Timer Running',
        compute='_compute_active_service_info',
        store=True,
    )
    active_service_timer_last_start = fields.Datetime(
        string='Active Timer Start',
        compute='_compute_active_service_info',
        store=True,
    )
    active_service_accumulated_seconds = fields.Float(
        string='Active Accumulated Seconds',
        compute='_compute_active_service_info',
        store=True,
    )
    active_service_time_diff = fields.Float(
        string='Active Duration',
        compute='_compute_active_service_info',
        store=True,
    )
    active_service_fru = fields.Float(
        string='Active Service FRU',
        compute='_compute_active_service_info',
        store=True,
    )
    active_service_unit_price = fields.Float(
        string='Active Service Price',
        compute='_compute_active_service_info',
        store=True,
    )
    active_service_fru_status = fields.Selection(
        [('green', 'Normal'), ('yellow', 'Warning'), ('red', 'Overtime')],
        string='Active Service FRU Status',
        compute='_compute_active_service_info',
        store=True,
        default='green',
    )
    total_service_fru = fields.Float(
        string='Total Service FRU',
        compute='_compute_active_service_info',
        store=True,
    )
    wip_fru_status = fields.Selection(
        [('green', 'Normal'), ('yellow', 'Warning'), ('red', 'Overtime')],
        string='WIP FRU Status',
        compute='_compute_active_service_info',
        store=True,
        default='green',
    )

    @api.depends(
        'service_line_ids.is_timer_running',
        'service_line_ids.employee_id',
        'service_line_ids.accumulated_seconds',
        'service_line_ids.timer_last_start',
        'service_line_ids.time_diff',
        'service_line_ids.alloted_fru',
        'service_line_ids.quantity',
        'service_line_ids.unit_price',
        'service_line_ids.fru_status',
    )
    def _compute_active_service_info(self):
        for rec in self:
            active_lines = rec.service_line_ids.filtered(lambda l: l.is_timer_running)
            if active_lines:
                rec.active_service_employee_ids = [(6, 0, active_lines.mapped('employee_id').ids)]
                rec.has_active_service_timer = True

                primary_lines = rec.service_line_ids.filtered(lambda l: l.is_timer_running and l.employee_id == rec.service_employee_id)
                active_line = primary_lines[0] if primary_lines else active_lines[0]

                rec.active_service_timer_last_start = active_line.timer_last_start
                rec.active_service_accumulated_seconds = active_line.accumulated_seconds or 0.0
                rec.active_service_time_diff = active_line.time_diff or 0.0
                rec.active_service_fru = float(active_line.alloted_fru or 0)
                rec.active_service_unit_price = float(active_line.unit_price or 0.0)
                rec.active_service_fru_status = active_line.fru_status or 'green'
            else:
                rec.active_service_employee_ids = [(5, 0, 0)]
                rec.has_active_service_timer = False
                rec.active_service_timer_last_start = False
                rec.active_service_accumulated_seconds = 0.0
                rec.active_service_time_diff = 0.0
                rec.active_service_fru = 0.0
                rec.active_service_unit_price = 0.0
                rec.active_service_fru_status = 'green'

            # 1 FRU = 5 minutes = 300 seconds = 200 rs
            total_fru = sum(
                (line.alloted_fru if (line.alloted_fru and line.alloted_fru > 0) else ((line.unit_price or 0.0) / 200.0))
                for line in rec.service_line_ids
            )
            rec.total_service_fru = total_fru
            fru_seconds = total_fru * 300.0

            if any(l.fru_status == 'red' for l in rec.service_line_ids):
                rec.wip_fru_status = 'red'
            elif any(l.fru_status == 'yellow' for l in rec.service_line_ids):
                rec.wip_fru_status = 'yellow'
            else:
                rec.wip_fru_status = 'green'

    # def write(self, vals):
    #     # First call the original write method
    #     res = super().write(vals)
    #     print("helllloosojojsodji")
    #     # Only proceed if we're updating specific records (not creating)
    #     if self and not self._context.get('skip_project_creation'):
    #         Project = self.env['project.project']
    #         for repair in self:
    #             # Only create project if sequence is set and no project exists
    #             if not repair.project_id and repair.sequence:
    #                 project_vals = {
    #                     'name': f"Job Card No: {repair.sequence}",
    #                     'allow_timesheets': True,
    #                     'partner_id': repair.client_id.id if repair.client_id else False,
    #                 }
    #                 # Use with_context to prevent recursion
    #                 repair.with_context(skip_project_creation=True).write({
    #                     'project_id': Project.create(project_vals).id
    #                 })
    #     return res

    @api.onchange('license_plate')
    def _onchange_license_plate(self):
        car = self.license_plate
        warning = {}
        if car:
            self.vehicle_id = car
            self.vin_sn = car.vin_sn or False

            if car.driver_id:
                self.client_id = car.driver_id
                self.client_email = car.driver_id.email or False
                self.client_phone = car.driver_id.phone or False
                self.client_mobile = car.driver_id.mobile or False
                self.client_address = car.driver_id.contact_address or False

            if car.model_id:
                self.model_name = car.model_id
                self.fleet_id = car.model_id.brand_id or False
            else:
                self.model_name = False
                self.fleet_id = False

            if hasattr(car, 'odometer') and car.odometer:
                self.kilometers_num = str(car.odometer)
            else:
                self.kilometers_num = False

            # Check if active job card exists for warning
            domain = [
                ('state', 'not in', ['done', 'cancel']),
            ]
            if self._origin and self._origin.id:
                domain.append(('id', '!=', self._origin.id))

            plate_name = car.license_plate
            if plate_name:
                domain.extend([
                    '|',
                    ('license_plate', '=', car.id),
                    ('license_plate.license_plate', '=ilike', plate_name.strip())
                ])
            else:
                domain.append(('license_plate', '=', car.id))

            existing_repairs = self.search(domain)
            for existing in existing_repairs:
                invoice_posted = False
                if existing.invoice_order_id and existing.invoice_order_id.state == 'posted':
                    invoice_posted = True
                else:
                    posted_count = self.env['account.move'].search_count([
                        ('fleet_repair_invoice_id', '=', existing.id),
                        ('state', '=', 'posted'),
                    ])
                    if posted_count > 0:
                        invoice_posted = True

                if not invoice_posted:
                    state_label = dict(self._fields['state'].selection).get(existing.state, existing.state)
                    jc_ref = existing.sequence or existing.name or _("ID %s") % existing.id
                    display_plate = plate_name or car.name or _("Selected Vehicle")
                    warning = {
                        'title': _("Active Job Card Exists"),
                        'message': _(
                            "A Job Card (%s) with License Plate '%s' is already active (Status: %s).\n\n"
                            "A new Job Card for the same License Plate cannot be created until the existing Job Card is Done or its Invoice is Posted."
                        ) % (jc_ref, display_plate, state_label)
                    }
                    break
        else:
            self.vehicle_id = False
            self.vin_sn = False
            self.model_name = False
            self.fleet_id = False
            self.kilometers_num = False
            self.client_id = False
            self.client_phone = False
            self.client_mobile = False
            self.client_email = False
            self.client_address = False

        if warning:
            return {'warning': warning}

    @api.onchange('vin_sn', 'kilometers_num')
    def _onchange_vin_sn_kilometers_num(self):
        # Database updates are synced on save via _sync_vehicle_data
        pass

    def _sync_vehicle_data(self):
        for record in self:
            if record.license_plate:
                vehicle = record.license_plate
                update_vals = {}
                if record.vin_sn and vehicle.vin_sn != record.vin_sn:
                    update_vals['vin_sn'] = record.vin_sn
                if record.kilometers_num:
                    try:
                        kms_val = float(record.kilometers_num)
                        if hasattr(vehicle, 'odometer') and vehicle.odometer != kms_val:
                            update_vals['odometer'] = kms_val
                    except (ValueError, TypeError):
                        pass
                if record.client_id and not vehicle.driver_id:
                    update_vals['driver_id'] = record.client_id.id
                if update_vals:
                    vehicle.write(update_vals)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            has_active_timer = any(rec.service_line_ids.mapped('is_timer_running')) or \
                               any(rec.fleet_work_line_ids.mapped('is_timer_running')) or \
                               any(rec.timesheet_ids.mapped('is_timer_running'))
            if has_active_timer and rec.state != 'workorder' and rec.state not in ('done', 'cancel'):
                rec.sudo().write({'state': 'workorder'})
        records._sync_vehicle_data()
        records.action_sync_work_lines_from_service_lines()
        return records

    def action_sync_work_lines_from_service_lines(self):
        for rec in self:
            rec.service_line_ids._sync_to_work_lines()
        return True

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals and vals.get('state') != 'workorder':
            for rec in self:
                has_active_timer = any(rec.service_line_ids.mapped('is_timer_running')) or \
                                   any(rec.fleet_work_line_ids.mapped('is_timer_running'))
                if has_active_timer:
                    raise UserError(_('Cannot change status while a timer is active and ongoing. The Job Card must remain in "Work in Progress" until all timers are paused or stopped.'))

        vehicle_trigger_fields = {'vehicle_id', 'client_id', 'license_plate', 'odometer', 'fuel_level'}
        if any(f in vals for f in vehicle_trigger_fields):
            self._sync_vehicle_data()

        invoice_trigger_fields = {'product_line_ids', 'service_line_ids', 'client_id', 'pricelist_id'}
        if any(f in vals for f in invoice_trigger_fields):
            self._sync_draft_invoices()

        if 'service_line_ids' in vals:
            self.action_sync_work_lines_from_service_lines()
        return res




    @api.model
    def check_owner_change(self, license_plate, client_id):
        vehicle = False
        if isinstance(license_plate, int):
            vehicle = self.env['fleet.vehicle'].browse(license_plate)
        elif isinstance(license_plate, (list, tuple)) and license_plate:
            vehicle = self.env['fleet.vehicle'].browse(license_plate[0])
        elif isinstance(license_plate, str) and license_plate:
            vehicle = self.env['fleet.vehicle'].search(
                [('license_plate', '=', license_plate)],
                order='acquisition_date desc, id desc',
                limit=1,
            )

        if not vehicle or not vehicle.exists():
            return {
                "changed": False,
            }

        if vehicle.driver_id and vehicle.driver_id.id != client_id:
            return {
                "changed": True,
                "vehicle_id": vehicle.id,
                "current_owner": vehicle.driver_id.name,
                "current_owner_id": vehicle.driver_id.id,
            }

        return {
            "changed": False,
        }

    @api.model
    def create_new_owner(self, vehicle_id, partner_id):
        vehicle = self.env["fleet.vehicle"].browse(vehicle_id)

        new_vehicle = self.env["fleet.vehicle"].create({
            "license_plate": vehicle.license_plate,
            "vin_sn": vehicle.vin_sn,
            "model_id": vehicle.model_id.id,
            "driver_id": partner_id,
            "acquisition_date": fields.Date.today(),
        })

        return {
            "vehicle_id": new_vehicle.id,
        }




    # @api.onchange('license_plate', 'vin_sn', 'client_id', 'model_name')
    # def _onchange_license_plate_vin_sn(self):
    #     """Create or update fleet.vehicle when license plate or VIN is set or corrected"""
    #     # Require model_name to create/update vehicle
    #     if not self.model_name:
    #         return
    #
    #     # If vehicle_id is already set, update it (handles corrections)
    #     if self.vehicle_id:
    #         update_vals = {}
    #         # Always update if license_plate is provided and different (handles corrections)
    #         if self.license_plate and self.vehicle_id.license_plate != self.license_plate:
    #             update_vals['license_plate'] = self.license_plate
    #         # Always update if vin_sn is provided and different
    #         if self.vin_sn and self.vehicle_id.vin_sn != self.vin_sn:
    #             update_vals['vin_sn'] = self.vin_sn
    #         # Update client if provided
    #         if self.client_id and self.vehicle_id.driver_id != self.client_id:
    #             update_vals['driver_id'] = self.client_id.id
    #         # Update model if provided
    #         if self.model_name and self.vehicle_id.model_id != self.model_name:
    #             update_vals['model_id'] = self.model_name.id
    #
    #         if update_vals:
    #             self.vehicle_id.write(update_vals)
    #             # Sync back the updated values
    #             if 'license_plate' in update_vals:
    #                 self.license_plate = self.vehicle_id.license_plate
    #             if 'vin_sn' in update_vals:
    #                 self.vin_sn = self.vehicle_id.vin_sn
    #         return
    #
    #     # Only search/create if we have license_plate or vin_sn
    #     if not (self.license_plate or self.vin_sn):
    #         return
    #
    #     vehicle = False
    #
    #     # Search by license_plate first (if provided)
    #     if self.license_plate:
    #         vehicle = self.env['fleet.vehicle'].search([
    #             ('license_plate', '=', self.license_plate)
    #         ], limit=1)
    #
    #     # If not found and vin_sn is provided, search by vin_sn
    #     if not vehicle and self.vin_sn:
    #         vehicle = self.env['fleet.vehicle'].search([
    #             ('vin_sn', '=', self.vin_sn)
    #         ], limit=1)
    #
    #     if not vehicle:
    #         # Create new vehicle if it doesn't exist
    #         vehicle_vals = {
    #             'model_id': self.model_name.id,  # Model is required
    #         }
    #         if self.license_plate:
    #             vehicle_vals['license_plate'] = self.license_plate
    #         if self.vin_sn:
    #             vehicle_vals['vin_sn'] = self.vin_sn
    #         if self.client_id:
    #             vehicle_vals['driver_id'] = self.client_id.id
    #
    #         # Create the vehicle
    #         vehicle = self.env['fleet.vehicle'].create(vehicle_vals)
    #     else:
    #         # Update existing vehicle with any missing or changed information
    #         update_vals = {}
    #         # Update license_plate if provided and different (handles corrections)
    #         if self.license_plate and vehicle.license_plate != self.license_plate:
    #             update_vals['license_plate'] = self.license_plate
    #         # Update vin_sn if provided and different
    #         if self.vin_sn and vehicle.vin_sn != self.vin_sn:
    #             update_vals['vin_sn'] = self.vin_sn
    #         # Update client if provided and missing
    #         if self.client_id and not vehicle.driver_id:
    #             update_vals['driver_id'] = self.client_id.id
    #         # Update model if provided and different
    #         if self.model_name and vehicle.model_id != self.model_name:
    #             update_vals['model_id'] = self.model_name.id
    #
    #         if update_vals:
    #             vehicle.write(update_vals)
    #
    #     # Set the vehicle_id to the vehicle
    #     self.vehicle_id = vehicle.id
    #
    #     # Sync license_plate and vin_sn from vehicle
    #     self.license_plate = vehicle.license_plate
    #     self.vin_sn = vehicle.vin_sn

    # @api.onchange('vehicle_id')
    # def _onchange_vehicle_id(self):
    #     """When vehicle is selected, update related fields"""
    #     if self.vehicle_id:
    #         # Auto-populate license_plate and vin_sn from vehicle
    #         self.license_plate = self.vehicle_id.license_plate
    #         self.vin_sn = self.vehicle_id.vin_sn
    #         # Auto-populate brand if vehicle has a brand
    #         if self.vehicle_id.brand_id:
    #             self.fleet_id = self.vehicle_id.brand_id.id
    #         # Auto-populate model if vehicle has a model
    #         if self.vehicle_id.model_id:
    #             self.model_name = self.vehicle_id.model_id.id
    #         # Auto-populate client if vehicle has a driver
    #         if self.vehicle_id.driver_id:
    #             self.client_id = self.vehicle_id.driver_id.id
    #     else:
    #         # Clear license_plate and vin_sn when vehicle is cleared
    #         self.license_plate = False
    #         self.vin_sn = False

    @api.onchange('fleet_id')
    def _onchange_fleet_id(self):
        """When manufacturer is selected, filter models and clear current model selection"""
        result = {}
        if self.fleet_id:
            # Clear the model selection when manufacturer changes
            if self.model_name and self.model_name.brand_id != self.fleet_id:
                self.model_name = False

            result = {
                'domain': {
                    'model_name': [('brand_id', '=', self.fleet_id.id)]
                },
                'context': {
                    'default_brand_id': self.fleet_id.id
                }
            }
        else:
            # If no manufacturer selected, clear model and remove domain restriction
            self.model_name = False
            result = {
                'domain': {
                    'model_name': []
                }
            }
        return result

    def _inverse_client_phone(self):
        for record in self:
            if record.client_id:
                if record.client_phone:
                    record.client_id.phone = record.client_phone
                if record.client_mobile:
                    record.client_id.mobile = record.client_mobile

    def _inverse_client_email(self):
        for record in self:
            if record.client_id and record.client_email:
                record.client_id.email = record.client_email

    def _inverse_client_address(self):
        for record in self:
            if record.client_id and record.client_address:
                record.client_id.street = record.client_address

    @api.constrains('client_email')
    def _check_client_email_format(self):
        for record in self:
            if record.client_email:
                if '@' not in record.client_email:
                    raise ValidationError(_("Email address must contain '@' special character (e.g. client@example.com)."))

    @api.constrains('client_phone', 'client_mobile')
    def _check_client_phone_digits(self):
        for record in self:
            if not record.client_phone:
                raise ValidationError(_("Mobile 1 (Phone) is mandatory."))
            digits = re.sub(r'\D', '', record.client_phone)
            if len(digits) < 10:
                raise ValidationError(_("Mobile 1 (Phone) must be at least 10 digits."))
            if record.client_mobile:
                mobile_digits = re.sub(r'\D', '', record.client_mobile)
                if len(mobile_digits) < 10:
                    raise ValidationError(_("Mobile 2 must be at least 10 digits."))

    @api.constrains('promised_date', 'receipt_date')
    def _check_promised_date(self):
        for record in self:
            if record.promised_date and record.receipt_date:
                promised_date = record.promised_date.date() if isinstance(record.promised_date, datetime) else record.promised_date
                receipt_date = record.receipt_date.date() if isinstance(record.receipt_date, datetime) else record.receipt_date
                if promised_date < receipt_date:
                    raise ValidationError(_("Promised Date must be greater than or equal to JC Date."))

    @api.constrains('license_plate', 'state')
    def _check_active_job_card_license_plate(self):
        for record in self:
            if not record.license_plate:
                continue

            vehicle = record.license_plate
            plate_name = vehicle.license_plate or False

            domain = [
                ('id', '!=', record.id),
                ('state', 'not in', ['done', 'cancel']),
            ]

            if plate_name:
                domain.extend([
                    '|',
                    ('license_plate', '=', vehicle.id),
                    ('license_plate.license_plate', '=ilike', plate_name.strip())
                ])
            else:
                domain.append(('license_plate', '=', vehicle.id))

            existing_repairs = self.search(domain)
            for existing in existing_repairs:
                invoice_posted = False
                if existing.invoice_order_id and existing.invoice_order_id.state == 'posted':
                    invoice_posted = True
                else:
                    posted_count = self.env['account.move'].search_count([
                        ('fleet_repair_invoice_id', '=', existing.id),
                        ('state', '=', 'posted'),
                    ])
                    if posted_count > 0:
                        invoice_posted = True

                if not invoice_posted:
                    state_label = dict(self._fields['state'].selection).get(existing.state, existing.state)
                    jc_ref = existing.sequence or existing.name or _("ID %s") % existing.id
                    display_plate = plate_name or vehicle.name or _("Selected Vehicle")

                    raise ValidationError(_(
                        "A Job Card (%s) with License Plate '%s' is already active (Status: %s).\n\n"
                        "A new Job Card for the same License Plate cannot be created until the existing Job Card is Done or its Invoice is Posted."
                    ) % (jc_ref, display_plate, state_label))

    @api.onchange('promised_date', 'receipt_date')
    def _onchange_promised_date(self):
        if self.promised_date and self.receipt_date:
            promised_date = self.promised_date.date() if isinstance(self.promised_date, datetime) else self.promised_date
            receipt_date = self.receipt_date.date() if isinstance(self.receipt_date, datetime) else self.receipt_date
            if promised_date < receipt_date:
                raise ValidationError(_("Promised Date must be greater than or equal to JC Date."))

    @api.depends(
        'promised_date',
        'receipt_date',
        'state',
        'invoice_order_id.state',
        'invoice_order_id.invoice_date',
        'invoice_order_id.date',
    )
    def _compute_delivery_status_color(self):
        today = fields.Date.context_today(self)
        for record in self:
            color = 'yellow'
            promised_date = False
            receipt_date = False
            invoice_date = False

            if record.promised_date:
                promised_dt = record.promised_date
                promised_date = promised_dt.date() if hasattr(promised_dt, 'date') else promised_dt

            if record.receipt_date:
                receipt_dt = record.receipt_date
                receipt_date = receipt_dt.date() if hasattr(receipt_dt, 'date') else receipt_dt

            if record.invoice_order_id:
                invoice_dt = record.invoice_order_id.invoice_date or record.invoice_order_id.date
                if invoice_dt:
                    invoice_date = invoice_dt.date() if hasattr(invoice_dt, 'date') else invoice_dt

            invoice_posted = record.invoice_order_id and record.invoice_order_id.state == 'posted'

            if invoice_posted and invoice_date:
                if receipt_date and invoice_date == receipt_date:
                    color = 'green'
                elif promised_date:
                    if invoice_date < promised_date:
                        color = 'green'
                    elif invoice_date == promised_date:
                        color = 'yellow'
                    else:
                        color = 'red'
                else:
                    color = 'green'
            else:
                if not promised_date:
                    color = 'yellow'
                elif today < promised_date:
                    color = 'green'
                elif today == promised_date:
                    color = 'yellow'
                else:
                    color = 'red'

            record.delivery_status_color = color

    @api.depends('product_line_ids.subtotal', 'service_line_ids.subtotal')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(line.subtotal for line in rec.product_line_ids) + sum(line.subtotal for line in rec.service_line_ids)

    @api.model
    def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
        """Ensure outdated delivery signal colors are refreshed before search/sort queries run."""
        if not self.env.context.get('skip_signal_refresh'):
            today = fields.Date.context_today(self)
            outdated = self.with_context(skip_signal_refresh=True).sudo().search([
                '|',
                '&', ('promised_date', '<', today), ('delivery_status_color', '!=', 'red'),
                '&', ('promised_date', '=', today), ('delivery_status_color', '!=', 'yellow'),
            ])
            if outdated:
                outdated.with_context(skip_signal_refresh=True)._compute_delivery_status_color()
                outdated.flush_recordset(['delivery_status_color'])
        return super().search_fetch(domain, field_names, offset=offset, limit=limit, order=order)

    def _cron_update_delivery_colors(self):
        """Cron job to update delivery status colors for all repairs"""
        repairs = self.sudo().search([])
        if repairs:
            repairs._compute_delivery_status_color()
            repairs.flush_recordset(['delivery_status_color'])

    @api.depends('product_line_ids.subtotal', 'service_line_ids.subtotal')
    def _compute_total(self):
        for rec in self:
            rec.amount_parts = sum(line.subtotal for line in rec.product_line_ids)
            rec.amount_service = sum(line.subtotal for line in rec.service_line_ids)
            rec.amount_untaxed = rec.amount_parts + rec.amount_service
            rec.amount_total = rec.amount_untaxed

    def _compute_invoice_paid_amount(self):
        invoice_move = self.env['account.move']
        for rec in self:
            invoices = invoice_move.search([
                ('fleet_repair_invoice_id', '=', rec.id),
                ('state', '=', 'posted'),
                ('payment_state', '=', 'paid'),
            ])
            rec.invoice_paid_amount = sum(invoices.mapped('amount_total'))

    def _compute_inv_count(self):
        for rec in self:
            rec.inv_count = self.env['account.move'].search_count([
                ('state', 'in', ['draft', 'posted']),
                ('fleet_repair_invoice_id', '=', rec.id)
            ])

    def action_create_quotation_fleet(self):
        self.ensure_one()
        if not self.sale_order_id:
            sale_order = self.env['sale.order'].create({
                'partner_id': self.client_id.id,
                'origin': self.name,
                'fleet_repair_id': self.id,

            })
            self.sale_order_id = sale_order.id
        else:
            sale_order = self.sale_order_id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Quotation',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': sale_order.id,

        }

    def _sync_draft_invoices(self):
        if self.env.context.get('skip_sync_draft_invoices'):
            return
        for rec in self:
            draft_invoices = self.env['account.move'].search([
                ('fleet_repair_invoice_id', '=', rec.id),
                ('state', '=', 'draft')
            ])
            if not draft_invoices and rec.invoice_order_id and rec.invoice_order_id.state == 'draft':
                draft_invoices = rec.invoice_order_id

            for invoice in draft_invoices:
                invoice_lines = []
                for line in rec.product_line_ids:
                    if not line.product_id:
                        continue
                    invoice_lines.append((0, 0, {
                        'item_code': line.item_code_display,
                        'product_id': line.product_id.id,
                        'name': line.product_id.name,
                        'quantity': line.quantity,
                        'price_unit': line.unit_price,
                        'product_uom_id': line.uom_id.id if line.uom_id else False,
                        'margin_parts': line.margin,
                        'department_id': line.department_id.id if line.department_id else False,
                        'tax_ids': [(6, 0, line.product_id.taxes_id.ids)],
                    }))

                for line in rec.service_line_ids:
                    if not line.product_id:
                        continue
                    invoice_lines.append((0, 0, {
                        'item_code': line.item_code,
                        'product_id': line.product_id.id,
                        'name': line.name or line.product_id.name,
                        'quantity': line.quantity,
                        'price_unit': line.unit_price,
                        'product_uom_id': line.uom_id.id if line.uom_id else False,
                        'department_id': line.department_id.id if line.department_id else False,
                        'employee_id': line.employee_id.id if line.employee_id else False,
                        'tax_ids': [(6, 0, line.product_id.taxes_id.ids)],
                    }))

                invoice.write({
                    'partner_id': rec.client_id.id if rec.client_id else invoice.partner_id.id,
                    'invoice_line_ids': [(5, 0, 0)] + invoice_lines
                })

    def action_create_invoice_fleet(self):
        self.ensure_one()

        if not self.invoice_order_id:
            existing_invoice = self.env['account.move'].search([
                ('fleet_repair_invoice_id', '=', self.id),
                ('state', '!=', 'cancel')
            ], limit=1)
            if existing_invoice:
                self.invoice_order_id = existing_invoice.id

        if self.invoice_order_id:
            if self.invoice_order_id.state == 'draft':
                self._sync_draft_invoices()
            return {
                'type': 'ir.actions.act_window',
                'name': 'Invoice',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.invoice_order_id.id,
            }

        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        if not journal:
            raise UserError("No Sale Journal found for this company.")

        invoice_lines = []
        for line in self.product_line_ids:
            if not line.product_id:
                continue

            invoice_lines.append((0, 0, {
                'item_code': line.item_code_display,
                'product_id': line.product_id.id,
                'name': line.product_id.name,
                'quantity': line.quantity,
                'price_unit': line.unit_price,
                'product_uom_id': line.uom_id.id if line.uom_id else False,
                'margin_parts': line.margin,
                'department_id': line.department_id.id if line.department_id else False,
                'tax_ids': [(6, 0, line.product_id.taxes_id.ids)],
            }))

        for line in self.service_line_ids:
            if not line.product_id:
                continue

            invoice_lines.append((0, 0, {
                'item_code': line.item_code,
                'product_id': line.product_id.id,
                'name': line.name or line.product_id.name,
                'quantity': line.quantity,
                'price_unit': line.unit_price,
                'product_uom_id': line.uom_id.id if line.uom_id else False,
                'department_id': line.department_id.id if line.department_id else False,
                'employee_id': line.employee_id.id if line.employee_id else False,
                'tax_ids': [(6, 0, line.product_id.taxes_id.ids)],
            }))

        invoice = self.env['account.move'].create({
            'partner_id': self.client_id.id if self.client_id else False,
            'move_type': 'out_invoice',
            'journal_id': journal.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': invoice_lines,
            'fleet_repair_invoice_id': self.id,
            'create_form_fleet': True
        })

        self.invoice_order_id = invoice.id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
        }

    def action_recompute_all_parts_costs(self):
        """Manually trigger cost price and margin recomputation for all parts lines on this job card."""
        for repair in self:
            repair.product_line_ids.action_recompute_cost_and_margin()
        return True

    @api.depends('sequence')
    def _compute_job_card_display(self):
        for rec in self:
            seq = rec.sequence or ''
            rec.job_card_display = f"Job Card No : {seq}"

    def _order_field_to_sql(self, alias, field_name, direction, nulls, query):
        if field_name == 'sequence':
            sql_field = SQL("COALESCE(NULLIF(regexp_replace(%s, '\\D', '', 'g'), '')::INTEGER, 0)", self._field_to_sql(alias, field_name, query))
            if query.groupby:
                query.groupby = SQL('%s, %s', query.groupby, sql_field)
            return SQL("%s %s %s", sql_field, direction, nulls)
        return super()._order_field_to_sql(alias, field_name, direction, nulls, query)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        has_state_filter = any(
            isinstance(term, (list, tuple)) and len(term) >= 1 and term[0] == 'state'
            for term in domain
        )
        has_id_filter = any(
            isinstance(term, (list, tuple)) and len(term) >= 1 and term[0] == 'id'
            for term in domain
        )
        if not has_state_filter and not has_id_filter and not self._context.get('show_all_states'):
            domain = [('state', '!=', 'done')] + list(domain)
        return super()._search(domain, offset=offset, limit=limit, order=order)

    @api.model_create_multi
    def create(self, vals_list):
        # Sequence
        self.env.cr.execute(
            "SELECT COALESCE(MAX(CAST(sequence AS INTEGER)), 0) FROM fleet_repair"
        )
        last_seq = self.env.cr.fetchone()[0]

        for vals in vals_list:
            last_seq += 1
            vals['sequence'] = str(last_seq)

        repairs = super().create(vals_list)

        project = self.env['project.project']

        for repair in repairs:

            # Sync vehicle_id from selected license_plate
            if repair.license_plate:
                repair.vehicle_id = repair.license_plate.id

            # Create project
            company_id = repair.company_id.id or self.env.company.id

            repair.project_id = project.with_company(company_id).create({
                'name': f"Job Card No: {repair.sequence}",
                'allow_timesheets': True,
                'partner_id': repair.client_id.id if repair.client_id else False,
                'company_id': company_id,
            }).id

        return repairs

    @api.depends('child_ids.planned_hours')
    def _compute_subtask_planned_hours(self):
        for task in self:
            task.subtask_planned_hours = sum(
                child_task.planned_hours + child_task.subtask_planned_hours for child_task in task.child_ids)

    def button_view_diagnosis(self):
        list = []
        context = dict(self._context or {})
        dig_order_ids = self.env['fleet.diagnose'].search([('fleet_repair_id', '=', self.id)])
        for order in dig_order_ids:
            list.append(order.id)
        return {
            'name': _('Car Diagnosis'),
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'fleet.diagnose',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', list)],
            'context': context,
        }

    def button_view_workorder(self):
        list = []
        context = dict(self._context or {})
        work_order_ids = self.env['fleet.workorder'].search([('fleet_repair_id', '=', self.id)])
        for order in work_order_ids:
            list.append(order.id)
        return {
            'name': _('Car Work Order'),
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'fleet.workorder',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', list)],
            'context': context,
        }

    def button_view_quotation_fleet(self):
        list = []
        context = dict(self._context or {})
        quo_order_ids = self.env['sale.order'].search([('state', '=', 'draft'), ('fleet_repair_id', '=', self.id)])
        for order in quo_order_ids:
            list.append(order.id)
        return {
            'name': _('Sale'),
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'sale.order',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', list)],
            'context': context,
        }

    def button_view_invoice_fleet(self):
        self._sync_draft_invoices()
        list = []
        context = dict(self._context or {})
        invoice_order_ids = self.env['account.move'].search([
            ('state', 'in', ['draft', 'posted']),
            ('fleet_repair_invoice_id', '=', self.id)
        ])
        for order in invoice_order_ids:
            list.append(order.id)

        if len(list) == 1:
            return {
                'name': _('Invoice'),
                'view_mode': 'form',
                'res_model': 'account.move',
                'res_id': list[0],
                'type': 'ir.actions.act_window',
                'context': context,
            }

        return {
            'name': _('Invoice'),
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', list)],
            'context': context,
        }

    def button_view_saleorder(self):
        list = []
        context = dict(self._context or {})
        quo_order_ids = self.env['sale.order'].search([('state', '=', 'sale'), ('fleet_repair_id', '=', self.id)])
        for order in quo_order_ids:
            list.append(order.id)
        return {
            'name': _('Sale'),
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'sale.order',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', list)],
            'context': context,
        }

    def button_view_invoice(self):
        list = []
        inv_list = []
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('account.action_invoice_tree1')
        list_view_id = imd.xmlid_to_res_id('account.invoice_tree')
        form_view_id = imd.xmlid_to_res_id('account.invoice_form')
        so_order_ids = self.env['sale.order'].search([('state', '=', 'sale'), ('fleet_repair_id', '=', self.id)])
        for order in so_order_ids:
            inv_order_ids = self.env['account.move'].search([('origin', '=', order.name)])
            if inv_order_ids:
                for order_id in inv_order_ids:
                    if order_id.id not in list:
                        list.append(order_id.id)

        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'list'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'],
                      [False, 'calendar'], [False, 'pivot']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(list) > 1:
            result['domain'] = "[('id','in',%s)]" % list
        elif len(list) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = list[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    @api.depends('workorder_id')
    def _compute_workorder_id(self):
        for order in self:
            work_order_ids = self.env['fleet.workorder'].search([('fleet_repair_id', '=', order.id)])
            order.workorder_count = len(work_order_ids)

    @api.depends('diagnose_id')
    def _compute_dignosis_id(self):
        for order in self:
            dig_order_ids = self.env['fleet.diagnose'].search([('fleet_repair_id', '=', order.id)])
            order.dig_count = len(dig_order_ids)

    @api.depends('sale_order_id')
    def _compute_quotation_id(self):
        for order in self:
            quo_order_ids = self.env['sale.order'].search([('state', '=', 'draft'), ('fleet_repair_id', '=', order.id)])
            order.quotation_count = len(quo_order_ids)

    @api.depends('confirm_sale_order')
    def _compute_saleorder_id(self):
        for order in self:
            order.quotation_count = 0
            so_order_ids = self.env['sale.order'].search([('state', '=', 'sale'), ('fleet_repair_id', '=', order.id)])
            order.saleorder_count = len(so_order_ids)

    @api.depends('state')
    def _compute_invoice_id(self):
        count = 0
        if self.state == 'invoiced':
            for order in self:
                so_order_ids = self.env['sale.order'].search(
                    [('state', '=', 'sale'), ('fleet_repair_id', '=', order.id)])
                for order in so_order_ids:
                    inv_order_ids = self.env['account.move'].search([('origin', '=', order.name)])
                    if inv_order_ids:
                        self.inv_count = len(inv_order_ids)

    def diagnosis_created(self):
        self.write({'state': 'diagnosis'})

    def quote_created(self):
        self.write({'state': 'quote'})

    def order_confirm(self):
        self.write({'state': 'saleorder'})

    def fleet_confirmed(self):
        self.write({'state': 'confirm'})

    def workorder_created(self):
        self.write({'state': 'workorder'})

    @api.onchange('client_id')
    def onchange_partner_id(self):
        if self.client_id:
            self.client_email = self.client_id.email or False
            self.client_phone = self.client_id.phone or False
            self.client_mobile = self.client_id.mobile or False
            self.client_address = self.client_id.contact_address or False
        else:
            self.client_email = False
            self.client_phone = False
            self.client_mobile = False
            self.client_address = False

    def action_create_fleet_diagnosis(self):
        Diagnosis_obj = self.env['fleet.diagnose']
        fleet_line_obj = self.env['fleet.repair.line']
        timesheet_obj = self.env['account.analytic.line']
        repair_obj = self.env['fleet.repair'].browse(self._ids[0])
        mod_obj = self.env['ir.model.data']
        act_obj = self.env['ir.actions.act_window']
        if not repair_obj.fleet_id:
            raise UserError('You cannot create Car Diagnosis without Cars.')

        diagnose_vals = {
            'service_rec_no': repair_obj.sequence,
            'name': repair_obj.name,
            'priority': repair_obj.priority,
            'receipt_date': repair_obj.receipt_date,
            'client_id': repair_obj.client_id.id,
            'contact_name': repair_obj.contact_name,
            'phone': repair_obj.phone,
            'client_phone': repair_obj.client_phone,
            'client_mobile': repair_obj.client_mobile,
            'client_email': repair_obj.client_email,
            'fleet_repair_id': repair_obj.id,
            'state': 'draft',
        }
        diagnose_id = Diagnosis_obj.create(diagnose_vals)
        for line in repair_obj.fleet_repair_line:
            fleet_line_vals = {
                'fleet_id': line.fleet_id.id,
                'license_plate': line.license_plate,
                'vin_sn': line.vin_sn,
                'fuel_type': line.fuel_type,
                'model_id': line.model_id.id,
                'service_type': line.service_type.id,
                'guarantee': line.guarantee,
                'guarantee_type': line.guarantee_type,
                'service_detail': line.service_detail,
                'diagnose_id': diagnose_id.id,
                'list_of_damage': line.list_of_damage,
                'car_year': line.car_year,
                'diagnose_id': diagnose_id.id,
                'state': 'diagnosis',
                'source_line_id': line.id,
            }
            fleet_line_obj.create(fleet_line_vals)
            line.write({'state': 'diagnosis'})

        for rec in repair_obj.timesheet_ids:
            if rec.task_id and rec.task_id.private:
                rec.task_id.write({'private': False})
            timesheet_line_vals = {
                'date': rec.date,
                'diagnose_id': diagnose_id.id,
                'project_id': rec.project_id.id,
                'task_id': rec.task_id.id,
                'employee_id': rec.employee_id.id,
                'name': rec.name,
                'service_type': rec.service_type.id,
                'unit_amount': rec.unit_amount,
                'company_id': rec.company_id.id,
                'currency_id': rec.currency_id.id,

            }
            timesheet_obj.create(timesheet_line_vals)

        self.write({'state': 'diagnosis', 'diagnose_id': diagnose_id.id})
        result = mod_obj._xmlid_lookup("%s.%s" % ('car_repair_industry', 'action_fleet_diagnose_tree_view'))
        id = result and result[1] or False
        result = act_obj.browse(id).read()[0]
        res = mod_obj._xmlid_lookup("%s.%s" % ('car_repair_industry', 'view_fleet_diagnose_form'))
        result['views'] = [(res and res[1] or False, 'form')]
        result['res_id'] = diagnose_id.id or False
        return result

    def action_print_receipt(self):
        assert len(self._ids) == 1, 'This option should only be used for a single id at a time'
        return self.env.ref('car_repair_industry.fleet_repair_receipt_id').report_action(self)

    def action_print_label(self):
        if not self.fleet_repair_line:
            raise UserError(_('You cannot print report without Car details'))

        assert len(self._ids) == 1, 'This option should only be used for a single id at a time'
        return self.env.ref('car_repair_industry.fleet_repair_label_id').report_action(self)

    def action_view_quotation(self):
        mod_obj = self.env['ir.model.data']
        act_obj = self.env['ir.actions.act_window']
        order_id = self.sale_order_id.id
        result = mod_obj._xmlid_lookup("%s.%s" % ('sale', 'action_orders'))[1:3]
        id = result and result[1] or False
        result = act_obj.browse(id).read()[0]
        res = mod_obj._xmlid_lookup("%s.%s" % ('sale', 'view_order_form'))[1:3]
        result['views'] = [(res and res[1] or False, 'form')]
        result['res_id'] = order_id or False
        return result

    def action_view_work_order(self):
        mod_obj = self.env['ir.model.data']
        act_obj = self.env['ir.actions.act_window']
        work_order_id = self.workorder_id.id
        result = mod_obj._xmlid_lookup("%s.%s" % ('car_repair_industry', 'action_fleet_workorder_tree_view'))[1:3]
        id = result and result[1] or False
        result = act_obj.browse(id).read()[0]
        res = mod_obj._xmlid_lookup("%s.%s" % ('car_repair_industry', 'view_fleet_workorder_form'))[1:3]
        result['views'] = [(res and res[1] or False, 'form')]
        result['res_id'] = work_order_id or False
        return result

    @api.model
    def action_activity_dashboard_redirect(self):
        if self.env.user.has_group('base.group_user'):
            return self.env["ir.actions.actions"]._for_xml_id("car_repair_industry.fleet_repair_dashboard")
        return self.env["ir.actions.actions"]._for_xml_id("car_repair_industry.fleet_repair_dashboard")


class ir_attachment(models.Model):
    _inherit = 'ir.attachment'

    car_repair_id = fields.Many2one('fleet.repair', 'Car Repair')


class ServiceType(models.Model):
    _name = 'service.type'
    _description = "Service Type"

    name = fields.Char(string='Name')
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        domain="[('model_ids.model', '=', 'service.type')]"
    )

    def write(self, vals):
        res = super().write(vals)
        if 'department_id' in vals:
            for rec in self:
                lines = self.env['service.detail.line'].search([('service_type', '=', rec.id)])
                lines.write({'department_id': rec.department_id.id})
        return res


class FleetRepairLine(models.Model):
    _name = 'fleet.repair.line'
    _description = "Fleet repair line"

    fleet_id = fields.Many2one('fleet.vehicle', 'Car')
    # license_plate = fields.Char('License Plate', help='License plate number of the vehicle (ie: plate number for a car)')
    license_plate = fields.Char(
        related='fleet_id.license_plate',
        string='License Plate',
        store=True, readonly=False)
    vin_sn = fields.Char('Chassis Number', help='Unique number written on the vehicle motor (VIN/SN number)')
    model_id = fields.Many2one('fleet.vehicle.model', 'Model', help='Model of the vehicle')
    fuel_type = fields.Selection([('diesel', 'Diesel'),
                                  ('petrol', 'Petrol'),
                                  ('gasoline', 'Gasoline'),
                                  ('full_hybrid', 'Full Hybrid'),
                                  ('plug_in_hybrid_diesel', 'Plug-in Hybrid Diesel'),
                                  ('plug_in_hybrid_gasoline', 'Plug-in Hybrid Gasoline'),
                                  ('cng', 'CNG'),
                                  ('lpg', 'LPG'),
                                  ('hydrogen', 'Hydrogen'),
                                  ('electric', 'Electric'), ('hybrid', 'Hybrid')], 'Fuel Type',
                                 help='Fuel Used by the vehicle')
    guarantee = fields.Selection(
        [('yes', 'Yes'), ('no', 'No')], string='Under Guarantee?')
    guarantee_type = fields.Selection(
        [('paid', 'paid'), ('free', 'Free')], string='Guarantee Type')
    service_type = fields.Many2one('service.type', string='Nature of Service')
    fleet_repair_id = fields.Many2one('fleet.repair', string='Car.', copy=False)
    service_detail = fields.Text(string='Repair Details')
    diagnostic_result = fields.Text(string='Diagnostic Result')
    diagnose_id = fields.Many2one('fleet.diagnose', string='Car Diagnose', copy=False)
    workorder_id = fields.Many2one('fleet.workorder', string='Car Work Order', copy=False)
    source_line_id = fields.Many2one('fleet.repair.line', string='Source')
    est_ser_hour = fields.Float(string='Estimated Sevice Hours')
    service_product_id = fields.Many2one('product.product', string='Service Product')
    service_product_price = fields.Float('Service Product Price')
    spare_part_ids = fields.One2many('spare.part.line', 'fleet_id', string='Spare Parts Needed')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('diagnosis', 'In Diagnosis'),
        ('done', 'Done'),
    ], 'Status', default="draft", readonly=True, copy=False, help="Gives the status of the fleet Diagnosis.",
        index=True)
    car_year = fields.Char(string="car Manufacturing Year")
    list_of_damage = fields.Char(string="Car Manufacturing Year")

    _rec_name = 'fleet_id'

    @api.onchange('service_product_id')
    def onchange_service_product_id(self):
        for price in self:
            price.service_product_price = price.service_product_id.list_price

    def name_get(self):
        if not self._ids:
            return []
        if isinstance(self._ids, (int, int)):
            ids = [self._ids]
        reads = self.read(['fleet_id', 'license_plate'])
        res = []
        for record in reads:
            name = record['license_plate']
            if record['fleet_id']:
                name = record['fleet_id'][1]
            res.append((record['id'], name))
        return res

    def action_add_fleet_diagnosis_result(self):
        for obj in self:
            self.write({'state': 'done'})
        return True

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(FleetRepairLine, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)
        return res

    # @api.onchange('fleet_id')
    # def onchange_fleet_id(self):
    #     addr = {}
    #     if self.fleet_id:
    #         fleet = self.fleet_id
    #         addr['license_plate'] = fleet.license_plate
    #         addr['vin_sn'] = fleet.vin_sn
    #         addr['fuel_type'] = fleet.fuel_type
    #         addr['model_id'] = fleet.model_id.id
    #     return {'value': addr}


class FleetRepairProductLine(models.Model):
    _name = 'fleet.repair.product.line'
    _description = 'Fleet Repair Product Line'

    repair_id = fields.Many2one('fleet.repair', string='Repair Order', ondelete='cascade', required=True)

    # Both product and item_code point to product.template now
    product_id = fields.Many2one('product.product', domain=[('type', '=', 'consu')], string='Item')
    item_code_id = fields.Many2one(
        'product.product',
        domain=[('type', '=', 'consu'), ('item_code', '!=', False), ('item_code', '!=', '')],
        string='Item Code',
    )

    item_code_display = fields.Char(
        string="Item Code",
        related='item_code_id.item_code',
        readonly=False,
        store=True
    )

    name = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity', default=0.0)
    available_qty = fields.Float(
        string='Available',
        compute='_compute_available_qty',
    )
    onhand_qty = fields.Float(
        string='On-Hand',
        compute='_compute_onhand_qty',
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True,
        domain="[('model_ids.model', '=', 'fleet.repair.product.line')]"
    )
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    unit_price = fields.Float(string='Unit Price')
    subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal', store=True)
    currency_id = fields.Many2one('res.currency', related='repair_id.currency_id', store=True, readonly=True)

    # @api.depends('item_code_id')
    # def _compute_item_code_display(self):
    #     for rec in self:
    #         rec.item_code_display = rec.item_code_id.item_code if rec.item_code_id else ''

    def _get_warehouse(self):
        self.ensure_one()
        company = self.repair_id.company_id or self.env.company
        return self.env['stock.warehouse'].search(
            [('company_id', '=', company.id)], limit=1
        )

    def _get_available_qty(self, product, warehouse):
        """Return free_qty in the line UoM (allowing negative stock)."""
        if not product or not product.is_storable:
            return 0.0
        line_uom = self.uom_id or product.uom_id
        if warehouse and warehouse.lot_stock_id:
            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id', 'child_of', warehouse.lot_stock_id.id),
            ])
            if quants:
                qty = sum(quants.mapped('quantity')) - sum(quants.mapped('reserved_quantity'))
            else:
                qty = self.env['stock.quant']._get_available_quantity(
                    product.sudo(), warehouse.lot_stock_id, strict=True, allow_negative=True,
                )
        else:
            qty = product.with_context(warehouse_id=warehouse.id).free_qty if warehouse else 0.0
        if line_uom and product.uom_id and line_uom != product.uom_id:
            qty = product.uom_id._compute_quantity(qty, line_uom)
        return qty

    def _get_total_requested_qty(self, product):
        """Sum requested qty for product on this repair, in the current line UoM."""
        self.ensure_one()
        target_uom = self.uom_id or product.uom_id
        total = 0.0
        for line in self.repair_id.product_line_ids.filtered(lambda l: l.product_id == product):
            line_uom = line.uom_id or product.uom_id
            qty = line.quantity
            if line_uom != target_uom:
                qty = line_uom._compute_quantity(qty, target_uom)
            total += qty
        return total

    def _get_repair_requested_qty(self, product):
        """Sum requested qty for product on this repair, in the product's default UoM."""
        self.ensure_one()
        total = 0.0
        for line in self.repair_id.product_line_ids.filtered(lambda l: l.product_id == product):
            line_uom = line.uom_id or product.uom_id
            total += line_uom._compute_quantity(line.quantity, product.uom_id)
        return total

    def _get_product_available_qty(self, product, warehouse):
        """Return free_qty in the product's default UoM."""
        if not product or not product.is_storable:
            return float('inf')
        return product.with_context(warehouse_id=warehouse.id).free_qty

    @api.depends('product_id', 'uom_id', 'quantity', 'qty_issued', 'repair_id', 'repair_id.company_id', 'repair_id.product_line_ids.quantity', 'repair_id.product_line_ids.product_id', 'repair_id.product_line_ids.qty_issued')
    def _compute_available_qty(self):
        for line in self:
            if not line.product_id or line.product_id.type != 'consu':
                line.available_qty = 0.0
                continue
            warehouse = line._get_warehouse()
            if warehouse and warehouse.lot_stock_id:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', line.product_id.id),
                    ('location_id', 'child_of', warehouse.lot_stock_id.id),
                ])
                base_qty = sum(quants.mapped('quantity')) if quants else self.env['stock.quant']._get_available_quantity(
                    line.product_id.sudo(), warehouse.lot_stock_id, strict=True, allow_negative=True,
                )
            else:
                base_qty = line.product_id.with_context(warehouse_id=warehouse.id).qty_available if warehouse else 0.0

            line_uom = line.uom_id or line.product_id.uom_id
            if line_uom and line.product_id.uom_id and line_uom != line.product_id.uom_id:
                base_qty = line.product_id.uom_id._compute_quantity(base_qty, line_uom)

            pending_qty = 0.0
            repair = line.repair_id or (line._find_repair_order() if hasattr(line, '_find_repair_order') else line.repair_id)
            if repair and repair.product_line_ids:
                for sibling in repair.product_line_ids.filtered(lambda l: l.product_id == line.product_id):
                    unissued = max(sibling.quantity - (getattr(sibling, 'qty_issued', 0.0) or 0.0), 0.0)
                    sib_uom = sibling.uom_id or sibling.product_id.uom_id
                    if line_uom and sib_uom and sib_uom != line_uom:
                        unissued = sib_uom._compute_quantity(unissued, line_uom)
                    pending_qty += unissued

            line.available_qty = base_qty - pending_qty

    @api.depends('product_id', 'uom_id', 'repair_id', 'repair_id.company_id')
    def _compute_onhand_qty(self):
        for line in self:
            if not line.product_id or line.product_id.type != 'consu':
                line.onhand_qty = 0.0
                continue
            warehouse = line._get_warehouse()
            if warehouse and warehouse.lot_stock_id:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', line.product_id.id),
                    ('location_id', 'child_of', warehouse.lot_stock_id.id),
                ])
                raw_qty = sum(quants.mapped('quantity')) if quants else self.env['stock.quant']._get_available_quantity(
                    line.product_id.sudo(), warehouse.lot_stock_id, strict=True, allow_negative=True,
                )
            else:
                raw_qty = line.product_id.with_context(warehouse_id=warehouse.id).qty_available if warehouse else 0.0

            line_uom = line.uom_id or line.product_id.uom_id
            if line_uom and line.product_id.uom_id and line_uom != line.product_id.uom_id:
                raw_qty = line.product_id.uom_id._compute_quantity(raw_qty, line_uom)
            line.onhand_qty = raw_qty

    @api.model
    def action_enable_inventory_tracking(self, product_id):
        """Enable Track Inventory on a goods product (called from repair line UI)."""
        product = self.env['product.product'].browse(product_id).exists()
        if not product:
            raise UserError(_('Product not found.'))
        if product.type != 'consu':
            raise UserError(_('Only goods products can track inventory.'))
        if not product.is_storable:
            product.write({'is_storable': True})
        return True

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price

    @api.onchange('item_code_id')
    def _onchange_item_code_id(self):
        for line in self:
            product = line.item_code_id
            if product:
                error = line._get_repair_line_product_error(product)
                if error:
                    line._clear_invalid_product_line()
                    return {
                        'warning': {
                            'title': _('Invalid Product') if product.type == 'service' else _('Track Inventory'),
                            'message': error,
                        }
                    }
                line.product_id = product
                line.name = product.name
                line.unit_price = product.list_price
                line.uom_id = product.uom_id
                if product.department_id:
                    line.department_id = product.department_id
            else:
                line.product_id = False
                line.name = False
                line.unit_price = 0.0
                line.uom_id = False

    def _get_repair_line_product_error(self, product):
        if product.type == 'service':
            return _('You cannot add a service product here.')
        if product.type == 'consu' and not product.is_storable:
            return _(
                'Product "%s" must have inventory tracking enabled '
                'before it can be added to repair items.',
                product.display_name,
            )
        return False

    def _clear_invalid_product_line(self):
        self.product_id = False
        self.item_code_id = False
        self.name = False
        self.unit_price = 0.0
        self.uom_id = False

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """When product is selected, populate item code and details."""
        for line in self:
            product = line.product_id
            if product:
                error = line._get_repair_line_product_error(product)
                if error:
                    line._clear_invalid_product_line()
                    return {
                        'warning': {
                            'title': _('Invalid Product') if product.type == 'service' else _('Track Inventory'),
                            'message': error,
                        }
                    }
                line.name = product.name
                line.unit_price = product.list_price
                line.uom_id = product.uom_id
                line.item_code_id = product
                if product.department_id:
                    line.department_id = product.department_id
            else:
                line.item_code_id = False
                line.name = False
                line.unit_price = 0.0
                line.uom_id = False

    @api.onchange('department_id')
    def _onchange_department_id_update_product(self):
        for line in self:
            if line.product_id and line.department_id and line.product_id.department_id != line.department_id:
                line.product_id.department_id = line.department_id

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.product_id and line.department_id and line.product_id.department_id != line.department_id:
                line.product_id.sudo().write({'department_id': line.department_id.id})
        return lines

    def write(self, vals):
        res = super().write(vals)
        if 'department_id' in vals:
            for line in self:
                if line.product_id and line.department_id and line.product_id.department_id != line.department_id:
                    line.product_id.sudo().write({'department_id': line.department_id.id})
        return res

    @api.constrains('product_id')
    def _check_product_line_product(self):
        for line in self:
            product = line.product_id
            if not product:
                continue
            error = line._get_repair_line_product_error(product)
            if error:
                raise ValidationError(error)


class FleetRepairServiceLine(models.Model):
    _name = 'fleet.repair.service.line'
    _description = 'Fleet Repair Service Line'

    repair_id = fields.Many2one('fleet.repair', string='Repair Order', ondelete='cascade', required=True)
    work_line_ids = fields.One2many('fleet.repair.work.line', 'service_line_id', string='Work Lines')
    product_id = fields.Many2one('product.product', domain=[('type', '=', 'service')], string='Service')
    item_code_id = fields.Many2one(
        'product.product',
        domain=[('type', '=', 'service'), ('item_code', '!=', False), ('item_code', '!=', '')],
        string='Item Code',
    )
    item_code = fields.Char(
        string='Item Code',
        compute='_compute_item_code',
        inverse='_inverse_item_code',
        store=True,
        readonly=False,
    )
    item_code_display = fields.Char(
        string='Item Code',
        related='item_code',
        readonly=False,
        store=True,
    )

    @api.depends('product_id.item_code', 'item_code_id.item_code')
    def _compute_item_code(self):
        for line in self:
            if line.item_code_id and line.item_code_id.item_code:
                line.item_code = line.item_code_id.item_code
            elif line.product_id and line.product_id.item_code:
                line.item_code = line.product_id.item_code
            elif not line.item_code:
                line.item_code = False

    def _inverse_item_code(self):
        for line in self:
            if line.item_code and line.item_code.strip():
                code = line.item_code.strip()
                product = self.env['product.product'].search([
                    ('type', '=', 'service'),
                    ('item_code', '=ilike', code),
                ], limit=1)
                if product:
                    line.product_id = product
                    line.item_code_id = product
    alloted_fru = fields.Integer(
        string='Alloted FRU',
        default=0,
    )

    name = fields.Text(string='Description')
    quantity = fields.Float(
        string='Quantity',
        compute='_compute_quantity',
        store=True,
        readonly=False,
        precompute=True,
        default=1.0,
    )

    @api.depends('alloted_fru')
    def _compute_quantity(self):
        for line in self:
            if line.alloted_fru and line.alloted_fru > 0:
                line.quantity = float(line.alloted_fru)
            else:
                line.quantity = 1.0
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True,
        domain="[('model_ids.model', '=', 'fleet.repair.service.line')]"
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        domain="[('department_id', '=', department_id)] if department_id else []",
        required=True
    )
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    unit_price = fields.Float(string='Price')
    subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal', store=True)
    currency_id = fields.Many2one('res.currency', related='repair_id.currency_id', store=True, readonly=True)

    timer_start = fields.Datetime('Start Timer')
    timer_end = fields.Datetime('End Timer')
    timer_last_start = fields.Datetime('Last Start Timer')
    is_timer_running = fields.Boolean('Timer Running', default=False)
    is_timer_paused = fields.Boolean('Timer Paused', default=False)
    accumulated_seconds = fields.Float('Accumulated Seconds', default=0.0)
    time_diff = fields.Float(
        compute='_compute_time_diff',
        store=True
    )
    fru_status = fields.Selection(
        [('green', 'Normal'), ('yellow', 'Warning'), ('red', 'Overtime')],
        string='FRU Status',
        compute='_compute_time_diff',
        store=True,
        default='green',
    )
    receipt_date = fields.Datetime(related='repair_id.receipt_date', string='JC date', store=True, readonly=True)

    @api.depends('timer_start', 'timer_end', 'is_timer_running', 'accumulated_seconds', 'timer_last_start', 'alloted_fru', 'quantity', 'unit_price')
    def _compute_time_diff(self):
        for rec in self:
            total_sec = rec.accumulated_seconds or 0.0
            if rec.is_timer_running and rec.timer_last_start:
                now = fields.Datetime.now()
                delta = now - rec.timer_last_start
                total_sec += delta.total_seconds()
            rec.time_diff = total_sec / 3600.0

            if rec.alloted_fru and rec.alloted_fru > 0:
                fru_sec = rec.alloted_fru * 300.0
                if total_sec < fru_sec:
                    rec.fru_status = 'green'
                elif total_sec < 2 * fru_sec:
                    rec.fru_status = 'yellow'
                else:
                    rec.fru_status = 'red'
            else:
                price = rec.unit_price or 0.0
                if price > 0:
                    # [0, y/2400) -> green, [y/2400, y/1200) -> yellow, [y/1200, infinity) -> red
                    # where y is the price and 2400 is 2400 rs/hr (3600 sec/hr)
                    # yellow threshold: (y / 2400) * 3600 = y * 1.5 seconds
                    # red threshold: (y / 1200) * 3600 = y * 3.0 seconds
                    yellow_sec = (price / 2400.0) * 3600.0
                    red_sec = (price / 1200.0) * 3600.0
                    if total_sec < yellow_sec:
                        rec.fru_status = 'green'
                    elif total_sec < red_sec:
                        rec.fru_status = 'yellow'
                    else:
                        rec.fru_status = 'red'
                else:
                    rec.fru_status = 'green'

    def _sync_to_work_lines(self):
        if self.env.context.get('skip_work_line_sync'):
            return
        WorkLine = self.env['fleet.repair.work.line'].sudo()
        for sline in self:
            if not sline.repair_id:
                continue
            vals = {
                'work_type': sline.product_id.id if sline.product_id else False,
                'department_type_id': sline.department_id.id if sline.department_id else False,
                'employee_id': sline.employee_id.id if sline.employee_id else False,
                'timer_start': sline.timer_start,
                'timer_end': sline.timer_end,
                'timer_last_start': sline.timer_last_start,
                'is_timer_running': sline.is_timer_running,
                'is_timer_paused': sline.is_timer_paused,
                'accumulated_seconds': sline.accumulated_seconds,
                'time_diff': sline.time_diff,
            }
            work_lines = WorkLine.search([('service_line_id', '=', sline.id)])
            if work_lines:
                work_lines.with_context(skip_service_line_sync=True).write(vals)
            else:
                unlinked = WorkLine.search([
                    ('repair_id', '=', sline.repair_id.id),
                    ('service_line_id', '=', False),
                    ('work_type', '=', sline.product_id.id if sline.product_id else False),
                    ('employee_id', '=', sline.employee_id.id if sline.employee_id else False),
                ], limit=1)
                if unlinked:
                    vals['service_line_id'] = sline.id
                    unlinked.with_context(skip_service_line_sync=True).write(vals)
                else:
                    vals.update({
                        'repair_id': sline.repair_id.id,
                        'service_line_id': sline.id,
                    })
                    WorkLine.with_context(skip_service_line_sync=True).create(vals)

    def action_start_timer(self):
        result = {}
        for rec in self:
            if rec.repair_id and rec.repair_id.state in ('done', 'cancel'):
                raise UserError(_('Cannot start timer when Job Card is in Done or Cancelled state.'))
            if rec.is_timer_running:
                continue

            now = fields.Datetime.now()
            if not rec.timer_start:
                rec.timer_start = now
            rec.timer_last_start = now
            rec.timer_end = False
            rec.is_timer_running = True
            rec.is_timer_paused = False
            if rec.repair_id and rec.repair_id.state != 'workorder' and rec.repair_id.state not in ('done', 'cancel'):
                rec.repair_id.sudo().write({'state': 'workorder'})
            if rec.repair_id:
                rec.repair_id._compute_active_service_info()
            rec._compute_time_diff()
            rec._sync_to_work_lines()
            result = {
                'timer_start': fields.Datetime.to_string(rec.timer_start) if rec.timer_start else False,
                'timer_last_start': fields.Datetime.to_string(rec.timer_last_start) if rec.timer_last_start else False,
                'timer_end': False,
                'is_timer_running': True,
                'is_timer_paused': False,
                'accumulated_seconds': rec.accumulated_seconds,
                'time_diff': rec.time_diff,
                'fru_status': rec.fru_status,
            }
        return result

    def action_pause_timer(self):
        result = {}
        for rec in self:
            if not rec.is_timer_running:
                continue

            now = fields.Datetime.now()
            if rec.timer_last_start:
                delta = now - rec.timer_last_start
                rec.accumulated_seconds += delta.total_seconds()
            rec.timer_last_start = False
            rec.timer_end = now
            rec.is_timer_running = False
            rec.is_timer_paused = True
            if rec.repair_id:
                rec.repair_id._compute_active_service_info()
            rec._compute_time_diff()
            rec._sync_to_work_lines()
            result = {
                'timer_start': fields.Datetime.to_string(rec.timer_start) if rec.timer_start else False,
                'timer_last_start': False,
                'timer_end': fields.Datetime.to_string(rec.timer_end) if rec.timer_end else False,
                'is_timer_running': False,
                'is_timer_paused': True,
                'accumulated_seconds': rec.accumulated_seconds,
                'time_diff': rec.time_diff,
                'fru_status': rec.fru_status,
            }
        return result

    def action_stop_timer(self):
        for rec in self:
            if not rec.timer_start and not rec.is_timer_paused and not rec.is_timer_running:
                raise UserError(_('Timer is not started'))
            if rec.timer_end and not rec.is_timer_running:
                raise UserError(_('Timer is already stopped'))

            now = fields.Datetime.now()
            if rec.is_timer_running and rec.timer_last_start:
                delta = now - rec.timer_last_start
                rec.accumulated_seconds += delta.total_seconds()
                rec.timer_last_start = False

            rec.timer_end = now
            rec.is_timer_running = False
            rec.is_timer_paused = False
            if rec.repair_id:
                rec.repair_id._compute_active_service_info()
            rec._sync_to_work_lines()

    def action_reset_timer(self):
        result = {}
        for rec in self:
            rec.write({
                'timer_start': False,
                'timer_last_start': False,
                'timer_end': False,
                'is_timer_running': False,
                'is_timer_paused': False,
                'accumulated_seconds': 0.0,
                'time_diff': 0.0,
                'fru_status': 'green',
            })
            if rec.repair_id:
                rec.repair_id._compute_active_service_info()
            rec._sync_to_work_lines()
            result = {
                'timer_start': False,
                'timer_last_start': False,
                'timer_end': False,
                'is_timer_running': False,
                'is_timer_paused': False,
                'accumulated_seconds': 0.0,
                'time_diff': 0.0,
                'fru_status': 'green',
            }
        return result

    @api.depends('quantity', 'unit_price', 'alloted_fru')
    def _compute_subtotal(self):
        for line in self:
            if line.alloted_fru and line.alloted_fru > 0:
                line.subtotal = float(line.alloted_fru) * (line.unit_price or 200.0)
            else:
                line.subtotal = line.unit_price or 0.0

    @api.onchange('alloted_fru', 'unit_price')
    def _onchange_alloted_fru(self):
        for line in self:
            if line.alloted_fru and line.alloted_fru > 0:
                line.unit_price = 200.0
                line.quantity = float(line.alloted_fru)
                line.subtotal = float(line.alloted_fru) * 200.0
            else:
                line.quantity = 1.0
                line.subtotal = line.unit_price or 0.0

    @api.onchange('item_code_id')
    def _onchange_item_code_id(self):
        for line in self:
            product = line.item_code_id
            if product:
                line.product_id = product
                line.item_code = product.item_code
                line.name = product.name
                line.uom_id = product.uom_id
                fru = product.alloted_fru or 0
                line.alloted_fru = fru
                if fru and fru > 0:
                    line.unit_price = 200.0
                    line.quantity = float(fru)
                    line.subtotal = float(fru) * 200.0
                else:
                    line.unit_price = product.list_price
                    line.quantity = 1.0
                    line.subtotal = product.list_price or 0.0
                if product.department_id:
                    line.department_id = product.department_id
            else:
                line.product_id = False
                line.item_code = False
                line.name = False
                line.unit_price = 0.0
                line.uom_id = False
                line.alloted_fru = 0
                line.quantity = 0.0
                line.subtotal = 0.0

    @api.onchange('item_code')
    def _onchange_item_code(self):
        for line in self:
            if line.item_code and line.item_code.strip():
                code = line.item_code.strip()
                product = self.env['product.product'].search([
                    ('type', '=', 'service'),
                    ('item_code', '=ilike', code),
                ], limit=1)
                if product:
                    line.item_code_id = product
                    line.product_id = product
                    line.name = product.name
                    line.uom_id = product.uom_id
                    fru = product.alloted_fru or 0
                    line.alloted_fru = fru
                    if fru and fru > 0:
                        line.unit_price = 200.0
                        line.quantity = float(fru)
                        line.subtotal = float(fru) * 200.0
                    else:
                        line.unit_price = product.list_price
                        line.quantity = 1.0
                        line.subtotal = product.list_price or 0.0
                    if product.department_id:
                        line.department_id = product.department_id

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            product = line.product_id
            if product:
                line.item_code = product.item_code
                line.item_code_id = product
                line.name = product.name
                line.uom_id = product.uom_id
                fru = product.alloted_fru or 0
                line.alloted_fru = fru
                if fru and fru > 0:
                    line.unit_price = 200.0
                    line.quantity = float(fru)
                    line.subtotal = float(fru) * 200.0
                else:
                    line.unit_price = product.list_price
                    line.quantity = 1.0
                    line.subtotal = product.list_price or 0.0
                if product.department_id:
                    line.department_id = product.department_id
            else:
                line.item_code = False
                line.item_code_id = False
                line.name = False
                line.unit_price = 0.0
                line.uom_id = False
                line.alloted_fru = 0
                line.quantity = 0.0
                line.subtotal = 0.0

    @api.onchange('department_id')
    def _onchange_department_id_update_product(self):
        for line in self:
            if line.product_id and line.department_id and line.product_id.department_id != line.department_id:
                line.product_id.department_id = line.department_id

    @api.constrains('product_id')
    def _check_service_line_product(self):
        for line in self:
            if line.product_id and line.product_id.type != 'service':
                raise ValidationError(_('Only service products can be added to service lines.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('item_code_id') and not vals.get('product_id'):
                vals['product_id'] = vals['item_code_id']
            elif vals.get('product_id') and not vals.get('item_code_id'):
                vals['item_code_id'] = vals['product_id']
            elif vals.get('item_code') and not vals.get('product_id'):
                product = self.env['product.product'].search([
                    ('type', '=', 'service'),
                    ('item_code', '=ilike', vals['item_code'].strip()),
                ], limit=1)
                if product:
                    vals['product_id'] = product.id
                    vals['item_code_id'] = product.id
            if vals.get('product_id') and 'alloted_fru' not in vals:
                product = self.env['product.product'].browse(vals['product_id'])
                vals['alloted_fru'] = product.alloted_fru or 0
            if vals.get('alloted_fru') and vals['alloted_fru'] > 0 and 'unit_price' not in vals:
                vals['unit_price'] = 200.0
        lines = super().create(vals_list)
        for line in lines:
            if line.product_id and line.department_id and line.product_id.department_id != line.department_id:
                line.product_id.sudo().write({'department_id': line.department_id.id})
            if line.is_timer_running and line.repair_id and line.repair_id.state != 'workorder' and line.repair_id.state not in ('done', 'cancel'):
                line.repair_id.sudo().write({'state': 'workorder'})
        lines._sync_to_work_lines()
        return lines

    def write(self, vals):
        if vals.get('item_code_id') and 'product_id' not in vals:
            vals['product_id'] = vals['item_code_id']
        elif vals.get('product_id') and 'item_code_id' not in vals:
            vals['item_code_id'] = vals['product_id']
        elif vals.get('item_code') and 'product_id' not in vals:
            product = self.env['product.product'].search([
                ('type', '=', 'service'),
                ('item_code', '=ilike', vals['item_code'].strip()),
            ], limit=1)
            if product:
                vals['product_id'] = product.id
                vals['item_code_id'] = product.id
        if vals.get('product_id') and 'alloted_fru' not in vals:
            product = self.env['product.product'].browse(vals['product_id'])
            vals['alloted_fru'] = product.alloted_fru or 0
        if vals.get('alloted_fru') and vals['alloted_fru'] > 0 and 'unit_price' not in vals:
            vals['unit_price'] = 200.0
        res = super().write(vals)
        if 'department_id' in vals:
            for line in self:
                if line.product_id and line.department_id and line.product_id.department_id != line.department_id:
                    line.product_id.sudo().write({'department_id': line.department_id.id})
        if vals.get('is_timer_running'):
            for line in self:
                if line.repair_id and line.repair_id.state != 'workorder' and line.repair_id.state not in ('done', 'cancel'):
                    line.repair_id.sudo().write({'state': 'workorder'})
        if any(k in vals for k in ('is_timer_running', 'timer_last_start', 'accumulated_seconds')):
            for line in self:
                if line.repair_id:
                    line.repair_id._compute_active_service_info()
        sync_trigger_fields = {'timer_start', 'timer_end', 'timer_last_start', 'is_timer_running', 'is_timer_paused', 'accumulated_seconds', 'time_diff', 'employee_id', 'department_id', 'product_id'}
        if any(k in vals for k in sync_trigger_fields):
            self._sync_to_work_lines()
        return res

    def unlink(self):
        work_lines = self.env['fleet.repair.work.line'].sudo().search([('service_line_id', 'in', self.ids)])
        if work_lines:
            work_lines.unlink()
        return super().unlink()


class ServiceDetailLine(models.Model):
    _name = 'service.detail.line'
    _description = 'Service Detail Line'

    service_type = fields.Many2one('service.type', string='Repair Details')
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        domain="[('model_ids.model', '=', 'service.type')]",
        store=True,
        readonly=False
    )
    service_detail_id = fields.Many2one('fleet.repair', string='Car.', copy=False)
    service_detail = fields.Text(string='Repair Details')

    @api.onchange('service_type')
    def _onchange_service_type(self):
        for line in self:
            if line.service_type and line.service_type.department_id:
                line.department_id = line.service_type.department_id

    @api.onchange('department_id')
    def _onchange_department_id_update_service_type(self):
        for line in self:
            if line.service_type and line.department_id and line.service_type.department_id != line.department_id:
                line.service_type.department_id = line.department_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'service_detail_id' in vals:
                repair = self.env['fleet.repair'].browse(vals['service_detail_id'])
                if len(repair.service_detail_line) >= 10:
                    raise ValidationError("You can't enter more than 10 repair details.")
        lines = super().create(vals_list)
        for line in lines:
            if line.service_type and line.department_id and line.service_type.department_id != line.department_id:
                line.service_type.sudo().write({'department_id': line.department_id.id})
        return lines

    def write(self, vals):
        if 'receipt_date' in vals and not self.env.context.get('skip_receipt_date_check'):
            for rec in self:
                if rec.receipt_date and vals.get('receipt_date'):
                    new_dt = fields.Datetime.to_datetime(vals['receipt_date'])
                    if rec.receipt_date != new_dt:
                        raise UserError(_("JC Date cannot be edited once the Job Card is created."))
        res = super().write(vals)
        for rec in self:
            if rec.service_detail_id and len(rec.service_detail_id.service_detail_line) > 10:
                raise ValidationError("You can't enter more than 10 repair details.")
            if 'department_id' in vals and rec.service_type and rec.department_id and rec.service_type.department_id != rec.department_id:
                rec.service_type.sudo().write({'department_id': rec.department_id.id})
        return res


class FleetRepairAnalysis(models.Model):
    _name = 'fleet.repair.analysis'
    _description = "Fleet repair analysis"
    _order = 'id desc'

    id = fields.Integer('fleet Id', readonly=True)
    sequence = fields.Char(string='Sequence', readonly=True)
    receipt_date = fields.Date(string='Date of Receipt', readonly=True)
    state = fields.Selection([
        ('draft', 'Received'),
        ('diagnosis', 'In Diagnosis'),
        ('diagnosis_complete', 'Diagnosis Complete'),
        ('quote', 'Quotation Sent'),
        ('saleorder', 'Quotation Approved'),
        ('workorder', 'Work in Progress'),
        ('work_completed', 'Work Completed'),
        ('invoiced', 'Invoiced'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], 'Status', readonly=True, copy=False, help="Gives the status of the fleet repairing.", index=True)
    client_id = fields.Many2one('res.partner', string='Client', readonly=True)


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    repair_id = fields.Many2one('fleet.repair', string="Car Repair")
    diagnose_id = fields.Many2one('fleet.diagnose', string="Car diagnose")
    workorder_id = fields.Many2one('fleet.workorder', string="Car workorder")
    service_type = fields.Many2one('service.type', string="Nature of Service")
    department_type_id = fields.Many2one('hr.department', string="Service Type")
    timer_start = fields.Datetime('Start Timer')
    timer_end = fields.Datetime('End Timer')
    timer_last_start = fields.Datetime('Last Start Timer')
    is_timer_running = fields.Boolean('Timer Running', default=False)
    is_timer_paused = fields.Boolean('Timer Paused', default=False)
    accumulated_seconds = fields.Float('Accumulated Seconds', default=0.0)
    # timer_duration = fields.Float('Timer Duration (Hours)', compute='_compute_timer_duration', store=True)
    unit_amount = fields.Float(
        compute='_compute_unit_amount',
        store=True
    )

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id and self.employee_id.department_id:
            self.department_type_id = self.employee_id.department_id.id

    @api.depends('timer_start', 'timer_end', 'is_timer_running', 'accumulated_seconds', 'timer_last_start')
    def _compute_unit_amount(self):
        for rec in self:
            total_sec = rec.accumulated_seconds or 0.0
            if rec.is_timer_running and rec.timer_last_start:
                now = fields.Datetime.now()
                delta = now - rec.timer_last_start
                total_sec += delta.total_seconds()
            rec.unit_amount = total_sec / 3600.0

    def action_start_timer(self):
        result = {}
        for rec in self:
            if rec.repair_id and rec.repair_id.state in ('done', 'cancel'):
                raise UserError(_('Cannot start timer when Job Card is in Done or Cancelled state.'))
            if rec.is_timer_running:
                continue
            now = fields.Datetime.now()
            if not rec.timer_start:
                rec.timer_start = now
            rec.timer_last_start = now
            rec.timer_end = False
            rec.is_timer_running = True
            rec.is_timer_paused = False
            if rec.repair_id and rec.repair_id.state != 'workorder' and rec.repair_id.state not in ('done', 'cancel'):
                rec.repair_id.sudo().write({'state': 'workorder'})
            result = {
                'timer_start': fields.Datetime.to_string(rec.timer_start) if rec.timer_start else False,
                'timer_last_start': fields.Datetime.to_string(rec.timer_last_start) if rec.timer_last_start else False,
                'timer_end': False,
                'is_timer_running': True,
                'is_timer_paused': False,
                'accumulated_seconds': rec.accumulated_seconds,
                'time_diff': rec.time_diff,
            }
        return result

    def action_pause_timer(self):
        result = {}
        for rec in self:
            if not rec.is_timer_running:
                continue
            now = fields.Datetime.now()
            if rec.timer_last_start:
                delta = now - rec.timer_last_start
                rec.accumulated_seconds += delta.total_seconds()
            rec.timer_last_start = False
            rec.timer_end = now
            rec.is_timer_running = False
            rec.is_timer_paused = True
            result = {
                'timer_start': fields.Datetime.to_string(rec.timer_start) if rec.timer_start else False,
                'timer_last_start': False,
                'timer_end': fields.Datetime.to_string(rec.timer_end) if rec.timer_end else False,
                'is_timer_running': False,
                'is_timer_paused': True,
                'accumulated_seconds': rec.accumulated_seconds,
                'time_diff': rec.time_diff,
            }
        return result

    def action_stop_timer(self):
        for rec in self:
            if not rec.timer_start and not rec.is_timer_paused and not rec.is_timer_running:
                raise UserError('Timer is not started')
            if rec.timer_end and not rec.is_timer_running:
                raise UserError('Timer is already stopped')
            now = fields.Datetime.now()
            if rec.is_timer_running and rec.timer_last_start:
                delta = now - rec.timer_last_start
                rec.accumulated_seconds += delta.total_seconds()
                rec.timer_last_start = False
            rec.timer_end = now
            rec.is_timer_running = False
            rec.is_timer_paused = False

    def action_reset_timer(self):
        result = {}
        for rec in self:
            rec.write({
                'timer_start': False,
                'timer_last_start': False,
                'timer_end': False,
                'is_timer_running': False,
                'is_timer_paused': False,
                'accumulated_seconds': 0.0,
                'unit_amount': 0.0,
                'time_diff': 0.0,
            })
            result = {
                'timer_start': False,
                'timer_last_start': False,
                'timer_end': False,
                'is_timer_running': False,
                'is_timer_paused': False,
                'accumulated_seconds': 0.0,
                'time_diff': 0.0,
            }
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.is_timer_running and rec.repair_id and rec.repair_id.state != 'workorder' and rec.repair_id.state not in ('done', 'cancel'):
                rec.repair_id.sudo().write({'state': 'workorder'})
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('is_timer_running'):
            for rec in self:
                if rec.repair_id and rec.repair_id.state != 'workorder' and rec.repair_id.state not in ('done', 'cancel'):
                    rec.repair_id.sudo().write({'state': 'workorder'})
        return res

    # @api.depends('service_type', 'unit_amount')
    # def _cal_total_cost(self):
    #     for timesheet in self:
    #         if timesheet.type_id and (timesheet.unit_amount > 0):
    #             timesheet.total_cost = timesheet.service_type.cost * timesheet.unit_amount
    #         else:
    #             timesheet.total_cost = 0.0


# fleet repair work line
class FleetRepairWorkLine(models.Model):
    _name = 'fleet.repair.work.line'
    _description = 'Fleet Repair Work Line'

    service_line_id = fields.Many2one(
        'fleet.repair.service.line',
        string='Service Line',
        ondelete='cascade',
        domain="[('repair_id', '=', repair_id)]"
    )
    employee_id = fields.Many2one('hr.employee', string='Employee')
    repair_id = fields.Many2one('fleet.repair', string='Repair Order', ondelete='cascade', required=True)
    department_type_id = fields.Many2one('hr.department', string='Department')
    work_type = fields.Many2one(
        'product.product',
        string='Work',
        domain="[('type', '=', 'service')]"
    )
    alloted_fru = fields.Integer(
        string='Alloted FRU',
        related='work_type.alloted_fru',
        store=True,
        readonly=True
    )
    unit_price = fields.Float(
        string='Price',
        related='work_type.list_price',
        store=True,
        readonly=True
    )
    timer_start = fields.Datetime('Start Timer')
    timer_end = fields.Datetime('End Timer')
    timer_last_start = fields.Datetime('Last Start Timer')
    is_timer_running = fields.Boolean('Timer Running', default=False)
    is_timer_paused = fields.Boolean('Timer Paused', default=False)
    accumulated_seconds = fields.Float('Accumulated Seconds', default=0.0)
    time_diff = fields.Float(
        compute='_compute_time_diff',
        store=True
    )
    receipt_date = fields.Datetime(related='repair_id.receipt_date', string='JC date', store=True, readonly=True)

    @api.onchange('service_line_id')
    def _onchange_service_line_id(self):
        if self.service_line_id:
            sline = self.service_line_id
            if sline.product_id:
                self.work_type = sline.product_id
            if sline.department_id:
                self.department_type_id = sline.department_id
            if sline.employee_id:
                self.employee_id = sline.employee_id
            self.timer_start = sline.timer_start
            self.timer_end = sline.timer_end
            self.timer_last_start = sline.timer_last_start
            self.is_timer_running = sline.is_timer_running
            self.is_timer_paused = sline.is_timer_paused
            self.accumulated_seconds = sline.accumulated_seconds
            self.time_diff = sline.time_diff

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id and self.employee_id.department_id:
            self.department_type_id = self.employee_id.department_id.id

    @api.onchange('work_type')
    def _onchange_work_type(self):
        if not self.service_line_id and self.repair_id and self.work_type:
            matching = self.repair_id.service_line_ids.filtered(lambda l: l.product_id == self.work_type)
            if matching:
                self.service_line_id = matching[0]
                self._onchange_service_line_id()
                return
        if self.work_type:
            dept = self.work_type.department_id
            if dept:
                self.department_type_id = dept.id
                if self.employee_id and self.employee_id.department_id != dept:
                    self.employee_id = False
                return {
                    'domain': {
                        'employee_id': [('department_id', '=', dept.id)]
                    }
                }
            else:
                return {
                    'domain': {
                        'employee_id': []
                    }
                }
        else:
            return {
                'domain': {
                    'employee_id': []
                }
            }

    @api.depends('timer_start', 'timer_end', 'is_timer_running', 'accumulated_seconds', 'timer_last_start', 'service_line_id.time_diff', 'service_line_id.accumulated_seconds')
    def _compute_time_diff(self):
        for rec in self:
            if rec.service_line_id and not rec.is_timer_running and rec.service_line_id.time_diff:
                rec.time_diff = rec.service_line_id.time_diff
            else:
                total_sec = rec.accumulated_seconds or 0.0
                if rec.is_timer_running and rec.timer_last_start:
                    now = fields.Datetime.now()
                    delta = now - rec.timer_last_start
                    total_sec += delta.total_seconds()
                rec.time_diff = total_sec / 3600.0

    def action_fetch_from_service_line(self):
        for rec in self:
            if rec.service_line_id:
                sline = rec.service_line_id
                rec.with_context(skip_service_line_sync=True).write({
                    'work_type': sline.product_id.id if sline.product_id else False,
                    'department_type_id': sline.department_id.id if sline.department_id else False,
                    'employee_id': sline.employee_id.id if sline.employee_id else False,
                    'timer_start': sline.timer_start,
                    'timer_end': sline.timer_end,
                    'timer_last_start': sline.timer_last_start,
                    'is_timer_running': sline.is_timer_running,
                    'is_timer_paused': sline.is_timer_paused,
                    'accumulated_seconds': sline.accumulated_seconds,
                    'time_diff': sline.time_diff,
                })

    def _sync_to_service_line(self):
        if self.env.context.get('skip_service_line_sync'):
            return
        for rec in self:
            if rec.service_line_id:
                vals = {
                    'timer_start': rec.timer_start,
                    'timer_end': rec.timer_end,
                    'timer_last_start': rec.timer_last_start,
                    'is_timer_running': rec.is_timer_running,
                    'is_timer_paused': rec.is_timer_paused,
                    'accumulated_seconds': rec.accumulated_seconds,
                    'time_diff': rec.time_diff,
                }
                rec.service_line_id.with_context(skip_work_line_sync=True).write(vals)

    def action_start_timer(self):
        result = {}
        for rec in self:
            if rec.repair_id and rec.repair_id.state in ('done', 'cancel'):
                raise UserError(_('Cannot start timer when Job Card is in Done or Cancelled state.'))
            if rec.is_timer_running:
                continue

            now = fields.Datetime.now()
            if not rec.timer_start:
                rec.timer_start = now
            rec.timer_last_start = now
            rec.timer_end = False
            rec.is_timer_running = True
            rec.is_timer_paused = False
            if rec.repair_id and rec.repair_id.state != 'workorder' and rec.repair_id.state not in ('done', 'cancel'):
                rec.repair_id.sudo().write({'state': 'workorder'})
            rec._compute_time_diff()
            rec._sync_to_service_line()
            result = {
                'timer_start': fields.Datetime.to_string(rec.timer_start) if rec.timer_start else False,
                'timer_last_start': fields.Datetime.to_string(rec.timer_last_start) if rec.timer_last_start else False,
                'timer_end': False,
                'is_timer_running': True,
                'is_timer_paused': False,
                'accumulated_seconds': rec.accumulated_seconds,
                'time_diff': rec.time_diff,
            }
        return result

    def action_pause_timer(self):
        result = {}
        for rec in self:
            if not rec.is_timer_running:
                continue

            now = fields.Datetime.now()
            if rec.timer_last_start:
                delta = now - rec.timer_last_start
                rec.accumulated_seconds += delta.total_seconds()
            rec.timer_last_start = False
            rec.timer_end = now
            rec.is_timer_running = False
            rec.is_timer_paused = True
            rec._compute_time_diff()
            rec._sync_to_service_line()
            result = {
                'timer_start': fields.Datetime.to_string(rec.timer_start) if rec.timer_start else False,
                'timer_last_start': False,
                'timer_end': fields.Datetime.to_string(rec.timer_end) if rec.timer_end else False,
                'is_timer_running': False,
                'is_timer_paused': True,
                'accumulated_seconds': rec.accumulated_seconds,
                'time_diff': rec.time_diff,
            }
        return result

    def action_stop_timer(self):
        for rec in self:
            if not rec.timer_start and not rec.is_timer_paused and not rec.is_timer_running:
                raise UserError('Timer is not started')
            if rec.timer_end and not rec.is_timer_running:
                raise UserError('Timer is already stopped')

            now = fields.Datetime.now()
            if rec.is_timer_running and rec.timer_last_start:
                delta = now - rec.timer_last_start
                rec.accumulated_seconds += delta.total_seconds()
                rec.timer_last_start = False

            rec.timer_end = now
            rec.is_timer_running = False
            rec.is_timer_paused = False
            rec._compute_time_diff()
            rec._sync_to_service_line()

    def action_reset_timer(self):
        result = {}
        for rec in self:
            rec.write({
                'timer_start': False,
                'timer_last_start': False,
                'timer_end': False,
                'is_timer_running': False,
                'is_timer_paused': False,
                'accumulated_seconds': 0.0,
                'time_diff': 0.0,
            })
            rec._sync_to_service_line()
            result = {
                'timer_start': False,
                'timer_last_start': False,
                'timer_end': False,
                'is_timer_running': False,
                'is_timer_paused': False,
                'accumulated_seconds': 0.0,
                'time_diff': 0.0,
            }
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.is_timer_running and rec.repair_id and rec.repair_id.state != 'workorder' and rec.repair_id.state not in ('done', 'cancel'):
                rec.repair_id.sudo().write({'state': 'workorder'})
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('is_timer_running'):
            for rec in self:
                if rec.repair_id and rec.repair_id.state != 'workorder' and rec.repair_id.state not in ('done', 'cancel'):
                    rec.repair_id.sudo().write({'state': 'workorder'})
        if not self.env.context.get('skip_service_line_sync'):
            sync_fields = {'timer_start', 'timer_end', 'timer_last_start', 'is_timer_running', 'is_timer_paused', 'accumulated_seconds', 'time_diff'}
            if any(k in vals for k in sync_fields):
                self._sync_to_service_line()
        return res


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'
    _rec_name = 'license_plate'

    vin_sn = fields.Char(string='Chassis Number', required=True)
    driver_id = fields.Many2one('res.partner', string='Client', required=True)
    odometer = fields.Float(string='Last Odometer', required=True)
    client_phone = fields.Char(string='Mobile 1', related='driver_id.phone', readonly=False, store=True, required=True)

    @api.onchange('driver_id')
    def _onchange_driver_id_phone(self):
        if self.driver_id and self.driver_id.phone:
            self.client_phone = self.driver_id.phone

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        print("=== DEBUG FleetVehicle.default_get CALLED ===")
        print(f"Context: {self._context}")
        print(f"res: {res}")
        _logger.info("DEBUG: FleetVehicle.default_get called with context=%s, res=%s", self._context, res)
        if self._context.get('default_name') and not res.get('license_plate'):
            res['license_plate'] = self._context.get('default_name')
        if self._context.get('default_vin_sn') and not res.get('vin_sn'):
            res['vin_sn'] = self._context.get('default_vin_sn')
        if self._context.get('default_driver_id') and not res.get('driver_id'):
            res['driver_id'] = self._context.get('default_driver_id')
        if self._context.get('default_client_phone') and not res.get('client_phone'):
            res['client_phone'] = self._context.get('default_client_phone')
        elif res.get('driver_id') and not res.get('client_phone'):
            driver = self.env['res.partner'].browse(res['driver_id'])
            if driver.phone:
                res['client_phone'] = driver.phone
        if self._context.get('default_odometer') and not res.get('odometer'):
            try:
                res['odometer'] = float(self._context.get('default_odometer') or 0.0)
            except (ValueError, TypeError):
                pass
        return res

    @api.model_create_multi
    def create(self, vals_list):
        print("=== DEBUG FleetVehicle.create CALLED ===")
        print(f"vals_list: {vals_list}")
        _logger.info("DEBUG: FleetVehicle.create called with vals_list=%s", vals_list)
        records = super().create(vals_list)
        for rec, vals in zip(records, vals_list):
            if 'driver_id' in vals and vals['driver_id'] and not rec.driver_id:
                rec.driver_id = vals['driver_id']
                print(f"Explicitly assigned driver_id={vals['driver_id']} to FleetVehicle ID={rec.id}")
                _logger.info("DEBUG: Explicitly assigned driver_id=%s to FleetVehicle ID=%s", vals['driver_id'], rec.id)
            if 'client_phone' in vals and vals['client_phone'] and rec.driver_id:
                rec.driver_id.phone = vals['client_phone']
            print(f"Created FleetVehicle ID={rec.id}, Plate={rec.license_plate}, Driver={rec.driver_id}")
            _logger.info("DEBUG: Created FleetVehicle ID=%s, Plate=%s, Driver=%s", rec.id, rec.license_plate, rec.driver_id)
        return records

    @api.depends('license_plate')
    def _compute_display_name(self):
        for record in self:
            if record.license_plate:
                record.display_name = record.license_plate
            else:
                super()._compute_display_name()

    @api.model
    def _get_latest_vehicle_ids(self, driver_id=None):
        """
        Returns IDs of fleet.vehicle records with the latest registration date
        (acquisition_date DESC NULLS LAST, create_date DESC, id DESC) for each license plate,
        optionally filtered by driver_id.
        """
        query = """
            SELECT DISTINCT ON (LOWER(TRIM(license_plate))) id
            FROM fleet_vehicle
            WHERE license_plate IS NOT NULL AND TRIM(license_plate) != ''
        """
        params = []
        if driver_id:
            query += " AND driver_id = %s"
            params.append(driver_id)

        query += " ORDER BY LOWER(TRIM(license_plate)), acquisition_date DESC NULLS LAST, create_date DESC, id DESC"

        self.env.cr.execute(query, params)
        latest_ids = [r[0] for r in self.env.cr.fetchall()]

        where_clause = "WHERE (license_plate IS NULL OR TRIM(license_plate) = '')"
        if driver_id:
            where_clause += " AND driver_id = %s"
            self.env.cr.execute(f"SELECT id FROM fleet_vehicle {where_clause}", [driver_id])
        else:
            self.env.cr.execute(f"SELECT id FROM fleet_vehicle {where_clause}")
        no_plate_ids = [r[0] for r in self.env.cr.fetchall()]

        return list(set(latest_ids + no_plate_ids))

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        domain = list(domain or [])
        driver_id = False
        for leaf in domain:
            if isinstance(leaf, (list, tuple)) and len(leaf) == 3 and leaf[0] == 'driver_id' and leaf[1] == '=':
                driver_id = leaf[2]
                break

        if not driver_id and self._context.get('default_driver_id'):
            driver_id = self._context.get('default_driver_id')

        latest_ids = self._get_latest_vehicle_ids(driver_id=driver_id)
        domain.append(('id', 'in', latest_ids))

        return super()._name_search(name=name, domain=domain, operator=operator, limit=limit, order=order)

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = list(args or [])
        driver_id = False
        for leaf in args:
            if isinstance(leaf, (list, tuple)) and len(leaf) == 3 and leaf[0] == 'driver_id' and leaf[1] == '=':
                driver_id = leaf[2]
                break

        if not driver_id and self._context.get('default_driver_id'):
            driver_id = self._context.get('default_driver_id')

        latest_ids = self._get_latest_vehicle_ids(driver_id=driver_id)
        args.append(('id', 'in', latest_ids))

        return super().name_search(name=name, args=args, operator=operator, limit=limit)



class FleetVehicleModel(models.Model):
    _inherit = 'fleet.vehicle.model'

    default_fuel_type = fields.Selection(default=False)




