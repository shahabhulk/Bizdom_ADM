from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


PROVIDER_DEFAULTS = {
    'groq': {
        'base_url': 'https://api.groq.com/openai/v1',
        'model': 'llama-3.3-70b-versatile',
        'needs_key': True,
    },
    'ollama': {
        'base_url': 'http://localhost:11434/v1',
        'model': 'llama3.1:8b',
        'needs_key': False,
    },
    'openai': {
        'base_url': 'https://api.openai.com/v1',
        'model': 'gpt-4o-mini',
        'needs_key': True,
    },
    'openrouter': {
        'base_url': 'https://openrouter.ai/api/v1',
        'model': 'meta-llama/llama-3.1-8b-instruct:free',
        'needs_key': True,
    },
    'custom': {
        'base_url': '',
        'model': '',
        'needs_key': True,
    },
}


class BizdomAiSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bizdom_ai_enabled = fields.Boolean(
        string='Enable AI Insights',
        config_parameter='bizdom.ai.enabled',
        help='Show the AI Insights chat on the Bizdom dashboards.',
    )
    bizdom_ai_provider = fields.Selection(
        [
            ('groq', 'Groq (free, recommended)'),
            ('ollama', 'Ollama (self-hosted, fully private)'),
            ('openai', 'OpenAI'),
            ('openrouter', 'OpenRouter'),
            ('custom', 'Custom (OpenAI-compatible)'),
        ],
        string='AI Provider',
        default='groq',
        config_parameter='bizdom.ai.provider',
    )
    bizdom_ai_base_url = fields.Char(
        string='Base URL',
        config_parameter='bizdom.ai.base_url',
        help='OpenAI-compatible base URL, e.g. https://api.groq.com/openai/v1. '
             'Leave blank to use the default for the selected provider.',
    )
    bizdom_ai_model = fields.Char(
        string='Model',
        config_parameter='bizdom.ai.model',
        help='Model name, e.g. llama-3.3-70b-versatile, gpt-4o-mini, llama3.1:8b. '
             'Leave blank to use the default for the selected provider.',
    )
    bizdom_ai_api_key = fields.Char(
        string='API Key',
        config_parameter='bizdom.ai.api_key',
        help='API key for the selected provider. Not needed for local Ollama.',
    )
    bizdom_ai_timeout = fields.Integer(
        string='Request Timeout (seconds)',
        default=30,
        config_parameter='bizdom.ai.timeout',
    )
    bizdom_ai_temperature = fields.Float(
        string='Creativity (0.0 - 1.0)',
        default=0.4,
        config_parameter='bizdom.ai.temperature',
        help='Lower = more focused/factual. Higher = more creative. 0.4 is a good balance for analysis.',
    )
    bizdom_ai_max_tokens = fields.Integer(
        string='Max Response Tokens',
        default=800,
        config_parameter='bizdom.ai.max_tokens',
    )

    @api.onchange('bizdom_ai_provider')
    def _onchange_bizdom_ai_provider(self):
        """When the provider is changed, snap Base URL and Model to that provider's
        defaults. This prevents stale values (e.g. a marketing webpage URL) from
        carrying over when the user switches providers.

        For 'custom', clear both fields so the user is forced to fill them in.
        """
        defaults = PROVIDER_DEFAULTS.get(self.bizdom_ai_provider)
        if not defaults:
            return
        if self.bizdom_ai_provider == 'custom':
            # Wipe so the user knows they must enter their own values.
            if not self.bizdom_ai_base_url or self._is_invalid_api_url(self.bizdom_ai_base_url):
                self.bizdom_ai_base_url = ''
            if not self.bizdom_ai_model:
                self.bizdom_ai_model = ''
            return
        # For known providers, always reset to the canonical defaults.
        self.bizdom_ai_base_url = defaults['base_url']
        self.bizdom_ai_model = defaults['model']

    @api.constrains('bizdom_ai_base_url', 'bizdom_ai_provider')
    def _check_bizdom_ai_base_url(self):
        """Refuse obviously-wrong Base URLs (e.g. webpage URLs containing query
        strings, marketing paths, or HTML extensions) before they can break a call.
        """
        for record in self:
            url = (record.bizdom_ai_base_url or '').strip()
            if not url:
                continue
            if record._is_invalid_api_url(url):
                raise ValidationError(_(
                    "The Base URL '%s' doesn't look like an API endpoint.\n\n"
                    "Examples of valid Base URLs:\n"
                    "  - Groq:       https://api.groq.com/openai/v1\n"
                    "  - OpenAI:     https://api.openai.com/v1\n"
                    "  - Ollama:     http://localhost:11434/v1\n"
                    "  - OpenRouter: https://openrouter.ai/api/v1\n\n"
                    "Tip: leave Base URL blank to auto-use the default for the selected provider."
                ) % url)

    @staticmethod
    def _is_invalid_api_url(url):
        """Heuristic: catches the most common 'pasted the wrong URL' mistakes."""
        if not url:
            return False
        url = url.strip()
        if not (url.startswith('http://') or url.startswith('https://')):
            return True
        bad_signals = ('?', '#', 'welcome', 'pricing', 'signup', 'login',
                       '.html', '.htm', '/dashboard', '/account', '/billing')
        lowered = url.lower()
        for signal in bad_signals:
            if signal in lowered:
                return True
        return False
