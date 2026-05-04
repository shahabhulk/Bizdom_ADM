import json
import logging
from datetime import date, datetime, timedelta

import requests

from odoo import http
from odoo.http import request

from .dashboard import BizdomDashboard
from ..utils.q1_helpers import Q1Helpers
from ..utils.q2_helpers import Q2Helpers
from ..utils.q3_helpers import Q3Helpers

_logger = logging.getLogger(__name__)


PROVIDER_DEFAULTS = {
    'groq': {
        'base_url': 'https://api.groq.com/openai/v1',
        'model': 'llama-3.3-70b-versatile',
    },
    'ollama': {
        'base_url': 'http://localhost:11434/v1',
        'model': 'llama3.1:8b',
    },
    'openai': {
        'base_url': 'https://api.openai.com/v1',
        'model': 'gpt-4o-mini',
    },
    'openrouter': {
        'base_url': 'https://openrouter.ai/api/v1',
        'model': 'meta-llama/llama-3.1-8b-instruct:free',
    },
}

# Hard caps to keep the LLM bill / latency sane no matter what the user typed in settings.
MAX_HISTORY_MESSAGES = 8
MAX_QUESTION_LENGTH = 1500
MAX_TOKENS_HARD_CAP = 2000
MAX_Q3_DEPARTMENTS = 8
MAX_Q3_CATEGORIES_PER_DEPARTMENT = 12


