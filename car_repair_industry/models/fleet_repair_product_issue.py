# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero


class FleetRepairProductLineIssue(models.Model):
    _inherit = 'fleet.repair.product.line'

    qty_issued = fields.Float(
        string='Issued',
        default=0.0,
        copy=False,
        readonly=True,
    )
    qty_to_return = fields.Float(
        string='Return Qty',
        default=0.0,
        digits='Product Unit of Measure',
        help='Quantity to send back to shelf when clicking Return.',
    )
    qty_to_issue = fields.Float(
        string='To Issue',
        compute='_compute_issue_flags',
        digits='Product Unit of Measure',
    )
    can_issue = fields.Boolean(compute='_compute_issue_flags')
    can_return = fields.Boolean(compute='_compute_issue_flags')
    issue_picking_ids = fields.Many2many(
        'stock.picking',
        'fleet_repair_product_line_issue_picking_rel',
        'line_id',
        'picking_id',
        string='Issue Transfers',
        copy=False,
        readonly=True,
    )
    cost_price = fields.Float(
        string='Cost Price',
        digits='Product Price',
        compute='_compute_cost_price',
        store=True,
        readonly=True,
        help='Weighted average FIFO unit cost from stock valuation / purchase order when parts are issued or selected.',
    )
    cost_subtotal = fields.Monetary(
        string='Cost Total',
        compute='_compute_cost_margin',
        store=True,
        currency_field='currency_id',
    )
    margin = fields.Monetary(
        string='Margin',
        compute='_compute_cost_margin',
        store=True,
        currency_field='currency_id',
    )
    margin_percent = fields.Float(
        string='Margin %',
        compute='_compute_cost_margin',
        store=True,
        digits=(16, 2),
    )
    issue_cost_line_ids = fields.One2many(
        'fleet.repair.product.line.cost',
        'repair_line_id',
        string='FIFO Cost Breakdown',
        copy=False,
        readonly=True,
    )
    returned_vendor_stock_ids = fields.One2many(
        'fleet.repair.returned.vendor.stock',
        'repair_line_id',
        string='Returned Vendor Stock',
        copy=False,
        readonly=True,
    )
    vendor_cost_summary = fields.Char(
        string='Vendors / Costs',
        compute='_compute_vendor_cost_summary',
        help='Per-vendor FIFO unit costs from each issue.',
    )

    @api.depends(
        'issue_cost_line_ids.vendor_name',
        'issue_cost_line_ids.quantity',
        'issue_cost_line_ids.unit_cost',
        'issue_cost_line_ids.uom_id',
    )
    def _compute_vendor_cost_summary(self):
        for line in self:
            parts = []
            rounding = (line.uom_id or line.product_id.uom_id).rounding if line.product_id else 0.01
            for cost_line in line.issue_cost_line_ids.filtered(lambda c: float_compare(c.quantity, 0.0, precision_rounding=rounding) > 0):
                vendor = cost_line.vendor_name or _('Unknown')
                parts.append(
                    '%(vendor)s: %(cost).2f × %(qty).2f %(uom)s'
                    % {
                        'vendor': vendor,
                        'cost': cost_line.unit_cost,
                        'qty': cost_line.quantity,
                        'uom': cost_line.uom_id.name if cost_line.uom_id else '',
                    }
                )
            line.vendor_cost_summary = '; '.join(parts)

    @api.depends(
        'product_id',
        'uom_id',
        'qty_issued',
        'issue_cost_line_ids',
        'issue_cost_line_ids.unit_cost',
        'issue_cost_line_ids.quantity',
    )
    def _compute_cost_price(self):
        for line in self:
            if not line.product_id:
                line.cost_price = 0.0
                continue
            line.cost_price = line._recompute_cost_price_from_cost_lines()

    @api.depends('unit_price', 'qty_issued', 'cost_price', 'quantity')
    def _compute_cost_margin(self):
        for line in self:
            qty = line.qty_issued if line.qty_issued > 0 else line.quantity
            revenue = line.unit_price * qty
            line.cost_subtotal = line.cost_price * qty
            line.margin = revenue - line.cost_subtotal
            line.margin_percent = (line.margin / revenue * 100.0) if revenue else 0.0

    @api.onchange('qty_issued')
    def _onchange_qty_issued_cap_return(self):
        for line in self:
            if not line.product_id:
                continue
            rounding = (line.uom_id or line.product_id.uom_id).rounding
            if float_compare(line.qty_to_return, line.qty_issued, precision_rounding=rounding) > 0:
                line.qty_to_return = line.qty_issued

    def _find_repair_order(self):
        self.ensure_one()
        if self.repair_id:
            return self.repair_id
        if self._origin and self._origin.repair_id:
            return self._origin.repair_id
        ctx = self.env.context
        repair_id = ctx.get('default_repair_id') or ctx.get('repair_id')
        if repair_id:
            return self.env['fleet.repair'].browse(repair_id)
        if ctx.get('active_model') == 'fleet.repair' and ctx.get('active_id'):
            return self.env['fleet.repair'].browse(ctx.get('active_id'))
        params = ctx.get('params') or {}
        if isinstance(params, dict):
            if params.get('model') == 'fleet.repair' and params.get('id'):
                return self.env['fleet.repair'].browse(params.get('id'))
            if params.get('id'):
                return self.env['fleet.repair'].browse(params.get('id'))
        return self.env['fleet.repair']

    def _refresh_stock_qty_cache(self):
        """Invalidate and recompute onhand_qty and available_qty across all product lines on the repair order."""
        for line in self:
            repair = line.repair_id or line._find_repair_order()
            if repair and repair.product_line_ids:
                lines = repair.product_line_ids
                lines.invalidate_recordset(['onhand_qty', 'available_qty'])
                lines._compute_onhand_qty()
                lines._compute_available_qty()
            else:
                line.invalidate_recordset(['onhand_qty', 'available_qty'])
                line._compute_onhand_qty()
                line._compute_available_qty()

    @api.onchange('quantity', 'product_id', 'uom_id')
    def _onchange_quantity_sync_stock_instant(self):
        for line in self:
            if not line.product_id or not line.product_id.is_storable:
                continue

            origin = line._origin
            if origin and origin.exists() and origin.repair_id:
                # Update existing database line and execute stock transfer in real-time
                rounding = (line.uom_id or line.product_id.uom_id).rounding
                if float_compare(line.quantity, origin.quantity, precision_rounding=rounding) != 0:
                    origin.with_context(skip_auto_stock_sync=True).write({'quantity': line.quantity})
                    origin._auto_sync_stock_issue_return()
                    line.qty_issued = origin.qty_issued
                    line.cost_price = origin.cost_price

            line._compute_onhand_qty()
            line._compute_available_qty()

    @api.depends('quantity', 'qty_issued', 'product_id', 'product_id.is_storable')
    def _compute_issue_flags(self):
        for line in self:
            rounding = (line.uom_id or line.product_id.uom_id).rounding if line.product_id else 0.01
            to_issue = max(line.quantity - line.qty_issued, 0.0)
            line.qty_to_issue = to_issue
            line.can_return = (
                line.product_id
                and line.product_id.is_storable
                and float_compare(line.qty_issued, 0.0, precision_rounding=rounding) > 0
            )
            line.can_issue = (
                line.product_id
                and line.product_id.is_storable
                and float_compare(to_issue, 0.0, precision_rounding=rounding) > 0
            )

    def _get_stock_location(self):
        self.ensure_one()
        warehouse = self._get_warehouse()
        if not warehouse:
            raise UserError(
                _('No warehouse configured for company %s.')
                % (self.repair_id.company_id.name or self.env.company.name)
            )
        return warehouse.lot_stock_id

    def _get_production_location(self):
        self.ensure_one()
        company = self.repair_id.company_id or self.env.company
        location = self.env['stock.location'].search([
            ('usage', '=', 'production'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not location:
            raise UserError(
                _('No production location configured for company %s.') % company.display_name
            )
        return location

    def _convert_qty(self, qty, from_uom, to_uom):
        if from_uom and to_uom and from_uom != to_uom:
            return from_uom._compute_quantity(qty, to_uom)
        return qty

    def _get_available_qty_at_stock(self, product=None):
        """Available quantity on warehouse stock location, in line UoM."""
        self.ensure_one()
        product = product or self.product_id
        if not product or not product.is_storable:
            return 0.0
        location = self._get_stock_location()
        qty = self.env['stock.quant']._get_available_quantity(
            product, location, strict=True,
        )
        line_uom = self.uom_id or product.uom_id
        return self._convert_qty(qty, product.uom_id, line_uom)

    def _get_available_qty(self, product, warehouse):
        """Shelf availability for display (adm/Stock), in line UoM (allowing negative stock)."""
        if not product or not product.is_storable:
            return 0.0
        line_uom = self.uom_id or product.uom_id
        location = warehouse.lot_stock_id if warehouse else False
        if location:
            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id', 'child_of', location.id),
            ])
            if quants:
                qty = sum(quants.mapped('quantity')) - sum(quants.mapped('reserved_quantity'))
            else:
                qty = self.env['stock.quant']._get_available_quantity(
                    product.sudo(), location, strict=True, allow_negative=True,
                )
        else:
            qty = product.with_context(warehouse_id=warehouse.id).free_qty if warehouse else 0.0
        return self._convert_qty(qty, product.uom_id, line_uom)

    def _get_product_available_qty(self, product, warehouse):
        """Available on stock location in product default UoM (allowing negative stock)."""
        if not product or not product.is_storable:
            return 0.0
        location = warehouse.lot_stock_id if warehouse else False
        if location:
            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id', 'child_of', location.id),
            ])
            if quants:
                return sum(quants.mapped('quantity')) - sum(quants.mapped('reserved_quantity'))
            return self.env['stock.quant']._get_available_quantity(
                product.sudo(), location, strict=True, allow_negative=True,
            )
        return product.with_context(warehouse_id=warehouse.id).free_qty if warehouse else 0.0

    def _get_repair_pending_issue_qty(self, product):
        """Sum (quantity - qty_issued) for product on this repair, in product UoM."""
        self.ensure_one()
        total = 0.0
        for line in self.repair_id.product_line_ids.filtered(lambda l: l.product_id == product):
            line_uom = line.uom_id or product.uom_id
            pending = max(line.quantity - line.qty_issued, 0.0)
            total += line_uom._compute_quantity(pending, product.uom_id)
        return total

    def _prepare_issue_qty_product_uom(self):
        self.ensure_one()
        product = self.product_id
        line_uom = self.uom_id or product.uom_id
        qty_to_issue = max(self.quantity - self.qty_issued, 0.0)
        return line_uom._compute_quantity(qty_to_issue, product.uom_id)

    def _peek_fifo_unit_cost(self, qty_product_uom):
        """Estimate FIFO unit cost from remaining valuation layers (no consumption)."""
        self.ensure_one()
        product = self.product_id
        if float_is_zero(qty_product_uom, precision_rounding=product.uom_id.rounding):
            return 0.0
        if 'stock.valuation.layer' not in self.env:
            return product.standard_price

        company = self.repair_id.company_id or self.env.company
        product_company = product.with_company(company)
        domain = product_company._get_fifo_candidates_domain(company) if hasattr(
            product_company, '_get_fifo_candidates_domain'
        ) else [
            ('product_id', '=', product.id),
            ('company_id', '=', company.id),
            ('remaining_qty', '>', 0),
        ]
        layers = self.env['stock.valuation.layer'].sudo().search(
            domain, order='create_date ASC, id ASC',
        )
        qty_left = qty_product_uom
        total_value = 0.0
        for layer in layers:
            if float_is_zero(qty_left, precision_rounding=product.uom_id.rounding):
                break
            take = min(qty_left, layer.remaining_qty)
            if float_is_zero(take, precision_rounding=product.uom_id.rounding):
                continue
            if float_is_zero(layer.remaining_qty, precision_rounding=product.uom_id.rounding):
                continue
            unit = layer.unit_cost or (
                layer.remaining_value / layer.remaining_qty
            )
            total_value += take * unit
            qty_left -= take

        consumed = qty_product_uom - qty_left
        if not float_is_zero(consumed, precision_rounding=product.uom_id.rounding):
            unit_cost_product_uom = total_value / consumed
            line_uom = self.uom_id or product.uom_id
            return self._convert_qty(unit_cost_product_uom, product.uom_id, line_uom)
        return 0.0

    def _get_last_purchase_order_line(self):
        self.ensure_one()
        company = self.repair_id.company_id or self.env.company
        return self.env['purchase.order.line'].search([
            ('product_id', '=', self.product_id.id),
            ('order_id.company_id', '=', company.id),
            ('order_id.state', 'in', ('purchase', 'done')),
        ], order='id desc', limit=1)

    def _get_last_purchase_unit_cost(self):
        """Fallback: latest confirmed purchase order line price for this product."""
        self.ensure_one()
        product = self.product_id
        po_line = self._get_last_purchase_order_line()
        if not po_line:
            return 0.0
        line_uom = self.uom_id or product.uom_id
        unit_cost = po_line.price_unit
        if po_line.product_uom != product.uom_id:
            unit_cost = po_line.product_uom._compute_price(unit_cost, product.uom_id)
        return self._convert_qty(unit_cost, product.uom_id, line_uom)

    def _get_last_receipt_unit_cost(self):
        """Fallback: unit cost from the latest done incoming move's valuation layers."""
        self.ensure_one()
        product = self.product_id
        company = self.repair_id.company_id or self.env.company
        move = self.env['stock.move'].search([
            ('product_id', '=', product.id),
            ('state', '=', 'done'),
            ('company_id', '=', company.id),
            ('picking_id.picking_type_id.code', '=', 'incoming'),
        ], order='date desc, id desc', limit=1)
        if not move or 'stock.valuation.layer' not in self.env:
            return 0.0
        total_value = 0.0
        total_qty = 0.0
        for svl in move.sudo().stock_valuation_layer_ids:
            qty = abs(svl.quantity)
            if float_is_zero(qty, precision_rounding=svl.uom_id.rounding):
                continue
            total_qty += qty
            if not float_is_zero(svl.value, precision_rounding=0.01):
                total_value += abs(svl.value)
            elif not float_is_zero(svl.unit_cost, precision_rounding=0.0001):
                total_value += abs(svl.unit_cost) * qty
        if float_is_zero(total_qty, precision_rounding=0.0001):
            return 0.0
        line_uom = self.uom_id or product.uom_id
        unit_cost = total_value / total_qty
        if float_is_zero(unit_cost, precision_rounding=0.0001):
            return 0.0
        return self._convert_qty(unit_cost, product.uom_id, line_uom)

    def _get_fifo_unit_cost_from_moves(self, moves, qty_product_uom=None):
        """FIFO unit cost from stock valuation layers on validated stock moves."""
        self.ensure_one()
        product = self.product_id
        moves = moves.filtered(lambda m: m.product_id == product and m.state == 'done')
        if not moves:
            return self._resolve_unit_cost_fallback(qty_product_uom)

        if 'stock.valuation.layer' in self.env:
            total_value = 0.0
            total_qty = 0.0
            has_svl = False
            for move in moves:
                for svl in move.sudo().stock_valuation_layer_ids:
                    has_svl = True
                    if float_is_zero(svl.quantity, precision_rounding=svl.uom_id.rounding):
                        continue
                    qty = abs(svl.quantity)
                    if float_is_zero(qty, precision_rounding=svl.uom_id.rounding):
                        continue
                    total_qty += qty
                    if not float_is_zero(svl.value, precision_rounding=0.01):
                        total_value += abs(svl.value)
                    elif not float_is_zero(svl.unit_cost, precision_rounding=0.0001):
                        total_value += abs(svl.unit_cost) * qty
            if has_svl and not float_is_zero(total_qty, precision_rounding=0.0001):
                unit_cost_product_uom = total_value / total_qty
                if not float_is_zero(unit_cost_product_uom, precision_rounding=0.0001):
                    line_uom = self.uom_id or product.uom_id
                    return self._convert_qty(unit_cost_product_uom, product.uom_id, line_uom)

        return self._resolve_unit_cost_fallback(qty_product_uom)

    def _resolve_unit_cost_fallback(self, qty_product_uom=None):
        self.ensure_one()
        product = self.product_id
        if qty_product_uom is None:
            qty_product_uom = self._prepare_issue_qty_product_uom()

        unit_cost = self._peek_fifo_unit_cost(qty_product_uom)
        if not float_is_zero(unit_cost, precision_rounding=0.0001):
            return unit_cost

        unit_cost = self._get_last_receipt_unit_cost()
        if not float_is_zero(unit_cost, precision_rounding=0.0001):
            return unit_cost

        unit_cost = self._get_last_purchase_unit_cost()
        if not float_is_zero(unit_cost, precision_rounding=0.0001):
            return unit_cost

        return product.standard_price

    def _get_fifo_unit_cost_from_picking(self, picking, qty_product_uom=None):
        self.ensure_one()
        self.env.flush_all()
        picking.invalidate_recordset(['move_ids'])
        return self._get_fifo_unit_cost_from_moves(picking.move_ids, qty_product_uom=qty_product_uom)

    def _get_fifo_candidate_layers(self):
        self.ensure_one()
        product = self.product_id
        company = self.repair_id.company_id or self.env.company
        product_company = product.with_company(company)
        if hasattr(product_company, '_get_fifo_candidates_domain'):
            domain = product_company._get_fifo_candidates_domain(company)
        else:
            domain = [
                ('product_id', '=', product.id),
                ('company_id', '=', company.id),
                ('remaining_qty', '>', 0),
            ]
        candidates = self.env['stock.valuation.layer'].sudo().search(
            domain, order='create_date ASC, id ASC',
        )
        if not candidates:
            candidates = self.env['stock.valuation.layer'].sudo().search([
                ('product_id', '=', product.id),
                ('company_id', '=', company.id),
                ('remaining_qty', '>', 0),
            ], order='create_date ASC, id ASC')
        return candidates

    def _get_incoming_purchase_moves_fifo(self):
        """Done receipt moves for this product (oldest first), linked to purchase."""
        self.ensure_one()
        product = self.product_id
        company = self.repair_id.company_id or self.env.company
        warehouse = self._get_warehouse()
        stock_location = warehouse.lot_stock_id
        moves = self.env['stock.move'].search([
            ('product_id', '=', product.id),
            ('state', '=', 'done'),
            ('company_id', '=', company.id),
            '|',
            ('location_dest_id', '=', stock_location.id),
            ('location_dest_id', 'child_of', stock_location.id),
            '|',
            ('purchase_line_id', '!=', False),
            ('picking_id.purchase_id', '!=', False),
        ], order='date ASC, id ASC')
        return moves

    def _get_available_qty_on_move_layers(self, move):
        svls = move.stock_valuation_layer_ids.filtered(
            lambda s: float_compare(s.remaining_qty, 0.0, precision_rounding=s.uom_id.rounding) > 0
        )
        if svls:
            return sum(svls.mapped('remaining_qty'))
        svls = self.env['stock.valuation.layer'].sudo().search([
            ('stock_move_id', '=', move.id),
            ('remaining_qty', '>', 0),
        ])
        return sum(svls.mapped('remaining_qty'))

    def _get_move_received_qty_product_uom(self, move):
        """Quantity received on this stock move in product default UoM."""
        self.ensure_one()
        product = self.product_id
        if float_is_zero(move.quantity, precision_rounding=move.product_uom.rounding):
            return move.product_uom._compute_quantity(move.product_uom_qty, product.uom_id)
        return move.product_uom._compute_quantity(move.quantity, product.uom_id)

    def _get_move_unit_cost_product_uom(self, move, available_qty):
        self.ensure_one()
        product = self.product_id
        if move.purchase_line_id:
            cost = move.purchase_line_id.price_unit
            pol_uom = move.purchase_line_id.product_uom
            if pol_uom and pol_uom != product.uom_id:
                cost = pol_uom._compute_price(cost, product.uom_id)
            return cost
        svls = move.stock_valuation_layer_ids.filtered(lambda s: s.remaining_qty > 0)
        if svls and available_qty:
            total_val = sum(svls.mapped('remaining_value'))
            total_qty = sum(svls.mapped('remaining_qty'))
            if not float_is_zero(total_qty, precision_rounding=product.uom_id.rounding):
                return total_val / total_qty
        return product.standard_price

    def _build_fifo_plan_from_purchase_receipts(self, qty_product_uom):
        """FIFO plan from PO receipts (vendor from purchase_line_id / PO)."""
        self.ensure_one()
        product = self.product_id
        rounding = product.uom_id.rounding
        qty_left = qty_product_uom
        plan = []

        for move in self._get_incoming_purchase_moves_fifo():
            if float_is_zero(qty_left, precision_rounding=rounding):
                break
            layer_available = self._get_available_qty_on_move_layers(move)
            received_qty = self._get_move_received_qty_product_uom(move)
            available = layer_available
            if not float_is_zero(received_qty, precision_rounding=rounding):
                if float_is_zero(layer_available, precision_rounding=rounding):
                    available = received_qty
                else:
                    available = min(layer_available, received_qty)
            if float_is_zero(available, precision_rounding=rounding):
                continue
            qty_take = min(qty_left, available)
            svls = move.stock_valuation_layer_ids.filtered(lambda s: s.remaining_qty > 0)
            if not svls:
                svls = self.env['stock.valuation.layer'].sudo().search([
                    ('stock_move_id', '=', move.id),
                    ('remaining_qty', '>', 0),
                ], limit=1)
            plan.append({
                'svl': svls[0] if svls else self.env['stock.valuation.layer'],
                'consumed_qty': qty_take,
                'unit_cost': self._get_move_unit_cost_product_uom(move, available),
                'vendor': self._get_vendor_from_stock_move(move),
            })
            qty_left -= qty_take

        return plan, qty_left

    def _build_plan_from_returned_vendor_stock(self, qty_product_uom):
        """Consume returned vendor pool first (preserves Vendor A vs B after return to shelf)."""
        self.ensure_one()
        product = self.product_id
        line_uom = self.uom_id or product.uom_id
        rounding = line_uom.rounding
        qty_left_line = product.uom_id._compute_quantity(qty_product_uom, line_uom)
        plan = []
        ReturnedStock = self.env['fleet.repair.returned.vendor.stock']
        stocks = ReturnedStock.search([
            ('repair_line_id', '=', self.id),
            ('quantity', '>', 0),
        ], order='id ASC')

        for stock in stocks:
            if float_is_zero(qty_left_line, precision_rounding=rounding):
                break
            take_line = min(qty_left_line, stock.quantity)
            if float_is_zero(take_line, precision_rounding=rounding):
                continue
            consumed_product = line_uom._compute_quantity(take_line, product.uom_id)
            unit_cost_product = stock.unit_cost
            if line_uom != product.uom_id:
                unit_cost_product = line_uom._compute_price(stock.unit_cost, product.uom_id)
            plan.append({
                'svl': stock.svl_source_id,
                'consumed_qty': consumed_product,
                'consumed_qty_line': take_line,
                'unit_cost': unit_cost_product,
                'vendor': stock.vendor_id,
                'returned_stock_id': stock.id,
            })
            qty_left_line -= take_line

        qty_left_product = line_uom._compute_quantity(qty_left_line, product.uom_id)
        return plan, qty_left_product

    def _consume_returned_vendor_stock(self, fifo_plan):
        self.ensure_one()
        ReturnedStock = self.env['fleet.repair.returned.vendor.stock']
        line_uom = self.uom_id or self.product_id.uom_id
        rounding = line_uom.rounding
        for item in fifo_plan:
            stock_id = item.get('returned_stock_id')
            if not stock_id:
                continue
            stock = ReturnedStock.browse(stock_id)
            if not stock.exists():
                continue
            take_line = item.get('consumed_qty_line')
            if take_line is None:
                take_line = self.product_id.uom_id._compute_quantity(
                    item['consumed_qty'], line_uom,
                )
            new_qty = max(stock.quantity - take_line, 0.0)
            stock.quantity = new_qty

    def _restore_returned_vendor_stock(self, returned_batches, return_picking):
        """Remember which vendor batches were returned so re-issue uses the same vendors."""
        self.ensure_one()
        if not returned_batches:
            return
        ReturnedStock = self.env['fleet.repair.returned.vendor.stock']
        for batch in returned_batches:
            if float_is_zero(batch['quantity'], precision_rounding=(self.uom_id or self.product_id.uom_id).rounding):
                continue
            vendor_id = batch.get('vendor_id') or False
            vendor_name = batch.get('vendor_name') or _('Unknown')
            domain = [
                ('repair_line_id', '=', self.id),
                ('vendor_id', '=', vendor_id),
            ]
            if batch.get('unit_cost') is not None:
                domain.append(('unit_cost', '=', batch['unit_cost']))
            existing = ReturnedStock.search(domain, limit=1)
            if existing:
                existing.quantity += batch['quantity']
                if return_picking and not existing.return_picking_id:
                    existing.return_picking_id = return_picking.id
            else:
                ReturnedStock.create({
                    'repair_line_id': self.id,
                    'vendor_id': vendor_id,
                    'vendor_name': vendor_name,
                    'quantity': batch['quantity'],
                    'unit_cost': batch['unit_cost'],
                    'return_picking_id': return_picking.id if return_picking else False,
                    'svl_source_id': batch.get('svl_source_id') or False,
                })

    def _get_fifo_issue_plan(self, qty_product_uom, fifo_snapshot=None):
        """Returned vendor pool first, then FIFO valuation layers / PO receipts."""
        self.ensure_one()
        if fifo_snapshot is None:
            fifo_candidates = self._get_fifo_candidate_layers()
            fifo_snapshot = self._snapshot_fifo_layers(fifo_candidates)

        plan, qty_left = self._build_plan_from_returned_vendor_stock(qty_product_uom)
        rounding = self.product_id.uom_id.rounding
        if not float_is_zero(qty_left, precision_rounding=rounding):
            remainder = self._build_fifo_plan_from_snapshot(qty_left, fifo_snapshot)
            if not remainder:
                rec_plan, qty_left2 = self._build_fifo_plan_from_purchase_receipts(qty_left)
                remainder = rec_plan
                if not float_is_zero(qty_left2, precision_rounding=rounding):
                    remainder.extend(self._build_fifo_plan_from_snapshot(qty_left2, fifo_snapshot))
            plan.extend(remainder)

        return self._assign_vendors_to_plan_from_svl(plan)

    def _assign_vendors_to_plan_from_svl(self, fifo_plan):
        """Each FIFO layer row gets the vendor from its own receipt/PO (not all from vendor A)."""
        self.ensure_one()
        used_po_line_ids = set()
        for item in fifo_plan:
            if item.get('vendor'):
                continue
            svl = item.get('svl')
            vendor = self.env['res.partner']
            if svl and svl.id:
                vendor = self._get_vendor_from_incoming_svl(svl)
            if not vendor:
                vendor = self._get_vendor_by_po_price_match_fifo(
                    item.get('unit_cost', 0.0), used_po_line_ids,
                )
            item['vendor'] = vendor
        return fifo_plan

    def _consolidate_plan_by_vendor_and_cost(self, fifo_plan):
        """One display row per vendor + unit cost (e.g. Vendor A x2, Vendor B x1)."""
        consolidated = []
        bucket_index = {}
        for item in fifo_plan:
            vendor = item.get('vendor') or self.env['res.partner']
            unit_cost = item.get('unit_cost', 0.0)
            key = (vendor.id, unit_cost)
            if key in bucket_index:
                consolidated[bucket_index[key]]['consumed_qty'] += item['consumed_qty']
            else:
                bucket_index[key] = len(consolidated)
                consolidated.append(dict(item))
        return consolidated

    def _snapshot_fifo_layers(self, candidates):
        return {
            svl.id: (svl.remaining_qty, svl.remaining_value)
            for svl in candidates
        }

    def _build_fifo_plan_from_snapshot(self, qty_product_uom, fifo_snapshot):
        """FIFO plan from pre-validate snapshot (reliable for multi-vendor single Issue)."""
        self.ensure_one()
        product = self.product_id
        rounding = product.uom_id.rounding
        qty_left = qty_product_uom
        plan = []
        if not fifo_snapshot:
            return plan

        snapshot_svls = self.env['stock.valuation.layer'].sudo().browse(list(fifo_snapshot.keys()))
        for svl in snapshot_svls.sorted(key=lambda svl: (svl.create_date, svl.id)):
            if float_is_zero(qty_left, precision_rounding=rounding):
                break
            qty_before, value_before = fifo_snapshot[svl.id]
            if float_is_zero(qty_before, precision_rounding=rounding):
                continue
            qty_take = min(qty_left, qty_before)
            unit_cost = value_before / qty_before
            plan.append({
                'svl': svl,
                'consumed_qty': qty_take,
                'unit_cost': unit_cost,
            })
            qty_left -= qty_take

        if not float_is_zero(qty_left, precision_rounding=rounding):
            plan.append({
                'svl': self.env['stock.valuation.layer'],
                'consumed_qty': qty_left,
                'unit_cost': product.standard_price,
            })
        return plan

    def _get_vendor_from_stock_move(self, move):
        if not move:
            return self.env['res.partner']
        if move.purchase_line_id:
            return move.purchase_line_id.order_id.partner_id
        picking = move.picking_id
        if picking:
            if picking.purchase_id:
                return picking.purchase_id.partner_id
            purchase_moves = picking.move_ids.filtered('purchase_line_id')
            if purchase_moves:
                return purchase_moves[0].purchase_line_id.order_id.partner_id
            if picking.partner_id:
                return picking.partner_id
        if move.group_id:
            po = self.env['purchase.order'].search([
                ('name', '=', move.group_id.name),
                ('company_id', '=', move.company_id.id),
            ], limit=1)
            if po:
                return po.partner_id
        if move.origin:
            origin_key = move.origin.split(',')[0].strip()
            po = self.env['purchase.order'].search([
                ('name', '=', origin_key),
                ('company_id', '=', move.company_id.id),
            ], limit=1)
            if po:
                return po.partner_id
        return self.env['res.partner']

    def _get_vendor_from_incoming_svl(self, svl):
        if not svl:
            return self.env['res.partner']
        move = svl.stock_move_id
        vendor = self._get_vendor_from_stock_move(move)
        if vendor:
            return vendor
        parent = svl.stock_valuation_layer_id
        if parent and parent != svl:
            vendor = self._get_vendor_from_incoming_svl(parent)
            if vendor:
                return vendor
        return self.env['res.partner']

    def _get_vendor_by_po_price_match_fifo(self, unit_cost_product, used_po_line_ids=None):
        """Match vendor from PO lines (FIFO order), one PO line per plan row."""
        self.ensure_one()
        used_po_line_ids = used_po_line_ids if used_po_line_ids is not None else set()
        product = self.product_id
        company = self.repair_id.company_id or self.env.company
        po_lines = self.env['purchase.order.line'].search([
            ('product_id', '=', product.id),
            ('order_id.company_id', '=', company.id),
            ('order_id.state', 'in', ('purchase', 'done')),
            ('qty_received', '>', 0),
        ], order='date_order ASC, id ASC')
        for po_line in po_lines:
            if po_line.id in used_po_line_ids:
                continue
            po_cost = po_line.price_unit
            if po_line.product_uom != product.uom_id:
                po_cost = po_line.product_uom._compute_price(po_cost, product.uom_id)
            if float_compare(po_cost, unit_cost_product, precision_rounding=0.01) == 0:
                used_po_line_ids.add(po_line.id)
                return po_line.order_id.partner_id
        return self.env['res.partner']

    def _get_vendor_by_po_price_match(self, unit_cost_product):
        return self._get_vendor_by_po_price_match_fifo(unit_cost_product, set())

    def _resolve_vendor_for_fifo_batch(self, svl, unit_cost_product):
        vendor = self._get_vendor_from_incoming_svl(svl)
        if vendor:
            return vendor
        return self._get_vendor_by_po_price_match(unit_cost_product)

    def _create_issue_cost_lines_from_plan(self, picking, move, fifo_plan):
        """Create one cost line per vendor batch (e.g. Vendor A x2 + Vendor B x1)."""
        self.ensure_one()
        CostLine = self.env['fleet.repair.product.line.cost']
        product = self.product_id
        line_uom = self.uom_id or product.uom_id
        issue_date = picking.date_done or fields.Datetime.now()
        created = CostLine
        fifo_plan = self._consolidate_plan_by_vendor_and_cost(fifo_plan)

        for item in fifo_plan:
            consumed_qty = item['consumed_qty']
            if float_is_zero(consumed_qty, precision_rounding=product.uom_id.rounding):
                continue
            svl = item.get('svl')
            unit_cost_product = item['unit_cost']
            unit_cost_line = self._convert_qty(unit_cost_product, product.uom_id, line_uom)
            qty_line = product.uom_id._compute_quantity(consumed_qty, line_uom)
            vendor = item.get('vendor') or self._resolve_vendor_for_fifo_batch(
                svl, unit_cost_product,
            )
            created |= CostLine.create({
                'repair_line_id': self.id,
                'picking_id': picking.id,
                'stock_move_id': move.id if move else False,
                'svl_source_id': svl.id if svl else False,
                'vendor_id': vendor.id,
                'vendor_name': vendor.display_name if vendor else _('Unknown'),
                'quantity': qty_line,
                'unit_cost': unit_cost_line,
                'issue_date': issue_date,
            })
        return created

    def _create_issue_cost_lines_from_fifo_diff(self, picking, move, before_snapshot):
        """Post-validate layer diff fallback (with cache refresh)."""
        self.ensure_one()
        CostLine = self.env['fleet.repair.product.line.cost']
        product = self.product_id
        line_uom = self.uom_id or product.uom_id
        rounding = product.uom_id.rounding
        issue_date = picking.date_done or fields.Datetime.now()

        if not before_snapshot:
            return CostLine

        created = CostLine
        svl_ids = list(before_snapshot.keys())
        svls = self.env['stock.valuation.layer'].sudo().browse(svl_ids)
        svls.invalidate_recordset(['remaining_qty', 'remaining_value'])
        for svl in svls.exists():
            qty_before, value_before = before_snapshot[svl.id]
            consumed_qty = qty_before - svl.remaining_qty
            if float_is_zero(consumed_qty, precision_rounding=rounding):
                continue
            consumed_value = value_before - svl.remaining_value
            unit_cost_product = abs(consumed_value / consumed_qty) if consumed_qty else 0.0
            unit_cost_line = self._convert_qty(unit_cost_product, product.uom_id, line_uom)
            qty_line = product.uom_id._compute_quantity(consumed_qty, line_uom)
            vendor = self._resolve_vendor_for_fifo_batch(svl, unit_cost_product)
            created |= CostLine.create({
                'repair_line_id': self.id,
                'picking_id': picking.id,
                'stock_move_id': move.id if move else False,
                'svl_source_id': svl.id,
                'vendor_id': vendor.id,
                'vendor_name': vendor.display_name if vendor else _('Unknown'),
                'quantity': qty_line,
                'unit_cost': unit_cost_line,
                'issue_date': issue_date,
            })
        return created

    def _create_issue_cost_lines_fallback(self, picking, move, qty_product_uom):
        """Last resort: PO-receipt plan again, else one line from SVL/PO."""
        self.ensure_one()
        plan, _qty_left = self._build_fifo_plan_from_purchase_receipts(qty_product_uom)
        if plan:
            created = self._create_issue_cost_lines_from_plan(picking, move, plan)
            if created:
                return created

        product = self.product_id
        line_uom = self.uom_id or product.uom_id
        issued_line_uom = product.uom_id._compute_quantity(qty_product_uom, line_uom)
        fifo_unit_cost = self._get_fifo_unit_cost_from_picking(
            picking, qty_product_uom=qty_product_uom,
        )
        po_line = self._get_last_purchase_order_line()
        po_vendor = po_line.order_id.partner_id if po_line else self.env['res.partner']
        return self.env['fleet.repair.product.line.cost'].create({
            'repair_line_id': self.id,
            'picking_id': picking.id,
            'stock_move_id': move.id if move else False,
            'vendor_id': po_vendor.id if po_vendor else False,
            'vendor_name': po_vendor.display_name if po_vendor else _('Unknown'),
            'quantity': issued_line_uom,
            'unit_cost': fifo_unit_cost,
            'issue_date': picking.date_done or fields.Datetime.now(),
            'is_fallback': True,
        })

    def _get_latest_purchase_cost_and_vendor(self):
        self.ensure_one()
        product = self.product_id
        if not product:
            return 0.0, False, ''
        line_uom = self.uom_id or product.uom_id
        company = self.repair_id.company_id or self.env.company

        moves = self.env['stock.move'].search([
            ('product_id', '=', product.id),
            ('state', '=', 'done'),
            ('company_id', '=', company.id),
            '|',
            ('purchase_line_id', '!=', False),
            ('picking_id.purchase_id', '!=', False),
        ], order='date DESC, id DESC', limit=1)

        if moves:
            move = moves[0]
            vendor = self._get_vendor_from_stock_move(move)
            unit_cost_product = self._get_move_unit_cost_product_uom(move, 0.0)
            unit_cost_line = self._convert_qty(unit_cost_product, product.uom_id, line_uom)
            return unit_cost_line, vendor.id if vendor else False, vendor.display_name if vendor else ''

        po_line = self._get_last_purchase_order_line()
        if po_line:
            po_cost = po_line.price_unit
            pol_uom = po_line.product_uom
            if pol_uom and pol_uom != line_uom:
                po_cost = pol_uom._compute_price(po_cost, line_uom)
            vendor = po_line.order_id.partner_id
            return po_cost, vendor.id if vendor else False, vendor.display_name if vendor else ''

        std_price = self._convert_qty(product.standard_price, product.uom_id, line_uom)
        return std_price, False, ''

    def _update_fallback_cost_lines_from_latest_purchase(self):
        for line in self:
            fallback_cost_lines = line.issue_cost_line_ids.filtered(
                lambda cl: cl.is_fallback or not cl.svl_source_id
            )
            if not fallback_cost_lines:
                continue
            unit_cost, vendor_id, vendor_name = line._get_latest_purchase_cost_and_vendor()
            if unit_cost:
                fallback_cost_lines.write({
                    'unit_cost': unit_cost,
                    'vendor_id': vendor_id,
                    'vendor_name': vendor_name or _('Unknown'),
                })

    def _recompute_cost_price_from_cost_lines(self):
        self.ensure_one()
        self._update_fallback_cost_lines_from_latest_purchase()
        rounding = (self.uom_id or self.product_id.uom_id).rounding if self.product_id else 0.01
        cost_lines = self.issue_cost_line_ids.filtered(lambda c: float_compare(c.quantity, 0.0, precision_rounding=rounding) > 0)
        total_qty = sum(cost_lines.mapped('quantity'))
        if float_is_zero(total_qty, precision_rounding=rounding):
            unit_cost, _vendor_id, _vendor_name = self._get_latest_purchase_cost_and_vendor()
            return unit_cost
        total_value = sum(line.quantity * line.unit_cost for line in cost_lines)
        return total_value / total_qty

    def _reverse_issue_cost_lines(self, qty_line_uom):
        """Remove cost lines (newest first) and return vendor batch data for the return pool."""
        self.ensure_one()
        rounding = (self.uom_id or self.product_id.uom_id).rounding
        qty_left = qty_line_uom
        returned_batches = []
        for cost_line in self.issue_cost_line_ids.filtered(lambda c: float_compare(c.quantity, 0.0, precision_rounding=rounding) > 0).sorted('id', reverse=True):
            if float_is_zero(qty_left, precision_rounding=rounding):
                break
            if float_compare(cost_line.quantity, qty_left, precision_rounding=rounding) <= 0:
                take = cost_line.quantity
                qty_left -= take
            else:
                take = qty_left
                qty_left = 0.0
            if float_is_zero(take, precision_rounding=rounding):
                continue
            returned_batches.append({
                'vendor_id': cost_line.vendor_id.id,
                'vendor_name': cost_line.vendor_name or cost_line.vendor_id.display_name,
                'quantity': take,
                'unit_cost': cost_line.unit_cost,
                'svl_source_id': cost_line.svl_source_id.id if cost_line.svl_source_id else False,
            })
            new_qty = max(cost_line.quantity - take, 0.0)
            cost_line.quantity = new_qty
        return returned_batches

    def _auto_sync_stock_issue_return(self):
        """Automatically issue or return stock based on line quantity vs qty_issued."""
        if self.env.context.get('skip_auto_stock_sync'):
            return
        for line in self:
            if not line.product_id or not line.product_id.is_storable or not line.repair_id:
                continue
            line_uom = line.uom_id or line.product_id.uom_id
            rounding = line_uom.rounding
            diff = line.quantity - line.qty_issued
            if float_compare(diff, 0.0, precision_rounding=rounding) > 0:
                line._action_issue_part(qty_to_issue_override=diff)
            elif float_compare(diff, 0.0, precision_rounding=rounding) < 0:
                line._action_return_part(qty_to_return_override=abs(diff), reduce_quantity=False)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get('skip_auto_stock_sync'):
            lines._auto_sync_stock_issue_return()
        return lines

    def write(self, vals):
        if self.env.context.get('skip_auto_stock_sync'):
            return super().write(vals)

        # Return old product's issued stock if product_id changes
        if 'product_id' in vals:
            for line in self:
                new_prod_id = vals['product_id']
                if (
                    line.product_id
                    and line.product_id.id != new_prod_id
                    and line.product_id.is_storable
                    and float_compare(line.qty_issued, 0.0, precision_rounding=(line.uom_id or line.product_id.uom_id).rounding) > 0
                ):
                    line._action_return_part(qty_to_return_override=line.qty_issued, reduce_quantity=False)

        res = super().write(vals)

        if any(f in vals for f in ('quantity', 'product_id', 'uom_id', 'repair_id')):
            self.filtered(lambda l: not l.env.context.get('skip_auto_stock_sync'))._auto_sync_stock_issue_return()

        # Clean up any zero-quantity cost/stock sub-records on save
        zero_cost_lines = self.issue_cost_line_ids.filtered(lambda c: float_is_zero(c.quantity, precision_rounding=0.001))
        if zero_cost_lines:
            zero_cost_lines.unlink()
        zero_vendor_stocks = self.returned_vendor_stock_ids.filtered(lambda s: float_is_zero(s.quantity, precision_rounding=0.001))
        if zero_vendor_stocks:
            zero_vendor_stocks.unlink()

        return res

    def _validate_stock_picking(self, picking):
        return picking.fleet_validate_picking()

    def action_issue_part(self):
        for line in self:
            line._action_issue_part()
        return True

    def _action_issue_part(self, qty_to_issue_override=None):
        self.ensure_one()
        if not self.product_id:
            raise UserError(_('Select a product before issuing.'))
        if not self.product_id.is_storable:
            raise UserError(_('Only storable products can be issued from stock.'))

        product = self.product_id
        line_uom = self.uom_id or product.uom_id
        rounding = product.uom_id.rounding

        if qty_to_issue_override is not None:
            qty_line_uom = qty_to_issue_override
            qty_product_uom = line_uom._compute_quantity(qty_line_uom, product.uom_id)
        else:
            qty_product_uom = self._prepare_issue_qty_product_uom()
            qty_line_uom = max(self.quantity - self.qty_issued, 0.0)

        if float_is_zero(qty_product_uom, precision_rounding=rounding):
            if qty_to_issue_override is not None:
                return True
            raise UserError(_('Nothing left to issue on this line.'))

        warehouse = self._get_warehouse()
        src = self._get_stock_location()
        dest = self._get_production_location()
        picking_type = (
            warehouse.int_type_id
            or self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('warehouse_id', '=', warehouse.id),
            ], limit=1)
            or self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('company_id', '=', warehouse.company_id.id),
            ], limit=1)
            or self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
            ], limit=1)
        )
        if not picking_type:
            picking_type = self.env['stock.picking.type'].create({
                'name': _('Internal Transfers'),
                'code': 'internal',
                'warehouse_id': warehouse.id if warehouse else False,
                'company_id': warehouse.company_id.id if warehouse else self.env.company.id,
                'sequence_code': 'INT',
            })

        repair = self.repair_id
        fifo_candidates = self._get_fifo_candidate_layers()
        fifo_snapshot = self._snapshot_fifo_layers(fifo_candidates)
        fifo_plan = self._get_fifo_issue_plan(qty_product_uom, fifo_snapshot=fifo_snapshot)
        fifo_plan_for_consume = [dict(item) for item in fifo_plan]

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': src.id,
            'location_dest_id': dest.id,
            'origin': _('Job Card %s - Issue') % (repair.sequence or repair.display_name),
            'company_id': repair.company_id.id,
            'fleet_repair_id': repair.id,
            'fleet_repair_product_line_id': self.id,
            'move_ids': [(0, 0, {
                'name': product.display_name,
                'product_id': product.id,
                'product_uom_qty': qty_product_uom,
                'product_uom': product.uom_id.id,
                'location_id': src.id,
                'location_dest_id': dest.id,
                'company_id': repair.company_id.id,
            })],
        })
        validate_result = self._validate_stock_picking(picking)
        if validate_result is not True:
            return validate_result

        issued_line_uom = product.uom_id._compute_quantity(qty_product_uom, line_uom)
        stock_move = picking.move_ids.filtered(lambda m: m.product_id == product)[:1]
        created_cost_lines = self._create_issue_cost_lines_from_plan(
            picking, stock_move, fifo_plan,
        )
        self._consume_returned_vendor_stock(fifo_plan_for_consume)
        if not created_cost_lines:
            created_cost_lines = self._create_issue_cost_lines_from_fifo_diff(
                picking, stock_move, fifo_snapshot,
            )
        if not created_cost_lines:
            created_cost_lines = self._create_issue_cost_lines_fallback(
                picking, stock_move, qty_product_uom,
            )
        new_cost_price = self._recompute_cost_price_from_cost_lines()
        self.with_context(skip_auto_stock_sync=True).write({
            'qty_issued': self.qty_issued + issued_line_uom,
            'cost_price': new_cost_price,
            'issue_picking_ids': [(4, picking.id)],
        })
        self._refresh_stock_qty_cache()

    def action_return_part(self):
        for line in self:
            line._action_return_part()
        return True

    def _action_return_part(self, qty_to_return_override=None, reduce_quantity=False):
        self.ensure_one()
        if not self.product_id or not self.product_id.is_storable:
            raise UserError(_('Only storable products can be returned to stock.'))

        product = self.product_id
        line_uom = self.uom_id or product.uom_id
        rounding = line_uom.rounding
        if float_is_zero(self.qty_issued, precision_rounding=rounding):
            if qty_to_return_override is not None:
                return True
            raise UserError(_('No issued quantity to return on this line.'))

        qty_line_uom = qty_to_return_override if qty_to_return_override is not None else self.qty_to_return
        if float_is_zero(qty_line_uom, precision_rounding=rounding):
            if qty_to_return_override is not None:
                return True
            raise UserError(_(
                'Enter a return quantity for "%(product)s" (max %(max)s %(uom)s).',
                product=product.display_name,
                max=self.qty_issued,
                uom=line_uom.name,
            ))
        if float_compare(qty_line_uom, self.qty_issued, precision_rounding=rounding) > 0:
            raise UserError(_(
                'Return quantity (%(ret)s %(uom)s) cannot exceed issued quantity (%(issued)s %(uom)s).',
                ret=qty_line_uom,
                issued=self.qty_issued,
                uom=line_uom.name,
            ))

        qty_product_uom = line_uom._compute_quantity(qty_line_uom, product.uom_id)

        warehouse = self._get_warehouse()
        src = self._get_production_location()
        dest = self._get_stock_location()
        picking_type = (
            warehouse.int_type_id
            or self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('warehouse_id', '=', warehouse.id),
            ], limit=1)
            or self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('company_id', '=', warehouse.company_id.id),
            ], limit=1)
            or self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
            ], limit=1)
        )
        if not picking_type:
            picking_type = self.env['stock.picking.type'].create({
                'name': _('Internal Transfers'),
                'code': 'internal',
                'warehouse_id': warehouse.id if warehouse else False,
                'company_id': warehouse.company_id.id if warehouse else self.env.company.id,
                'sequence_code': 'INT',
            })
        repair = self.repair_id

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': src.id,
            'location_dest_id': dest.id,
            'origin': _('Job Card %s - Return') % (repair.sequence or repair.display_name),
            'company_id': repair.company_id.id,
            'fleet_repair_id': repair.id,
            'fleet_repair_product_line_id': self.id,
            'move_ids': [(0, 0, {
                'name': product.display_name,
                'product_id': product.id,
                'product_uom_qty': qty_product_uom,
                'product_uom': product.uom_id.id,
                'location_id': src.id,
                'location_dest_id': dest.id,
                'company_id': repair.company_id.id,
            })],
        })
        validate_result = self._validate_stock_picking(picking)
        if validate_result is not True:
            return validate_result

        returned_batches = self._reverse_issue_cost_lines(qty_line_uom)
        self._restore_returned_vendor_stock(returned_batches, picking)
        new_qty_issued = max(self.qty_issued - qty_line_uom, 0.0)

        write_vals = {
            'qty_issued': new_qty_issued,
            'qty_to_return': 0.0,
            'issue_picking_ids': [(4, picking.id)],
            'cost_price': self._recompute_cost_price_from_cost_lines(),
        }
        if reduce_quantity:
            new_quantity = max(self.quantity - qty_line_uom, 0.0)
            write_vals['quantity'] = new_quantity

        if float_is_zero(new_qty_issued, precision_rounding=rounding):
            write_vals['cost_price'] = 0.0

        self.with_context(skip_auto_stock_sync=True).write(write_vals)
        self._refresh_stock_qty_cache()

    @api.constrains('qty_to_return', 'qty_issued', 'product_id', 'uom_id')
    def _check_qty_to_return(self):
        for line in self:
            if not line.product_id:
                continue
            rounding = (line.uom_id or line.product_id.uom_id).rounding
            if float_compare(line.qty_to_return, 0.0, precision_rounding=rounding) < 0:
                raise ValidationError(_('Return quantity cannot be negative.'))
            if float_compare(line.qty_to_return, line.qty_issued, precision_rounding=rounding) > 0:
                raise ValidationError(_(
                    'Return quantity cannot exceed issued quantity (%(issued)s).',
                    issued=line.qty_issued,
                ))

    def unlink(self):
        for line in self:
            if not line.env.context.get('skip_auto_stock_sync'):
                if (
                    line.product_id
                    and line.product_id.is_storable
                    and float_compare(line.qty_issued, 0.0, precision_rounding=(line.uom_id or line.product_id.uom_id).rounding) > 0
                ):
                    line._action_return_part(qty_to_return_override=line.qty_issued, reduce_quantity=False)
        return super().unlink()




