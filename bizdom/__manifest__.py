{
    'name': 'Bizdom',
    "version": "18.0.0.0",
    'summary': 'Add Pillars (SM, Operations, Finance) to Departments',
    'author': 'Your Name',
    'category': 'Customization',
    'depends': ['base', 'hr', 'mail', 'hr_timesheet', 'account', 'jwt_auth_api', 'car_repair_industry', 'board', 'web'],
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
        'views/score_dashboard.xml',
        'views/score_views.xml',
        'views/dashboard_views.xml',
        'views/category_views.xml'
        # 'views/signal_views.xml',
        # 'views/productivity_views.xml'

    ],
    'assets': {
        'web.assets_backend': [
            'bizdom/static/src/css/dashboard.css',
            'bizdom/static/src/xml/dashboard_templates.xml',
            'bizdom/static/src/js/dashboard.js',
            'bizdom/static/src/js/score_dashboard.js',
            'bizdom/static/src/xml/score_dashboard_templates.xml'
            # 'bizdom/static/src/css/swagger-ui.css',
            # 'bizdom/static/src/js/swagger-ui-bundle.js',
            # 'bizdom/static/src/js/swagger-ui-standalone-preset.js',
        ],
    },
    "post_init_hook": "post_init_add_performance_indexes",
    'installable': True,
    'auto_install': False,
}
