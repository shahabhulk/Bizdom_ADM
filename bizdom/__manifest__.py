{
    'name': 'Bizdom',
    "version": "18.0.0.0",
    'summary': 'Add Pillars (SM, Operations, Finance) to Departments',
    'author': 'Your Name',
    'category': 'Customization',
    'depends': ['base', 'hr', 'mail', 'hr_timesheet', 'account', 'jwt_auth_api', 'car_repair_industry', 'board'],
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'security/security.xml',
        'views/bizdom_menu.xml',
        'views/pillar_views.xml',
        'views/labour_billing.xml',
        'views/feedback_data.xml',
        'views/timesheet_data.xml',
        # 'wizard/productivity_wizard_views.xml'
        'views/score_views.xml',
        'views/dashboard_views.xml'
        # 'views/signal_views.xml',
        # 'views/productivity_views.xml'

    ],
    'assets': {
        'web.assets_backend': [
            'bizdom/static/src/xml/dashboard_templates.xml',
            'bizdom/static/src/js/dashboard.js'
        ],
    },
    "post_init_hook": "post_init_sync_feedback_data",
    'installable': True,
    'auto_install': False,
}
