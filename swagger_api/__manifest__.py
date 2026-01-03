{
    'name': 'Swagger API Documentation',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'API Documentation using Swagger UI',
    'depends': ['base', 'web'],
    'data': [
        'views/templates.xml',
    ],
    # Assets are loaded directly in the template, not via manifest
    # to avoid loading on login page and causing conflicts
    'installable': True,
    'application': False,
    'auto_install': False,
}