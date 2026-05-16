# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class FleetRepairStock(models.Model):
    _inherit = 'fleet.repair'

    delivery_picking_ids = fields.One2many(
        'stock.picking',
        'fleet_repair_id',
        string='Part Deliveries',
    )

    def _get_fleet_warehouse(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', company.id)], limit=1
        )
        if not warehouse:
            raise UserError(
                _('No warehouse configured for company %s.') % company.display_name
            )
        return warehouse


class StockPickingFleetRepair(models.Model):
    _inherit = 'stock.picking'

    fleet_repair_id = fields.Many2one('fleet.repair', string='Job Card', index=True, copy=False)
    fleet_repair_invoice_id = fields.Many2one('account.move', string='Job Card Invoice', index=True, copy=False)


class AccountMoveFleetRepairStock(models.Model):
    _inherit = 'account.move'

    fleet_delivery_picking_ids = fields.One2many(
        'stock.picking',
        'fleet_repair_invoice_id',
        string='Job Card Deliveries',
        copy=False,
    )
    fleet_delivery_count = fields.Integer(
        string='Delivery Count',
        compute='_compute_fleet_delivery_stats',
    )
    fleet_delivery_pending = fields.Boolean(
        string='Delivery To Validate',
        compute='_compute_fleet_delivery_stats',
    )

    @api.depends('fleet_delivery_picking_ids.state', 'state')
    def _compute_fleet_delivery_stats(self):
        for move in self:
            pickings = move.fleet_delivery_picking_ids.filtered(lambda p: p.state != 'cancel')
            move.fleet_delivery_count = len(pickings)
            move.fleet_delivery_pending = bool(
                pickings.filtered(lambda p: p.state not in ('done',))
            )

    def _fleet_repair_is_job_card_invoice(self):
        self.ensure_one()
        return bool(
            self.create_form_fleet
            and self.fleet_repair_invoice_id
            and self.move_type == 'out_invoice'
        )

    def _fleet_repair_get_customer_location(self):
        self.ensure_one()
        partner = self.partner_id
        location = partner.with_company(self.company_id).property_stock_customer
        if not location:
            location = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        if not location:
            raise UserError(_('No customer stock location configured.'))
        return location

    def _fleet_repair_get_storable_invoice_lines(self):
        self.ensure_one()
        return self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product'
            and l.product_id
            and l.product_id.is_storable
            and not float_is_zero(l.quantity, precision_rounding=l.product_uom_id.rounding)
        )

    def _fleet_repair_create_stock_delivery(self):
        """Create and reserve an outgoing picking (not validated yet)."""
        Picking = self.env['stock.picking']
        created = Picking

        for invoice in self:
            if not invoice._fleet_repair_is_job_card_invoice():
                continue
            if invoice.fleet_delivery_picking_ids.filtered(lambda p: p.state != 'cancel'):
                continue

            repair = invoice.fleet_repair_invoice_id
            warehouse = repair._get_fleet_warehouse()
            dest_location = invoice._fleet_repair_get_customer_location()
            storable_lines = invoice._fleet_repair_get_storable_invoice_lines()
            if not storable_lines:
                continue

            move_commands = []
            for line in storable_lines:
                product = line.product_id
                qty = line.product_uom_id._compute_quantity(line.quantity, product.uom_id)
                if float_is_zero(qty, precision_rounding=product.uom_id.rounding):
                    continue
                available = product.with_context(warehouse_id=warehouse.id).free_qty
                if float_compare(qty, available, precision_rounding=product.uom_id.rounding) > 0:
                    raise UserError(_(
                        'Not enough stock for "%(product)s". '
                        'Required: %(req)s %(uom)s, Available: %(avail)s %(uom)s (%(wh)s).',
                        product=product.display_name,
                        req=qty,
                        avail=available,
                        uom=product.uom_id.name,
                        wh=warehouse.name,
                    ))
                move_commands.append((0, 0, {
                    'name': product.display_name,
                    'product_id': product.id,
                    'product_uom_qty': qty,
                    'product_uom': product.uom_id.id,
                    'location_id': warehouse.lot_stock_id.id,
                    'location_dest_id': dest_location.id,
                    'company_id': invoice.company_id.id,
                }))

            if not move_commands:
                continue

            picking = Picking.create({
                'picking_type_id': warehouse.out_type_id.id,
                'partner_id': invoice.partner_id.id,
                'origin': _('Job Card %s / %s') % (
                    repair.sequence or repair.display_name,
                    invoice.name or invoice.display_name,
                ),
                'location_id': warehouse.lot_stock_id.id,
                'location_dest_id': dest_location.id,
                'company_id': invoice.company_id.id,
                'fleet_repair_id': repair.id,
                'fleet_repair_invoice_id': invoice.id,
                'move_ids': move_commands,
            })
            picking.action_confirm()
            picking.action_assign()
            for move in picking.move_ids:
                if float_is_zero(move.product_uom_qty, precision_rounding=move.product_uom.rounding):
                    continue
                move.quantity = move.product_uom_qty
                move.picked = True
            created |= picking

        return created

    def _fleet_repair_process_stock_delivery(self):
        """On invoice post: create delivery only; user validates to Done manually."""
        self._fleet_repair_create_stock_delivery()

    def action_view_fleet_deliveries(self):
        """Open delivery transfer(s); prefer not-done pickings for manual validation."""
        self.ensure_one()
        pickings = self.fleet_delivery_picking_ids.filtered(lambda p: p.state != 'cancel')
        pending = pickings.filtered(lambda p: p.state not in ('done',))
        action = self.env['ir.actions.actions']._for_xml_id('stock.action_picking_tree_all')
        if len(pickings) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = pickings.id
        elif len(pending) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = pending.id
        else:
            action['domain'] = [('id', 'in', (pending or pickings).ids)]
        action['context'] = dict(self.env.context, default_fleet_repair_invoice_id=self.id)
        return action


    def _fleet_repair_return_delivery_pickings(self):
        """Return done job-card deliveries when the invoice is reset to draft."""
        ReturnPicking = self.env['stock.return.picking']

        for invoice in self:
            if not invoice.fleet_repair_invoice_id:
                continue
            pickings = invoice.fleet_delivery_picking_ids.filtered(lambda p: p.state == 'done')
            for picking in pickings:
                if picking.return_ids.filtered(lambda p: p.state not in ('cancel',)):
                    continue
                wizard = ReturnPicking.with_context(
                    active_id=picking.id,
                    active_model='stock.picking',
                ).create({'picking_id': picking.id})
                for return_line in wizard.product_return_moves:
                    stock_move = return_line.move_id
                    if not stock_move or stock_move.state == 'cancel':
                        continue
                    return_line.quantity = stock_move.quantity
                new_picking = wizard._create_return()
                new_picking.write({
                    'fleet_repair_id': picking.fleet_repair_id.id,
                    'fleet_repair_invoice_id': picking.fleet_repair_invoice_id.id,
                })
                for move in new_picking.move_ids:
                    if float_is_zero(move.product_uom_qty, precision_rounding=move.product_uom.rounding):
                        continue
                    move.quantity = move.product_uom_qty
                    move.picked = True
                validate_result = new_picking.button_validate()
                if validate_result is not True and isinstance(validate_result, dict):
                    return validate_result
        return True
