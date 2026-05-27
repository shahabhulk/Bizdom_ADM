# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class FleetRepairReturnedVendorStock(models.Model):
    """Vendor-tagged qty returned to shelf from a job line (used before global FIFO on re-issue)."""

    _name = 'fleet.repair.returned.vendor.stock'
    _description = 'Returned Vendor Stock Pool'
    _order = 'id ASC'

    repair_line_id = fields.Many2one(
        'fleet.repair.product.line',
        string='Job Line',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        related='repair_line_id.product_id',
        store=True,
        readonly=True,
    )
    vendor_id = fields.Many2one('res.partner', string='Vendor', required=True, index=True)
    vendor_name = fields.Char(string='Vendor Name', required=True)
    quantity = fields.Float(
        string='Qty Available',
        digits='Product Unit of Measure',
        required=True,
    )
    unit_cost = fields.Float(string='Unit Cost', digits='Product Price', required=True)
    uom_id = fields.Many2one(related='repair_line_id.uom_id', readonly=True)
    return_picking_id = fields.Many2one('stock.picking', string='Return Transfer', readonly=True)
    svl_source_id = fields.Many2one(
        'stock.valuation.layer',
        string='Original FIFO Layer',
        readonly=True,
        ondelete='set null',
    )