class BizdomAiInsights(http.Controller):

    # ------------------------------------------------------------------
    # Public routes
    # ------------------------------------------------------------------
    @http.route('/api/ai/status', type='json', auth='user', methods=['POST'], csrf=False)
    def ai_status(self):
        """Return whether AI Insights is enabled and properly configured.

        Used by the OWL chat widget to decide whether to render itself.
        """
        ICP = request.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param('bizdom.ai.enabled', 'False') == 'True'
        provider = ICP.get_param('bizdom.ai.provider') or 'groq'
        api_key = (ICP.get_param('bizdom.ai.api_key') or '').strip()
        # Ollama runs locally and does not require an API key.
        configured = enabled and (provider == 'ollama' or bool(api_key))
        return {
            'enabled': bool(enabled),
            'configured': bool(configured),
            'provider': provider,
        }

    @http.route('/api/ai/analyze', type='json', auth='user', methods=['POST'], csrf=False)
    def ai_analyze(self, question=None, scope='dashboard', filterType='MTD',
                   startDate=None, endDate=None, scoreId=None, history=None, **kw):
        """Analyze the user's question against the current dashboard / score data.

        Body (JSON RPC params):
            question     str  - what the user asked
            scope        str  - 'dashboard' or 'score'
            filterType   str  - Today | WTD | MTD | YTD | Custom
            startDate    str  - DD-MM-YYYY (only used when filterType is Custom)
            endDate      str  - DD-MM-YYYY (only used when filterType is Custom)
            scoreId      int  - required when scope == 'score'
            history      list - prior chat turns [{role, content}, ...]
        """
        question = (question or '').strip()
        if not question:
            return {'statusCode': 400, 'message': 'Please type a question.'}
        if len(question) > MAX_QUESTION_LENGTH:
            return {'statusCode': 400, 'message': 'Your question is too long. Please shorten it.'}

        ICP = request.env['ir.config_parameter'].sudo()
        if ICP.get_param('bizdom.ai.enabled', 'False') != 'True':
            return {
                'statusCode': 503,
                'message': 'AI Insights is disabled. Enable it in Settings → Bizdom AI.',
            }

        # Build the data snapshot the LLM will reason over.
        try:
            user = request.env.user
            company = user.company_id
            is_owner = user.has_group('bizdom.group_bizdom_owner')
            allowed_pillar_ids = user.bizdom_allowed_pillar_ids.ids

            start_date, end_date = self._resolve_date_range(filterType, startDate, endDate)

            if scope == 'score' and scoreId:
                snapshot = self._build_score_snapshot(
                    int(scoreId), start_date, end_date, filterType, startDate, endDate,
                    company, is_owner, allowed_pillar_ids,
                )
                if snapshot.get('error'):
                    return {'statusCode': 403, 'message': snapshot['error']}
            else:
                snapshot = self._build_dashboard_snapshot(
                    start_date, end_date, filterType,
                    company, is_owner, allowed_pillar_ids,
                )
        except Exception as e:
            _logger.exception("AI Insights: error building data snapshot")
            return {'statusCode': 500, 'message': 'Could not assemble dashboard data: %s' % str(e)[:200]}

        # Call the LLM.
        try:
            answer = self._call_llm(question, snapshot, history or [])
        except requests.exceptions.Timeout:
            return {'statusCode': 504, 'message': 'AI service timed out. Try a shorter question or try again.'}
        except requests.exceptions.ConnectionError:
            return {
                'statusCode': 502,
                'message': 'Could not reach the AI provider. Check the Base URL in Settings → Bizdom AI.',
            }
        except requests.exceptions.RequestException as e:
            _logger.exception("AI Insights: provider request failed")
            return {'statusCode': 502, 'message': 'AI provider error: %s' % str(e)[:200]}
        except ValueError as e:
            _logger.exception("AI Insights: provider returned malformed payload")
            return {'statusCode': 502, 'message': str(e)[:200]}
        except Exception as e:
            _logger.exception("AI Insights: unexpected error")
            return {'statusCode': 500, 'message': 'Unexpected error: %s' % str(e)[:200]}

        return {
            'statusCode': 200,
            'answer': answer,
            'context_summary': {
                'scope': snapshot.get('scope'),
                'filter': filterType,
                'start_date': start_date.strftime('%d-%m-%Y'),
                'end_date': end_date.strftime('%d-%m-%Y'),
                'pillar_count': len(snapshot.get('pillars', [])) if snapshot.get('scope') == 'dashboard' else None,
            },
        }

    # ------------------------------------------------------------------
    # Date range
    # ------------------------------------------------------------------
    def _resolve_date_range(self, filter_type, start_str, end_str):
        today = date.today()
        f = (filter_type or 'MTD').upper()
        if f == 'TODAY':
            return today, today
        if f == 'WTD':
            week_start = today - timedelta(days=today.weekday())
            return week_start, today
        if f == 'YTD':
            return date(today.year, 1, 1), today
        if f == 'CUSTOM':
            if start_str and end_str:
                try:
                    s = datetime.strptime(start_str, '%d-%m-%Y').date()
                    e = datetime.strptime(end_str, '%d-%m-%Y').date()
                    if s > e:
                        s, e = e, s
                    return s, e
                except ValueError:
                    pass
        # Default: month-to-date.
        return today.replace(day=1), today

    # ------------------------------------------------------------------
    # Dashboard snapshot (all pillars + scores for current period)
    # ------------------------------------------------------------------
    def _build_dashboard_snapshot(self, start_date, end_date, filter_type,
                                  company, is_owner, allowed_pillar_ids):
        helper = BizdomDashboard()
        domain = [('company_id', '=', company.id)]
        if not is_owner:
            domain.append(('id', 'in', allowed_pillar_ids))
        pillar_records = request.env['bizdom.pillar'].sudo().search(domain)

        normalized_filter = (filter_type or 'MTD')
        # _batch_compute_scores expects the same filter_type strings the dashboard route uses.
        scores_map = helper._batch_compute_scores(
            pillar_records,
            start_date,
            end_date,
            favorites_only=False,
            company_id=company.id,
            filter_type=normalized_filter,
            is_owner=is_owner,
            allowed_pillar_ids=allowed_pillar_ids,
        )

        pillars = []
        total_scores = 0
        green_count = 0
        yellow_count = 0
        red_count = 0
        unknown_count = 0
        for p in pillar_records:
            scores = scores_map.get(p.id, [])
            for s in scores:
                s['status'] = self._classify_score(
                    s.get('score_name'),
                    s.get('total_score_value'),
                    s.get('min_value'),
                    s.get('max_value'),
                )
                total_scores += 1
                if s['status'] == 'green':
                    green_count += 1
                elif s['status'] == 'yellow':
                    yellow_count += 1
                elif s['status'] == 'red':
                    red_count += 1
                else:
                    unknown_count += 1
            pillars.append({
                'pillar_id': p.id,
                'pillar_name': p.name,
                'pillar_identifier': p.pillar_identifier,
                'scores': scores,
            })

        return {
            'scope': 'dashboard',
            'filter': normalized_filter,
            'period': {
                'start': start_date.strftime('%d-%m-%Y'),
                'end': end_date.strftime('%d-%m-%Y'),
            },
            'company': company.name,
            'totals': {
                'pillars': len(pillars),
                'scores': total_scores,
                'green': green_count,
                'yellow': yellow_count,
                'red': red_count,
                'unknown': unknown_count,
            },
            'pillars': pillars,
            'score_status_legend': {
                'green': 'Meeting or exceeding target',
                'yellow': 'Between min and max thresholds (room to improve)',
                'red': 'Below minimum threshold (needs attention) — for TAT, above max is also red',
                'unknown': 'Min/max thresholds not configured for this score',
            },
        }

    # ------------------------------------------------------------------
    # Single-score snapshot (for the Score Dashboard)
    # ------------------------------------------------------------------
    def _build_score_snapshot(self, score_id, start_date, end_date, filter_type, start_date_str, end_date_str,
                              company, is_owner, allowed_pillar_ids):
        score = request.env['bizdom.score'].sudo().browse(score_id)
        if not score.exists():
            return {'scope': 'score', 'error': 'Score not found.'}
        if score.company_id and score.company_id.id != company.id:
            return {'scope': 'score', 'error': 'Score belongs to a different company.'}
        if not is_owner and score.pillar_id and score.pillar_id.id not in allowed_pillar_ids:
            return {'scope': 'score', 'error': 'You are not allowed to view this score.'}

        # Current period
        cur_value = self._compute_score_value(score, start_date, end_date)

        # Same-length previous period (immediately before)
        delta = end_date - start_date
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - delta
        prev_value = self._compute_score_value(score, prev_start, prev_end)

        if score.type == 'percentage':
            min_val = score.min_score_percentage
            max_val = score.max_score_percentage
        else:
            min_val = score.min_score_number
            max_val = score.max_score_number

        change = round(cur_value - prev_value, 2)
        change_pct = None
        if prev_value:
            try:
                change_pct = round(((cur_value - prev_value) / abs(prev_value)) * 100, 1)
            except ZeroDivisionError:
                change_pct = None

        score_data = {
            'score_id': score.id,
            'score_name': score.score_name,
            'score_identifier': score.score_identifier,
            'pillar_name': score.pillar_id.name if score.pillar_id else None,
            'type': score.type or 'value',
            'min_value': min_val,
            'max_value': max_val,
            'current_value': cur_value,
            'previous_period_value': prev_value,
            'change_vs_previous': change,
            'change_vs_previous_pct': change_pct,
            'status': self._classify_score(score.score_name, cur_value, min_val, max_val),
        }

        quadrants = self._build_score_quadrants(
            score=score,
            user=request.env.user,
            filter_type=filter_type,
            start_date=start_date,
            end_date=end_date,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
        )

        return {
            'scope': 'score',
            'filter': filter_type,
            'period': {
                'start': start_date.strftime('%d-%m-%Y'),
                'end': end_date.strftime('%d-%m-%Y'),
            },
            'previous_period': {
                'start': prev_start.strftime('%d-%m-%Y'),
                'end': prev_end.strftime('%d-%m-%Y'),
            },
            'company': company.name,
            'score': score_data,
            'quadrants': quadrants,
            'score_status_legend': {
                'green': 'Meeting or exceeding target',
                'yellow': 'Between min and max thresholds (room to improve)',
                'red': 'Below minimum threshold (needs attention) — for TAT, above max is also red',
                'unknown': 'Min/max thresholds not configured for this score',
            },
        }

    def _build_score_quadrants(self, score, user, filter_type, start_date, end_date, start_date_str=None, end_date_str=None):
        """Build compact Q1/Q2/Q3 context so AI can answer quadrant-specific questions."""
        filter_norm = (filter_type or 'MTD')
        start_str = start_date_str or start_date.strftime('%d-%m-%Y')
        end_str = end_date_str or end_date.strftime('%d-%m-%Y')

        # Q1: score overview across periods for the selected filter.
        try:
            q1_ranges = Q1Helpers.get_date_ranges(filter_norm, start_str, end_str)
        except Exception:
            q1_ranges = [(start_date, end_date, filter_norm)]

        q1 = []
        for q1_start, q1_end, period_label in q1_ranges:
            actual_value = self._compute_score_value(score, q1_start, q1_end)
            min_value, max_value = Q1Helpers.calculate_min_max(score, filter_norm, q1_start, q1_end)
            q1.append({
                'period': period_label,
                'start_date': q1_start.strftime('%d-%m-%Y'),
                'end_date': q1_end.strftime('%d-%m-%Y'),
                'actual_value': actual_value,
                'min_value': '' if min_value is None else min_value,
                'max_value': '' if max_value is None else max_value,
                'status': self._classify_score(score.score_name, actual_value, min_value, max_value),
            })

        # Q2: department breakdown for the current active period.
        category_lvl1_records = request.env['bizdom.category_lvl1'].sudo().search([
            ('score_id', '=', score.id),
            ('category_lvl1_selection', '!=', False),
        ])
        q2_departments = Q2Helpers.compute_department_scores(
            category_lvl1_records, start_date, end_date, score, user, filter_norm
        )
        q2_departments = sorted(
            q2_departments,
            key=lambda d: float(d.get('actual_value') or 0),
            reverse=True,
        )[:12]

        q2_total_actual = round(sum(float(d.get('actual_value') or 0) for d in q2_departments), 2)
        # Q3: employee/category/source breakdown per department (capped).
        q3_by_department = []
        if q2_departments:
            category_lvl2_records = request.env['bizdom.category_lvl2'].sudo().search([
                ('score_id', '=', score.id),
                ('category_lvl2_selection', '!=', False),
            ])
            # Keep payload bounded while still giving cross-department insight.
            for dept in q2_departments[:MAX_Q3_DEPARTMENTS]:
                dept_id = dept.get('department_id')
                dept_name = dept.get('department_name')
                if not dept_id:
                    continue
                dept_categories = Q3Helpers.compute_employee_scores(
                    category_lvl2_records,
                    start_date,
                    end_date,
                    score,
                    user,
                    int(dept_id),
                    filter_norm,
                )
                dept_categories = sorted(
                    dept_categories,
                    key=lambda e: float(e.get('actual_value') or 0),
                    reverse=True,
                )[:MAX_Q3_CATEGORIES_PER_DEPARTMENT]
                q3_by_department.append({
                    'department_id': dept_id,
                    'department_name': dept_name,
                    'category_count': len(dept_categories),
                    'categories': dept_categories,
                })

        return {
            'q1_overview': q1,
            'q2_department_overview': {
                'start_date': start_date.strftime('%d-%m-%Y'),
                'end_date': end_date.strftime('%d-%m-%Y'),
                'total_actual_value': q2_total_actual,
                'departments': q2_departments,
            },
            'q3_breakdown': {
                'departments': q3_by_department,
            },
        }

    def _compute_score_value(self, score_record, start_date, end_date):
        """Compute the score value for a given date range using the model's existing logic."""
        try:
            ctx_record = score_record.with_context(
                force_date_start=start_date,
                force_date_end=end_date,
            )
            ctx_record._compute_context_total_score()
            value = ctx_record.context_total_score or 0.0
            return round(value, 2)
        except Exception:
            _logger.exception("AI Insights: failed to compute score %s", score_record.id)
            return 0.0

    # ------------------------------------------------------------------
    # Status classification (shared by both snapshots)
    # ------------------------------------------------------------------
    def _classify_score(self, score_name, actual, min_val, max_val):
        try:
            actual = float(actual or 0)
        except (TypeError, ValueError):
            return 'unknown'
        try:
            min_val = float(min_val or 0)
        except (TypeError, ValueError):
            min_val = 0.0
        try:
            max_val = float(max_val or 0)
        except (TypeError, ValueError):
            max_val = 0.0

        if min_val <= 0 and max_val <= 0:
            return 'unknown'

        name = (score_name or '').strip().lower()
        # TAT: lower is better (inverted)
        if name == 'tat':
            if actual <= min_val:
                return 'green'
            if actual > max_val:
                return 'red'
            return 'yellow'
        # Standard: higher is better
        if actual < min_val:
            return 'red'
        if actual >= max_val:
            return 'green'
        return 'yellow'

    # ------------------------------------------------------------------
    # LLM call (provider-agnostic, OpenAI-compatible)
    # ------------------------------------------------------------------
    @staticmethod
    def _looks_like_webpage_url(url):
        """Catch the 'pasted the OpenAI welcome page URL' class of mistake."""
        if not url:
            return False
        lowered = url.strip().lower()
        bad_signals = ('?', '#', 'welcome', 'pricing', 'signup', 'login',
                       '.html', '.htm', '/dashboard', '/account', '/billing')
        return any(sig in lowered for sig in bad_signals)

    def _call_llm(self, question, snapshot, history):
        ICP = request.env['ir.config_parameter'].sudo()
        provider = ICP.get_param('bizdom.ai.provider') or 'groq'
        defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS['groq'])

        saved_base_url = (ICP.get_param('bizdom.ai.base_url') or '').strip().rstrip('/')
        # If the saved URL is obviously a webpage URL and we know the right default,
        # silently fall back. This rescues a misconfigured field without forcing
        # the user to fix settings before getting a useful response.
        if provider != 'custom' and self._looks_like_webpage_url(saved_base_url):
            _logger.warning(
                "AI Insights: saved Base URL %r looks like a webpage URL; "
                "falling back to provider default for %s.",
                saved_base_url, provider,
            )
            saved_base_url = ''
        base_url = (saved_base_url or defaults['base_url'] or '').strip().rstrip('/')
        if not base_url:
            raise ValueError('AI Base URL is not configured. Set it in Settings → Bizdom AI.')

        saved_model = (ICP.get_param('bizdom.ai.model') or '').strip()
        model = saved_model or (defaults['model'] or '').strip()
        if not model:
            raise ValueError('AI Model is not configured. Set it in Settings → Bizdom AI.')

        api_key = (ICP.get_param('bizdom.ai.api_key') or '').strip()
        if provider != 'ollama' and not api_key:
            raise ValueError('AI API Key is missing. Add it in Settings → Bizdom AI.')

        try:
            timeout = int(ICP.get_param('bizdom.ai.timeout') or '30')
        except (TypeError, ValueError):
            timeout = 30
        timeout = max(5, min(timeout, 120))

        try:
            temperature = float(ICP.get_param('bizdom.ai.temperature') or '0.4')
        except (TypeError, ValueError):
            temperature = 0.4
        temperature = max(0.0, min(temperature, 1.0))

        try:
            max_tokens = int(ICP.get_param('bizdom.ai.max_tokens') or '800')
        except (TypeError, ValueError):
            max_tokens = 800
        max_tokens = max(100, min(max_tokens, MAX_TOKENS_HARD_CAP))

        url = '%s/chat/completions' % base_url
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['Authorization'] = 'Bearer %s' % api_key

        system_prompt = self._build_system_prompt(snapshot)
        messages = [{'role': 'system', 'content': system_prompt}]
        for m in (history or [])[-MAX_HISTORY_MESSAGES:]:
            role = m.get('role') if isinstance(m, dict) else None
            content = m.get('content') if isinstance(m, dict) else None
            if role in ('user', 'assistant') and content:
                messages.append({'role': role, 'content': str(content)[:4000]})
        messages.append({'role': 'user', 'content': question})

        payload = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': False,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code >= 400:
            # Surface a useful slice of the provider's error so the user can fix config quickly.
            try:
                err_body = resp.json()
                err_msg = err_body.get('error', {}).get('message') if isinstance(err_body, dict) else None
            except ValueError:
                err_msg = None
            err_msg = err_msg or resp.text or ('HTTP %s' % resp.status_code)
            raise requests.exceptions.RequestException('HTTP %s: %s' % (resp.status_code, err_msg[:300]))

        try:
            data = resp.json()
        except ValueError:
            raise ValueError('AI provider returned a non-JSON response.')

        try:
            content = data['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError):
            raise ValueError('AI provider returned an unexpected response shape.')
        return (content or '').strip() or '(The AI returned an empty response. Try rephrasing your question.)'

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------
    def _build_system_prompt(self, snapshot):
        scope = snapshot.get('scope')
        if scope == 'score':
            return (
                "You are 'Bizdom Insights', a friendly, sharp business productivity analyst "
                "embedded in the Bizdom Odoo dashboard. You help small/medium business owners "
                "understand a single KPI and decide what to do next.\n\n"
                "Rules:\n"
                "- Be concise. Lead with a one-line verdict (e.g. 'On track', 'Behind target', 'At risk').\n"
                "- Use plain language; avoid jargon.\n"
                "- When suggesting actions, give 2-3 specific, doable next steps.\n"
                "- Compare current_value vs previous_period_value to describe trend.\n"
                "- For TAT (Turnaround Time), lower is better.\n"
                "- Use the status field (green/yellow/red/unknown) which already classifies the score against min/max.\n"
                "- If status is 'unknown', flag that thresholds aren't set rather than guessing.\n"
                "- The payload includes Q1/Q2/Q3 quadrant data. Q3 contains per-department breakdowns.\n"
                "- For questions like 'best employee in each department', iterate through q3_breakdown.departments.\n"
                "- Never invent numbers; only quote values present in the JSON below.\n"
                "- If the question can't be answered from this data, say so plainly.\n\n"
                "DATA (single score snapshot, JSON):\n%s"
            ) % json.dumps(snapshot, default=str)

        return (
            "You are 'Bizdom Insights', a friendly, sharp business productivity analyst "
            "embedded in the Bizdom Odoo dashboard. You help business owners understand "
            "their multi-pillar KPI dashboard and decide what to focus on.\n\n"
            "Rules:\n"
            "- Be concise. Lead with a one-line headline verdict.\n"
            "- For broad questions like 'how am I doing', give a 1-line summary per pillar, "
            "then a short list of 2-3 priorities.\n"
            "- Use the 'status' field on each score (green/yellow/red/unknown). It already classifies "
            "each score against its min/max thresholds.\n"
            "- For TAT (Turnaround Time), lower is better.\n"
            "- If a score's status is 'unknown', say its thresholds aren't set rather than judging it.\n"
            "- Never invent numbers; only use what's in the JSON below.\n"
            "- Score 'type' may be 'percentage', 'value', or 'currency_inr' — quote values with appropriate units.\n"
            "- If the user asks something not answerable from this snapshot, say so plainly.\n\n"
            "DATA (current dashboard snapshot, JSON):\n%s"
        ) % json.dumps(snapshot, default=str)
