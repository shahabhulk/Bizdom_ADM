from . import models
from . import controllers
from odoo import api, SUPERUSER_ID


def post_init_rebuild_labour(env):
    invoices = env["account.move"].search([("state", "=", "posted")])
    for inv in invoices:
        for line in inv.invoice_line_ids:
            if hasattr(line, "_sync_labour_billing"):
                line._sync_labour_billing()