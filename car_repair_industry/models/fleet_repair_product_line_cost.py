# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class FleetRepairProductLineCost(models.Model):
    _name = 'fleet.repair.product.line.cost'
    _description = 'FIFO Issue Cost Line'
    _order = 'issue_date desc, id desc'

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
    currency_id = fields.Many2one(
        related='repair_line_id.currency_id',
        store=True,
        readonly=True,
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Transfer',
        readonly=True,
        ondelete='set null',
    )
    stock_move_id = fields.Many2one(
        'stock.move',
        string='Stock Move',
        readonly=True,
        ondelete='set null',
    )
    svl_source_id = fields.Many2one(
        'stock.valuation.layer',
        string='FIFO Layer',
        readonly=True,
        ondelete='set null',
        help='Incoming valuation layer consumed by FIFO on this issue.',
    )
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        readonly=True,
    )
    vendor_name = fields.Char(
        string='Vendor Name',
        readonly=True,
    )
    quantity = fields.Float(
        string='Qty',
        digits='Product Unit of Measure',
        readonly=True,
    )
    uom_id = fields.Many2one(
        related='repair_line_id.uom_id',
        readonly=True,
    )
    unit_cost = fields.Float(
        string='Unit Cost',
        digits='Product Price',
        readonly=True,
    )
    cost_subtotal = fields.Monetary(
        string='Cost',
        compute='_compute_cost_subtotal',
        store=True,
        currency_field='currency_id',
    )
    issue_date = fields.Datetime(
        string='Issued On',
        readonly=True,
    )

    @api.depends('quantity', 'unit_cost')
    def _compute_cost_subtotal(self):
        for line in self:
            line.cost_subtotal = line.quantity * line.unit_cost
