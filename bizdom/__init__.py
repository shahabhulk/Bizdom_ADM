from . import models
from . import controllers
from odoo import api, SUPERUSER_ID





def post_init_rebuild_labour(env):
    invoices = env["account.move"].search([("state", "=", "posted")])
    for inv in invoices:
        for line in inv.invoice_line_ids:
            if hasattr(line, "_sync_labour_billing"):
                line._sync_labour_billing()


def post_init_sync_feedback_data(env):
    """Sync existing fleet.feedback.line records with feedback.data model"""
    service_feedbacks=env["fleet.repair.feedback"].search([])
    # feedback_lines = env["fleet.feedback.line"].search([("feedback_id", "!=", False), ("question_id", "!=", False)])
    for service in service_feedbacks:
        for line in service.question_line_ids:
            if hasattr(line, '_sync_service_feedback'):
                line._sync_service_feedback()


        # if hasattr(line, '_sync_service_feedback'):
        #     line._sync_service_feedback()
