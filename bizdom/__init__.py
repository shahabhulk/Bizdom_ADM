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


def post_init_add_performance_indexes(env):
    """
    Add database indexes for performance optimization.
    These indexes dramatically improve query performance for date-range queries
    used in score calculations and dashboard APIs.
    """
    cr = env.cr
    
    def create_index_if_not_exists(index_name, create_sql):
        """Helper function to create index only if it doesn't exist"""
        try:
            # Check if index already exists
            cr.execute("""
                SELECT 1 FROM pg_indexes 
                WHERE indexname = %s
            """, (index_name,))
            if cr.fetchone():
                env.logger.info(f"Index {index_name} already exists, skipping")
                return
            
            # Create the index
            cr.execute(create_sql)
            env.logger.info(f"Created index: {index_name}")
        except Exception as e:
            # If index creation fails, log warning but continue
            env.logger.warning(f"Could not create {index_name}: {e}")
    
    # 1. Indexes for labour.billing - Used in Labour and AOV scores
    create_index_if_not_exists(
        'idx_labour_billing_date',
        "CREATE INDEX idx_labour_billing_date ON labour_billing(date)"
    )
    
    # 2. Indexes for fleet.repair - Used in TAT score
    create_index_if_not_exists(
        'idx_fleet_repair_receipt_date',
        "CREATE INDEX idx_fleet_repair_receipt_date ON fleet_repair(receipt_date)"
    )
    
    create_index_if_not_exists(
        'idx_fleet_repair_invoice_order_id',
        """CREATE INDEX idx_fleet_repair_invoice_order_id 
           ON fleet_repair(invoice_order_id) 
           WHERE invoice_order_id IS NOT NULL"""
    )
    
    # 3. Indexes for account.move - Used in TAT score (invoice_date)
    create_index_if_not_exists(
        'idx_account_move_invoice_date',
        """CREATE INDEX idx_account_move_invoice_date 
           ON account_move(invoice_date) 
           WHERE invoice_date IS NOT NULL"""
    )
    
    # 4. Indexes for crm.lead - Used in Leads and Conversion scores
    create_index_if_not_exists(
        'idx_crm_lead_date_company_stage',
        "CREATE INDEX idx_crm_lead_date_company_stage ON crm_lead(lead_date, company_id, stage_id)"
    )
    
    # 5. Indexes for account.move.line - Used in Income, Expense, Cashflow
    create_index_if_not_exists(
        'idx_account_move_line_date_company',
        "CREATE INDEX idx_account_move_line_date_company ON account_move_line(date, company_id)"
    )
    
    create_index_if_not_exists(
        'idx_account_move_line_account_id',
        "CREATE INDEX idx_account_move_line_account_id ON account_move_line(account_id)"
    )
    
    # 6. Indexes for fleet.repair.feedback - Used in AOV and Customer Retention
    create_index_if_not_exists(
        'idx_fleet_repair_feedback_date_customer',
        "CREATE INDEX idx_fleet_repair_feedback_date_customer ON fleet_repair_feedback(feedback_date, customer_id)"
    )
    
    # 7. Indexes for bizdom.score - Used in dashboard queries
    create_index_if_not_exists(
        'idx_bizdom_score_pillar_company_fav',
        "CREATE INDEX idx_bizdom_score_pillar_company_fav ON bizdom_score(pillar_id, company_id, favorite)"
    )
    
    env.logger.info("Performance indexes creation completed")