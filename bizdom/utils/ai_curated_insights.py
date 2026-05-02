# -*- coding: utf-8 -*-
"""Curated Odoo analytics snippets for Bizdom AI Insights.

Each function returns a small, bounded structure suitable for LLM context — never raw
table dumps. They use the current env (respect record rules when not using sudo).
"""
import logging
import datetime as dt

from odoo import fields

_logger = logging.getLogger(__name__)

# Row cap per ranked list (keep token use predictable)
DEFAULT_ROW_LIMIT = 8


def curated_tool_catalog():
    """Registry of available curated insights (for docs / future tool-routing)."""
    return [
        {
            'id': 'top_vehicles_by_labour',
            'summary': 'Paid customer-invoice labour charges (labour.billing) grouped by vehicle plate.',
        },
        {
            'id': 'top_vehicles_by_parts_spend',
            'summary': 'Product lines on paid customer invoices with no employee (treated as parts/materials), by vehicle plate.',
        },
        {
            'id': 'top_vehicles_by_workshop_charges',
            'summary': 'All department.charges on paid invoices (labour + other allocated lines) by vehicle plate.',
        },
        {
            'id': 'crm_leads_in_period',
            'summary': 'CRM leads count in the date range (company-scoped, uses lead_date when present).',
        },
        {
            'id': 'vendor_bills_paid_summary',
            'summary': 'Posted paid vendor bills (in_invoice) in range — count and amount_total sum.',
        },
        {
            'id': 'customer_invoices_paid_summary',
            'summary': 'Posted paid customer invoices (out_invoice) in range — count and amount_total sum.',
        },
    ]


def _safe_read_group(env, model_name, domain, aggregates, groupby, limit=DEFAULT_ROW_LIMIT, orderby=None):
    """Run read_group if model exists; return [] on failure."""
    if model_name not in env:
        return []
    try:
        kw = {'limit': limit}
        if orderby:
            kw['orderby'] = orderby
        return env[model_name].read_group(domain, aggregates, groupby, **kw)
    except Exception:
        _logger.exception('ai_curated_insights: read_group failed for %s', model_name)
        return []


def top_vehicles_by_labour(env, company, start_date, end_date, limit=DEFAULT_ROW_LIMIT):
    """Labour billing totals by license plate (paid invoices, date on labour line)."""
    domain = [
        ('date', '>=', start_date),
        ('date', '<=', end_date),
        ('invoice_id.payment_state', '=', 'paid'),
        ('invoice_id.company_id', '=', company.id),
        ('car_number', '!=', False),
    ]
    groups = _safe_read_group(
        env,
        'labour.billing',
        domain,
        ['charge_amount:sum'],
        ['car_number'],
        limit=None,
    )
    groups.sort(key=lambda g: float(g.get('charge_amount', 0) or 0), reverse=True)
    groups = groups[:limit]
    rows = []
    for g in groups:
        plate = (g.get('car_number') or '').strip() or 'Unknown'
        rows.append({
            'license_plate': plate,
            'labour_total': round(float(g.get('charge_amount', 0) or 0), 2),
            'car_name_line': None,
        })
    # Enrich car display name from one lookup per plate (bounded by limit)
    if rows and 'labour.billing' in env:
        for row in rows:
            if row['license_plate'] == 'Unknown':
                continue
            try:
                rec = env['labour.billing'].search([
                    ('car_number', '=', row['license_plate']),
                    ('invoice_id.company_id', '=', company.id),
                ], limit=1, order='date desc')
                if rec:
                    row['car_name_line'] = rec.car_name_line or None
            except Exception:
                pass
    return {
        'description': 'Labour charge_amount sums from labour.billing (paid invoices only), grouped by vehicle plate.',
        'rows': rows,
    }


