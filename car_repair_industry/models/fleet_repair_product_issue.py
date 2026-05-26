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

    @api.onchange('qty_issued')
    def _onchange_qty_issued_cap_return(self):
        for line in self:
            if not line.product_id:
                continue
            rounding = (line.uom_id or line.product_id.uom_id).rounding
            if float_compare(line.qty_to_return, line.qty_issued, precision_rounding=rounding) > 0:
                line.qty_to_return = line.qty_issued

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
        """Shelf availability for display (adm/Stock), in line UoM."""
        if not product or not product.is_storable:
            return float('inf')
        line_uom = self.uom_id or product.uom_id
        location = warehouse.lot_stock_id
        qty = self.env['stock.quant']._get_available_quantity(
            product.sudo(), location, strict=True,
        )
        return self._convert_qty(qty, product.uom_id, line_uom)

    def _get_product_available_qty(self, product, warehouse):
        """Available on stock location in product default UoM."""
        if not product or not product.is_storable:
            return float('inf')
        qty = self.env['stock.quant']._get_available_quantity(
            product.sudo(), warehouse.lot_stock_id, strict=True,
        )
        return qty

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

    def _validate_stock_picking(self, picking):
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            if float_is_zero(move.product_uom_qty, precision_rounding=move.product_uom.rounding):
                continue
            move.quantity = move.product_uom_qty
            move.picked = True
        validate_result = picking.button_validate()
        if validate_result is not True and isinstance(validate_result, dict):
            return validate_result
        return True

    def action_issue_part(self):
        for line in self:
            line._action_issue_part()
        return True

    def _action_issue_part(self):
        self.ensure_one()
        if not self.product_id:
            raise UserError(_('Select a product before issuing.'))
        if not self.product_id.is_storable:
            raise UserError(_('Only storable products can be issued from stock.'))

        product = self.product_id
        rounding = product.uom_id.rounding
        qty_product_uom = self._prepare_issue_qty_product_uom()
        if float_is_zero(qty_product_uom, precision_rounding=rounding):
            raise UserError(_('Nothing left to issue on this line.'))

        available_product_uom = self._get_product_available_qty(
            product, self._get_warehouse(),
        )
        if float_compare(qty_product_uom, available_product_uom, precision_rounding=rounding) > 0:
            raise UserError(_(
                'Not enough stock for "%(product)s". '
                'To issue: %(req)s %(uom)s, Available on shelf: %(avail)s %(uom)s.',
                product=product.display_name,
                req=qty_product_uom,
                avail=available_product_uom,
                uom=product.uom_id.name,
            ))

        warehouse = self._get_warehouse()
        src = self._get_stock_location()
        dest = self._get_production_location()
        picking_type = warehouse.int_type_id
        if not picking_type:
            raise UserError(_('No internal operation type on warehouse %s.') % warehouse.name)

        repair = self.repair_id
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

        line_uom = self.uom_id or product.uom_id
        issued_line_uom = product.uom_id._compute_quantity(qty_product_uom, line_uom)
        self.write({
            'qty_issued': self.qty_issued + issued_line_uom,
            'issue_picking_ids': [(4, picking.id)],
        })

    def action_return_part(self):
        for line in self:
            line._action_return_part()
        return True

    def _action_return_part(self):
        self.ensure_one()
        if not self.product_id or not self.product_id.is_storable:
            raise UserError(_('Only storable products can be returned to stock.'))

        product = self.product_id
        line_uom = self.uom_id or product.uom_id
        rounding = line_uom.rounding
        if float_is_zero(self.qty_issued, precision_rounding=rounding):
            raise UserError(_('No issued quantity to return on this line.'))

        qty_line_uom = self.qty_to_return
        if float_is_zero(qty_line_uom, precision_rounding=rounding):
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
        if float_compare(qty_line_uom, self.quantity, precision_rounding=rounding) > 0:
            raise UserError(_(
                'Return quantity (%(ret)s %(uom)s) cannot exceed line quantity (%(qty)s %(uom)s).',
                ret=qty_line_uom,
                qty=self.quantity,
                uom=line_uom.name,
            ))

        qty_product_uom = line_uom._compute_quantity(qty_line_uom, product.uom_id)

        warehouse = self._get_warehouse()
        src = self._get_production_location()
        dest = self._get_stock_location()
        picking_type = warehouse.int_type_id
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

        new_quantity = self.quantity - qty_line_uom
        if float_compare(new_quantity, 0.0, precision_rounding=rounding) < 0:
            new_quantity = 0.0

        self.write({
            'quantity': new_quantity,
            'qty_issued': self.qty_issued - qty_line_uom,
            'qty_to_return': 0.0,
            'issue_picking_ids': [(4, picking.id)],
        })

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

    @api.constrains('quantity', 'qty_issued')
    def _check_quantity_not_below_issued(self):
        for line in self:
            if not line.product_id:
                continue
            rounding = (line.uom_id or line.product_id.uom_id).rounding
            if float_compare(line.quantity, line.qty_issued, precision_rounding=rounding) < 0:
                raise ValidationError(_(
                    'Quantity cannot be less than issued quantity (%(issued)s) for "%(product)s". '
                    'Return the part first.',
                    issued=line.qty_issued,
                    product=line.product_id.display_name,
                ))

    def unlink(self):
        for line in self:
            rounding = (line.uom_id or line.product_id.uom_id).rounding if line.product_id else 0.01
            if float_compare(line.qty_issued, 0.0, precision_rounding=rounding) > 0:
                raise UserError(_(
                    'Cannot delete line for "%(product)s": return issued stock first.',
                    product=line.product_id.display_name,
                ))
        return super().unlink()

    @api.constrains('quantity', 'product_id', 'uom_id', 'qty_issued')
    def _check_stock_quantity(self):
        checked = set()
        for line in self:
            if not line.product_id or not line.product_id.is_storable:
                continue
            key = (line.repair_id.id, line.product_id.id)
            if key in checked:
                continue
            checked.add(key)
            warehouse = line._get_warehouse()
            if not warehouse:
                raise ValidationError(
                    _('No warehouse configured for company %s.')
                    % (line.repair_id.company_id.name or line.env.company.name)
                )
            product = line.product_id
            available = line._get_product_available_qty(product, warehouse)
            requested = line._get_repair_pending_issue_qty(product)
            if float_compare(requested, available, precision_rounding=product.uom_id.rounding) > 0:
                raise ValidationError(_(
                    'Not enough stock for "%(product)s". '
                    'Pending issue: %(req)s %(uom)s, Available on shelf: %(avail)s %(uom)s (%(wh)s).',
                    product=product.display_name,
                    req=requested,
                    avail=available,
                    uom=product.uom_id.name,
                    wh=warehouse.name,
                ))

    @api.onchange('quantity', 'product_id', 'uom_id')
    def _onchange_quantity_stock(self):
        for line in self:
            if not line.product_id or not line.product_id.is_storable:
                continue
            warehouse = line._get_warehouse()
            if not warehouse:
                continue
            available = line._get_available_qty(line.product_id, warehouse)
            pending = line.quantity - line.qty_issued
            if float_compare(pending, available, precision_rounding=(line.uom_id or line.product_id.uom_id).rounding or 0.01) > 0:
                uom_name = (line.uom_id or line.product_id.uom_id).name
                return {
                    'warning': {
                        'title': _('Insufficient Stock'),
                        'message': _(
                            'Product "%(product)s": pending issue %(req)s %(uom)s, '
                            'available on shelf %(avail)s %(uom)s (%(wh)s).',
                            product=line.product_id.display_name,
                            req=pending,
                            avail=available,
                            uom=uom_name,
                            wh=warehouse.name,
                        ),
                    }
                }

