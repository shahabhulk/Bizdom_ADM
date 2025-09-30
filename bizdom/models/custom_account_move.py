from odoo import api, fields, models

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # employee_id = fields.Many2one("hr.employee", string="Employee")  # define here if not already

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
                existing = self.env['labour.billing'].search(
                    [('invoice_line_id', '=', line.id)], limit=1
                )
                vals = {
                    'employee_id': line.employee_id.id,
                    'charge_amount': line.price_subtotal,
                    'date': line.move_id.invoice_date or fields.Date.today(),
                }
                if existing:
                    existing.write(vals)
                else:
                    vals['invoice_line_id'] = line.id
                    self.env['labour.billing'].create(vals)
