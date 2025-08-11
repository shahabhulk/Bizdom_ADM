# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from datetime import date, time, datetime
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    diagnose_id = fields.Many2one('fleet.diagnose', string='Car Diagnosis', readonly=True)
    fleet_repair_id = fields.Many2one('fleet.repair', string='Car Repair')
    workorder_id = fields.Many2one('fleet.workorder', string='Repair Work Order', readonly=True)
    is_workorder_created = fields.Boolean(string="Workorder Created")
    count_fleet_repair = fields.Integer(string='Repair Orders', compute='_compute_repair_id')
    workorder_count = fields.Integer(string='Work Orders', compute='_compute_workorder_id')

    @api.depends('fleet_repair_id')
    def _compute_repair_id(self):
        for order in self:
            repair_order_ids = self.env['fleet.repair'].search([('sale_order_id', '=', order.id)])
            order.count_fleet_repair = len(repair_order_ids)

    @api.depends('is_workorder_created')
    def _compute_workorder_id(self):
        for order in self:
            work_order_ids = self.env['fleet.workorder'].search([('sale_order_id', '=', order.id)])
            order.workorder_count = len(work_order_ids)

    def workorder_created(self):
        self.write({'state': 'workorder'})

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        order = self
        order.state = 'sale'
        fleet_line_obj = self.env['fleet.repair.line']
        if order.diagnose_id:
            wo_vals = {
                'name': order.diagnose_id.name,
                'date': order.date_order.date() if order.date_order else False,
                'client_id': order.diagnose_id.client_id.id,
                'sale_order_id': order.id,
                'fleet_repair_id': order.diagnose_id.fleet_repair_id.id,
                'diagnose_id': order.diagnose_id.id,
                'hour': sum((line.est_ser_hour for line in order.diagnose_id.fleet_repair_line), 0.0),
                'priority': order.diagnose_id.priority,
                'state': 'draft',
                'user_id': order.diagnose_id.user_id.id,
                'confirm_sale_order': True,
            }
            wo_id = self.env['fleet.workorder'].create(wo_vals)
            for line in order.diagnose_id.fleet_repair_line:
                fleet_line_vals = {
                    'workorder_id': wo_id,
                }
                line.write({'workorder_id': wo_id.id})
                fleet_line_obj.write({'fleet_repair_line': line.id})

            diag_id = order.diagnose_id.id
            diagnose_obj = self.env['fleet.diagnose'].browse(diag_id)
            diagnose_obj.is_workorder_created = True
            diagnose_obj.confirm_sale_order = True
            if diagnose_obj.fleet_repair_id:
                repair_id = [diagnose_obj.fleet_repair_id.id]
                browse_record = self.env['fleet.repair'].browse(repair_id)
                browse_record.state = 'saleorder'
                browse_record.workorder_id = wo_id.id
                browse_record.confirm_sale_order = True
            self.write({'workorder_id': wo_id.id, 'fleet_repair_id': diagnose_obj.fleet_repair_id.id,
                        'is_workorder_created': True})
        return res

    def button_view_repair(self):
        list = []
        context = dict(self._context or {})
        repair_order_ids = self.env['fleet.repair'].search([('sale_order_id', '=', self.id)])
        for order in repair_order_ids:
            list.append(order.id)
        return {
            'name': _('Fleet Repair'),
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'fleet.repair',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', list)],
            'context': context,
        }

    def button_view_workorder(self):
        list = []
        context = dict(self._context or {})
        work_order_ids = self.env['fleet.workorder'].search([('sale_order_id', '=', self.id)])
        for order in work_order_ids:
            list.append(order.id)
        return {
            'name': _('Fleet Work Order'),
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'fleet.workorder',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', list)],
            'context': context,
        }

    # TO CREATE WORKORDER ON SHIP CREATE ###

    def action_view_work_order(self):
        mod_obj = self.env['ir.model.data']
        act_obj = self.env['ir.actions.act_window']
        work_order_id = self.workorder_id.id
        result = mod_obj._xmlid_lookup("%s.%s" % ('car_repair_industry', 'action_fleet_workorder_tree_view'))
        id = result and result[1] or False
        result = act_obj.browse(id).read()[0]
        res = mod_obj._xmlid_lookup("%s.%s" % ('car_repair_industry', 'view_fleet_workorder_form'))
        result['views'] = [(res and res[1] or False, 'form')]
        result['res_id'] = work_order_id or False
        return result


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"
    _description = "Sales Advance Payment Invoice"

    def create_invoices(self):
        res = super(SaleAdvancePaymentInv, self).create_invoices()
        if self._context.get('active_id'):
            sale_obj = self.env['sale.order'].browse(self._context.get('active_id'))
            if sale_obj.diagnose_id and sale_obj.diagnose_id.fleet_repair_id:
                sale_obj.diagnose_id.fleet_repair_id.write({'state': 'invoiced'})
        return res


