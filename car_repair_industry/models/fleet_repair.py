# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from datetime import date, time, datetime
from odoo import tools
from pytz import timezone
from odoo.exceptions import UserError, ValidationError


class FleetRepair(models.Model):
    _name = 'fleet.repair'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Car Repair"
    _rec_name = 'sequence'
    _order = 'id desc'

    license_plate = fields.Char(
        related='fleet_id.license_plate',
        string='License Plate',
        store=True, readonly=False)
    vin_sn = fields.Char(
        related='fleet_id.vin_sn',
        string='Chassis Number',
        store=True, readonly=False)
    model_name = fields.Char(
        string="Model",
        related='fleet_id.model_id.name',
        store=True,
        readonly=False
    )
    kilometers_num = fields.Char(string="KMS")
    name = fields.Char(string='Subject')
    sequence = fields.Char(string='Sequence', readonly=True, copy=False)
    client_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    client_phone = fields.Char(string='Phone')
    client_mobile = fields.Char(string='Mobile')
    client_email = fields.Char(string='Email')
    receipt_date = fields.Datetime(string='JC Date',default=fields.Datetime.now)
    contact_name = fields.Char(string='Contact Name')
    phone = fields.Char(string='Contact Number')
    fleet_id = fields.Many2one('fleet.vehicle', 'Car')
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
    user_id = fields.Many2one('res.users', string='Assigned to', tracking=True)
    priority = fields.Selection([('0', 'Low'), ('1', 'Normal'), ('2', 'High')], 'Priority')
    description = fields.Text(string='Notes')
    service_detail = fields.Text(string='Service Details')
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
    feedback_description = fields.Char(string="Feedback")
    rating = fields.Selection([('0', 'Low'), ('1', 'Normal'), ('2', 'High')], string="Rating")
    timesheet_ids = fields.One2many('account.analytic.line', 'repair_id', string="Timesheet")
    planned_hours = fields.Float("Initially Planned Hours", tracking=True)
    subtask_planned_hours = fields.Float("Sub-tasks Planned Hours", compute='_compute_subtask_planned_hours',
                                         help="Sum of the hours allocated for all the sub-tasks (and their own sub-tasks) linked to this task. Usually less than or equal to the allocated hours of this task.")

    job_card_display = fields.Char(
        string='Job Card',
        compute='_compute_job_card_display',
        store=False
    )

    product_line_ids = fields.One2many('fleet.repair.product.line', 'repair_id', string='Product Lines')
    # amount_total = fields.Monetary(string="Total Amount", compute="_compute_amount_total", store=True)
    # currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    amount_untaxed = fields.Monetary(string='Untaxed Amount', compute='_compute_total', store=True)
    amount_total = fields.Monetary(string='Total', compute='_compute_total', store=True)
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

    promised_date = fields.Datetime(string="Promised Delivery Date",default=fields.Datetime.now, required=True)

    # This field will control the decoration color
    delivery_status_color = fields.Selection([
        ('green', 'Delivered'),
        ('yellow', 'On Track'),
        ('red', 'Delayed')
    ], compute="_compute_delivery_status_color", store=True)

    @api.depends('promised_date', 'receipt_date')
    def _compute_delivery_status_color(self):
        today = fields.Date.today()
        for record in self:
            record.delivery_status_color = False
            if record.promised_date and record.receipt_date:
                # Convert both datetime fields to date before comparing
                promised_date = record.promised_date.date()
                receipt_date = record.receipt_date.date()

                if receipt_date <= today < promised_date:
                    record.delivery_status_color = 'green'
                elif today == promised_date:
                    record.delivery_status_color = 'yellow'
                elif today > promised_date:
                    record.delivery_status_color = 'red'

    @api.depends('product_line_ids.subtotal')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(line.subtotal for line in rec.product_line_ids)

    def _cron_update_delivery_colors(self):
        repairs = self.sudo().search([])
        print("hello")
        repairs._compute_delivery_status_color()

    @api.depends('product_line_ids.subtotal')
    def _compute_total(self):
        for rec in self:
            rec.amount_untaxed = sum(line.subtotal for line in rec.product_line_ids)
            rec.amount_total = rec.amount_untaxed

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

    def action_create_invoice_fleet(self):
        self.ensure_one()

        if self.invoice_order_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Invoice',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.invoice_order_id.id,
            }

        if not self.product_line_ids:
            raise UserError("Cannot create invoice: No product lines found.")

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
                'product_uom_id': line.uom_id.id,
                'tax_ids': [(6, 0, [])],
            }))

        if not invoice_lines:
            raise UserError("All product lines are empty or invalid.")

        invoice = self.env['account.move'].create({
            'partner_id': self.client_id.id,
            'move_type': 'out_invoice',
            'journal_id': journal.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': invoice_lines,
            'fleet_repair_invoice_id': self.id,  # custom field, define it if needed
        })

        self.invoice_order_id = invoice.id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
        }

    @api.depends('sequence')
    def _compute_job_card_display(self):
        for rec in self:
            seq = rec.sequence or ''
            rec.job_card_display = f"Job Card No : {seq}"

    @api.model_create_multi
    def create(self, vals_list):
        self.env.cr.execute("SELECT COALESCE(MAX(CAST(sequence AS INTEGER)), 0) FROM fleet_repair")
        last_seq = self.env.cr.fetchone()[0]

        for vals in vals_list:
            last_seq += 1
            vals['sequence'] = str(last_seq)

        return super(FleetRepair, self).create(vals_list)

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
        list = []
        context = dict(self._context or {})
        invoice_order_ids = self.env['account.move'].search([
            ('state', 'in', ['draft', 'posted'])
            , ('fleet_repair_invoice_id', '=', self.id)
        ])
        for order in invoice_order_ids:
            list.append(order.id)

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
        addr = {}
        if self.client_id:
            addr = self.client_id.address_get(['contact'])
            addr['client_phone'] = self.client_id.phone
            addr['client_mobile'] = self.client_id.mobile
            addr['client_email'] = self.client_id.email
        return {'value': addr}

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
            timesheet_line_vals = {
                'date': rec.date,
                'diagnose_id': diagnose_id.id,
                'project_id': rec.project_id.id,
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
    service_detail = fields.Text(string='Service Details')
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

    @api.onchange('fleet_id')
    def onchange_fleet_id(self):
        addr = {}
        if self.fleet_id:
            fleet = self.fleet_id
            addr['license_plate'] = fleet.license_plate
            addr['vin_sn'] = fleet.vin_sn
            addr['fuel_type'] = fleet.fuel_type
            addr['model_id'] = fleet.model_id.id
        return {'value': addr}


class FleetRepairProductLine(models.Model):
    _name = 'fleet.repair.product.line'
    _description = 'Fleet Repair Product Line'

    repair_id = fields.Many2one('fleet.repair', string='Repair Order', ondelete='cascade', required=True)

    # Both product and item_code point to product.template now
    product_id = fields.Many2one('product.product', string='Item')
    item_code_id = fields.Many2one(
        'product.product',
        string='Item Code Search',
    )

    item_code_display = fields.Char(
        string="Item Code",
        related='item_code_id.item_code',
        readonly=False,
        store=True
    )

    name = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    unit_price = fields.Float(string='Unit Price')
    subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal', store=True)
    currency_id = fields.Many2one('res.currency', related='repair_id.currency_id', store=True, readonly=True)

    # @api.depends('item_code_id')
    # def _compute_item_code_display(self):
    #     for rec in self:
    #         rec.item_code_display = rec.item_code_id.item_code if rec.item_code_id else ''

    def write(self, vals):
        for record in self:
            print(vals)
            print(record.item_code_id.item_code)
        return super().write(vals)

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price

    @api.onchange('item_code_id')
    def _onchange_item_code_id(self):
        for line in self:
            product = line.item_code_id
            if product:
                line.product_id = product
                line.name = product.name
                line.unit_price = product.list_price
                line.uom_id = product.uom_id
            else:
                line.product_id = False
                line.name = False
                line.unit_price = 0.0
                line.uom_id = False

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """When product is selected, populate item code and details."""
        for line in self:
            product = line.product_id
            if product:
                line.name = product.name
                line.unit_price = product.list_price
                line.uom_id = product.uom_id
                line.item_code_id = product if product.item_code else False
            else:
                line.item_code_id = False
                line.name = False
                line.unit_price = 0.0
                line.uom_id = False


class ServiceDetailLine(models.Model):
    _name = 'service.detail.line'
    _description = 'Service Detail Line'

    service_type = fields.Many2one('service.type', string='Nature of Service')
    service_detail_id = fields.Many2one('fleet.repair', string='Car.', copy=False)
    service_detail = fields.Text(string='Service Details')


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
    service_type = fields.Many2one('service.type', string="Service Type")

    @api.depends('service_type', 'unit_amount')
    def _cal_total_cost(self):
        for timesheet in self:
            if timesheet.type_id and (timesheet.unit_amount > 0):
                timesheet.total_cost = timesheet.service_type.cost * timesheet.unit_amount
            else:
                timesheet.total_cost = 0.0
