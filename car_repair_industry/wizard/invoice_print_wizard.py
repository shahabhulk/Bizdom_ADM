# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class InvoicePrintWizard(models.TransientModel):
    _name = 'invoice.print.wizard'
    _description = 'Print Invoice Wizard'

    invoice_id = fields.Many2one('account.move', string='Invoice', default=lambda self: self.env.context.get('active_id'))
    print_type = fields.Selection([
        ('b2c', 'B2C Invoice'),
        ('b2b', 'B2B Invoice')
    ], string='Invoice Type', default='b2c', required=True)

    def action_print(self):
        self.ensure_one()
        if self.print_type == 'b2c':
            return self.action_print_b2c()
        else:
            return self.action_print_b2b()

    def action_print_b2c(self):
        self.ensure_one()
        invoice = self.invoice_id or self.env['account.move'].browse(self._context.get('active_id'))
        return self.env.ref('car_repair_industry.action_report_invoice_b2c').report_action(invoice)

    def action_print_b2b(self):
        self.ensure_one()
        invoice = self.invoice_id or self.env['account.move'].browse(self._context.get('active_id'))
        return self.env.ref('car_repair_industry.action_report_invoice_b2b').report_action(invoice)
