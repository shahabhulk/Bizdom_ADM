from odoo import api, fields, models

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # employee_id = fields.Many2one("hr.employee", string="Employee")  # define here if not already

    @api.model
    def create(self, vals):
        line = super().create(vals)
        line._sync_labour_billing()
        line._sync_department_charges()
        return line

    def write(self, vals):
        res = super().write(vals)
        self._sync_labour_billing()
        self._sync_department_charges()
        return res

    def _sync_labour_billing(self):
        for line in self:
            existing = self.env['labour.billing'].search(
                [('invoice_line_id', '=', line.id)], limit=1
            )

            # Only sync for customer invoices (out_invoice). If the line is moved
            # to another move type, remove any previously synced record.
            if line.move_id.move_type != 'out_invoice':
                if existing:
                    existing.unlink()
                continue

            if line.employee_id and line.price_subtotal > 0:
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
            elif existing:
                existing.unlink()

    def _sync_department_charges(self):
        for line in self:
            existing = self.env['department.charges'].search(
                [('invoice_line_id', '=', line.id)], limit=1
            )

            # Only sync for customer invoices (out_invoice). If the line is moved
            # to another move type, remove any previously synced record.
            if line.move_id.move_type != 'out_invoice':
                if existing:
                    existing.unlink()
                continue

            if line.price_subtotal <= 0:
                if existing:
                    existing.unlink()
                continue

            vals = {
                'charge_amount': line.price_subtotal,
                'date': line.move_id.invoice_date or fields.Date.today(),
            }
            if line.department_id:
                vals['department_id'] = line.department_id.id
                vals['employee_id'] = line.employee_id.id if line.employee_id else False
            if existing:
                existing.write(vals)
            else:
                vals['invoice_line_id'] = line.id
                self.env['department.charges'].create(vals)