def top_vehicles_by_parts_spend(env, company, start_date, end_date, limit=DEFAULT_ROW_LIMIT):
    """Non-labour product invoice lines (no employee on line) summed by vehicle plate."""
    if 'account.move.line' not in env:
        return {'description': 'account.move.line not available.', 'rows': []}

    domain = [
        ('move_id.move_type', '=', 'out_invoice'),
        ('move_id.state', '=', 'posted'),
        ('move_id.payment_state', '=', 'paid'),
        ('move_id.invoice_date', '>=', start_date),
        ('move_id.invoice_date', '<=', end_date),
        ('move_id.company_id', '=', company.id),
        ('display_type', '=', False),
        ('product_id', '!=', False),
        ('employee_id', '=', False),
        ('move_id.license_plate', '!=', False),
    ]
    groups = _safe_read_group(
        env,
        'account.move.line',
        domain,
        ['price_subtotal:sum'],
        ['move_id.license_plate'],
        limit=None,
    )
    groups.sort(key=lambda g: float(g.get('price_subtotal', 0) or 0), reverse=True)
    groups = groups[:limit]
    rows = []
    for g in groups:
        plate = (g.get('move_id.license_plate') or '').strip() or 'Unknown'
        rows.append({
            'license_plate': plate,
            'parts_total': round(float(g.get('price_subtotal', 0) or 0), 2),
            'car_name': None,
        })
    if rows:
        Move = env['account.move']
        for row in rows:
            if row['license_plate'] == 'Unknown':
                continue
            try:
                inv = Move.search([
                    ('license_plate', '=', row['license_plate']),
                    ('company_id', '=', company.id),
                    ('move_type', '=', 'out_invoice'),
                ], limit=1, order='invoice_date desc')
                if inv:
                    row['car_name'] = inv.car_name or None
            except Exception:
                pass
    return {
        'description': 'Sum of invoice line price_subtotal for product lines without employee (heuristic: parts/materials), by invoice license_plate.',
        'rows': rows,
    }


def top_vehicles_by_workshop_charges(env, company, start_date, end_date, limit=DEFAULT_ROW_LIMIT):
    """department.charges — mirrors workshop billing allocation per vehicle."""
    domain = [
        ('date', '>=', start_date),
        ('date', '<=', end_date),
        ('invoice_id.payment_state', '=', 'paid'),
        ('invoice_id.company_id', '=', company.id),
        ('car_number', '!=', False),
    ]
    groups = _safe_read_group(
        env,
        'department.charges',
        domain,
        ['charge_amount:sum'],
        ['car_number'],
        limit=None,
    )
    groups.sort(key=lambda g: float(g.get('charge_amount', 0) or 0), reverse=True)
    groups = groups[:limit]
    rows = []
    for g in groups:
        plate = (g.get('car_number') or '').strip() or 'Unknown'
        rows.append({
            'license_plate': plate,
            'workshop_line_total': round(float(g.get('charge_amount', 0) or 0), 2),
        })
    return {
        'description': 'department.charges sums (allocated invoice lines) by vehicle plate — includes labour and other department lines.',
        'rows': rows,
    }


def crm_leads_in_period(env, company, start_date, end_date):
    """Lead counts for the period (same date field as Bizdom KPIs when available)."""
    if 'crm.lead' not in env:
        return {'description': 'CRM not installed.', 'total': 0, 'by_stage': []}

    Lead = env['crm.lead']
    if 'lead_date' in Lead._fields:
        date_domain = [
            ('lead_date', '>=', start_date),
            ('lead_date', '<=', end_date),
        ]
    else:
        start_d = start_date if isinstance(start_date, dt.date) else start_date
        end_d = end_date if isinstance(end_date, dt.date) else end_date
        start_cmp = fields.Datetime.to_string(
            dt.datetime.combine(start_d, dt.time.min)
        )
        end_cmp = fields.Datetime.to_string(
            dt.datetime.combine(end_d, dt.time.max)
        )
        date_domain = [
            ('create_date', '>=', start_cmp),
            ('create_date', '<=', end_cmp),
        ]

    base_domain = [('company_id', 'in', [False, company.id])] + date_domain
    try:
        total = Lead.search_count(base_domain)
    except Exception:
        _logger.exception('ai_curated_insights: crm lead count')
        total = 0

    by_stage = []
    try:
        stage_groups = Lead.read_group(
            base_domain,
            ['__count'],
            ['stage_id'],
            limit=15,
        )
        for g in stage_groups:
            stage = g.get('stage_id')
            name = stage[1] if isinstance(stage, (list, tuple)) and len(stage) > 1 else (stage or 'Unknown')
            by_stage.append({
                'stage': name,
                'count': int(g.get('__count', 0) or 0),
            })
    except Exception:
        _logger.exception('ai_curated_insights: crm read_group')

    return {
        'description': 'CRM leads with lead_date in range (or create_date fallback if lead_date missing).',
        'total': total,
        'by_stage': by_stage[:12],
    }