class AccountInvoice(models.Model):
    _inherit = "account.move"

    create_form_fleet = fields.Boolean(string='Fleet')
    fleet_repair_invoice_id = fields.Many2one('fleet.repair')
    license_plate = fields.Char(related='fleet_repair_invoice_id.license_plate', store=True)
    model_name = fields.Char(related='fleet_repair_invoice_id.model_name', store=True)
    vin_sn = fields.Char(related='fleet_repair_invoice_id.vin_sn', store=True)

    # def _prepare_product_base_line_for_taxes_computation(self, line):
    #     res = super()._prepare_product_base_line_for_taxes_computation(line)
    #     if line.labour_charges:
    #         quantity = line.quantity or 1.0
    #         res['price_unit'] += line.labour_charges / quantity
    #     return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('invoice_origin'):
                sale_obj = self.env['sale.order'].search([('name', '=', vals.get('invoice_origin'))])
                invoice_line_ids = vals.get('invoice_line_ids', [])

                if sale_obj and sale_obj.workorder_id and sale_obj.workorder_id.fleet_repair_id:
                    vals.update({'create_form_fleet': True})
                    repair_obj = self.env['fleet.repair.line'].browse(sale_obj.workorder_id.fleet_repair_line.id)
                    for line_vals in invoice_line_ids:
                        car_model = line_vals[2].get('car_model')
                        license_plate = line_vals[2].get('license_plate')
                        product = line_vals[2].get('name')
                        product_id = line_vals[2].get('product_id')
                        product_template = self.env['product.product'].browse(product_id)
                        model_id = self.env['fleet.vehicle.model'].search([('name', '=', car_model)], limit=1)
                        license_id = self.env['fleet.repair.line'].search([('license_plate', '=', license_plate)],
                                                                          limit=1)
                        detailed_type = product_template.type
                        if repair_obj.guarantee == 'yes':
                            if repair_obj.guarantee_type == 'free':
                                if not (model_id and license_id) or detailed_type == 'consu':
                                    line_vals[2].update({
                                        'quantity': 0,
                                    })
                                else:
                                    line_vals[2].update({
                                        'quantity': line_vals[2].get('quantity'),
                                    })
                            elif repair_obj.guarantee_type == 'paid':
                                line_vals[2].update({
                                    'quantity': line_vals[2].get('quantity'),
                                })
        return super(AccountInvoice, self).create(vals_list)

    def write(self, vals):
        if vals.get('state'):
            if vals.get('state') == 'posted':
                for move in self:
                    sale_obj = self.env['sale.order'].search([('name', '=', move.invoice_origin)])
                    if sale_obj and sale_obj.workorder_id and sale_obj.workorder_id.fleet_repair_id:
                        repair_obj = self.env['fleet.repair'].search(
                            [('id', '=', sale_obj.workorder_id.fleet_repair_id.id)])
                        repair_obj.write({'state': 'done'})
                        template_id = self.env.ref('car_repair_industry.car_repair_service_done').id
                        template = self.env['mail.template'].browse(template_id)
                        template.send_mail(repair_obj.id, force_send=True)
        return super(AccountInvoice, self).write(vals)


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def send_mail(self, auto_commit=False):
        if self._context.get('default_model') == 'sale.order' and self._context.get(
                'default_res_id') and self._context.get('mark_so_as_sent'):
            order = self.env['sale.order'].browse([self._context['default_res_id']])
            if order.state == 'draft':
                order.state = 'sent'
                if order.diagnose_id and order.diagnose_id.fleet_repair_id:
                    order.diagnose_id.fleet_repair_id.write({'state': 'quote'})
            self = self.with_context(mail_post_autofollow=True)
        return super(MailComposeMessage, self).send_mail(auto_commit=auto_commit)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    license_plate = fields.Char(string="License Plate")
    car_model = fields.Char(string="Model #")

    def _prepare_invoice_line(self, **optional_values):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        """
        self.ensure_one()
        res = {
            'license_plate': self.license_plate,
            'car_model': self.car_model,
            'sequence': self.sequence,
            'name': self.name,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom.id,
            'quantity': self.qty_to_invoice,
            'discount': self.discount,
            'price_unit': self.price_unit,
            'tax_ids': [(6, 0, self.tax_id.ids)],
            'sale_line_ids': [(4, self.id)],
        }
        if self.display_type:
            res['account_id'] = False
        return res


class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'

    license_plate = fields.Char(string="License Plate")
    car_model = fields.Char(string="Model #")
    department_id = fields.Many2one('hr.department', string='Department')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    name = fields.Char(string='Description')
    # item_code = fields.Char(string="Item Code")

    # labour_charges = fields.Monetary(
    #     string='Labour Charge',
    #     currency_field='currency_id',
    #     store=True
    # )

    item_code = fields.Char(
        string="Item Code",
        related='product_id.item_code',
        store=True,
        readonly=False  # Optional: make editable if needed
    )

    @api.onchange('department_id')
    def _onchange_department_id(self):
        for line in self:
            if line.department_id:
                return {
                    'domain': {
                        'employee_id': [('department_id', '=', line.department_id.id)]
                    }
                }
            else:
                return {
                    'domain': {
                        'employee_id': []
                    }
                }


    @api.model
    def create(self, vals):
        line = super().create(vals)
        line._sync_labour_billing()
        return line

    def write(self, vals):
        res = super().write(vals)
        self._sync_labour_billing()
        return res

    def _sync_labour_billing(self):
        for line in self:
            if line.employee_id and line.price_subtotal > 0:
                existing = self.env['labour.billing'].search([('invoice_line_id', '=', line.id)], limit=1)
                if existing:
                    existing.write({
                        'charge_amount': line.price_subtotal,
                        'employee_id': line.employee_id.id,
                        'date': line.move_id.invoice_date or fields.Date.today(),
                    })
                else:
                    self.env['labour.billing'].create({
                        'employee_id': line.employee_id.id,
                        'charge_amount': line.price_subtotal,
                        'date': line.move_id.invoice_date or fields.Date.today(),
                        'invoice_line_id': line.id
                    })

    #
    # @api.onchange('labour_charges')
    # def _onchange_labour(self):
    #     for line in self:
    #         line._compute_totals()
    #         if line.move_id:
    #             line.move_id._compute_amount()