def vendor_bills_paid_summary(env, company, start_date, end_date):
    """Paid vendor bills in period."""
    if 'account.move' not in env:
        return {}
    domain = [
        ('move_type', '=', 'in_invoice'),
        ('state', '=', 'posted'),
        ('payment_state', '=', 'paid'),
        ('invoice_date', '>=', start_date),
        ('invoice_date', '<=', end_date),
        ('company_id', '=', company.id),
    ]
    try:
        Move = env['account.move']
        moves = Move.search(domain)
        return {
            'description': 'Posted vendor bills (in_invoice) marked paid, invoice_date in range.',
            'bill_count': len(moves),
            'amount_total_sum': round(float(sum(moves.mapped('amount_total'))), 2),
        }
    except Exception:
        _logger.exception('ai_curated_insights: vendor bills summary')
        return {'error': 'Could not compute vendor bill summary.'}


def customer_invoices_paid_summary(env, company, start_date, end_date):
    """Paid customer invoices in period."""
    if 'account.move' not in env:
        return {}
    domain = [
        ('move_type', '=', 'out_invoice'),
        ('state', '=', 'posted'),
        ('payment_state', '=', 'paid'),
        ('invoice_date', '>=', start_date),
        ('invoice_date', '<=', end_date),
        ('company_id', '=', company.id),
    ]
    try:
        Move = env['account.move']
        moves = Move.search(domain)
        return {
            'description': 'Posted customer invoices (out_invoice) marked paid, invoice_date in range.',
            'invoice_count': len(moves),
            'amount_total_sum': round(float(sum(moves.mapped('amount_total'))), 2),
        }
    except Exception:
        _logger.exception('ai_curated_insights: customer invoices summary')
        return {'error': 'Could not compute customer invoice summary.'}


def build_curated_insights_bundle(env, company, start_date, end_date, limit=DEFAULT_ROW_LIMIT):
    """Assemble all curated blocks for the AI system prompt."""
    bundle = {
        'tool_catalog': curated_tool_catalog(),
        'period': {
            'start': start_date.strftime('%d-%m-%Y') if hasattr(start_date, 'strftime') else str(start_date),
            'end': end_date.strftime('%d-%m-%Y') if hasattr(end_date, 'strftime') else str(end_date),
        },
        'top_vehicles_by_labour': {},
        'top_vehicles_by_parts_spend': {},
        'top_vehicles_by_workshop_charges': {},
        'crm_leads_in_period': {},
        'vendor_bills_paid_summary': {},
        'customer_invoices_paid_summary': {},
    }
    try:
        bundle['top_vehicles_by_labour'] = top_vehicles_by_labour(
            env, company, start_date, end_date, limit=limit
        )
    except Exception:
        _logger.exception('ai_curated_insights: top_vehicles_by_labour')
        bundle['top_vehicles_by_labour'] = {'error': 'unavailable'}

    try:
        bundle['top_vehicles_by_parts_spend'] = top_vehicles_by_parts_spend(
            env, company, start_date, end_date, limit=limit
        )
    except Exception:
        _logger.exception('ai_curated_insights: top_vehicles_by_parts_spend')
        bundle['top_vehicles_by_parts_spend'] = {'error': 'unavailable'}

    try:
        bundle['top_vehicles_by_workshop_charges'] = top_vehicles_by_workshop_charges(
            env, company, start_date, end_date, limit=limit
        )
    except Exception:
        _logger.exception('ai_curated_insights: top_vehicles_by_workshop_charges')
        bundle['top_vehicles_by_workshop_charges'] = {'error': 'unavailable'}

    try:
        bundle['crm_leads_in_period'] = crm_leads_in_period(env, company, start_date, end_date)
    except Exception:
        _logger.exception('ai_curated_insights: crm_leads_in_period')
        bundle['crm_leads_in_period'] = {'error': 'unavailable'}

    try:
        bundle['vendor_bills_paid_summary'] = vendor_bills_paid_summary(env, company, start_date, end_date)
    except Exception:
        bundle['vendor_bills_paid_summary'] = {'error': 'unavailable'}

    try:
        bundle['customer_invoices_paid_summary'] = customer_invoices_paid_summary(env, company, start_date, end_date)
    except Exception:
        bundle['customer_invoices_paid_summary'] = {'error': 'unavailable'}

    return bundle
