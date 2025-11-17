{
    'name': 'Swagger API Documentation',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'API Documentation using Swagger UI',
    'depends': ['base', 'web'],
    'data': [
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'swagger_api/static/lib/swagger/swagger-ui.css',
            'swagger_api/static/lib/swagger/swagger-ui-bundle.js',
            'swagger_api/static/lib/swagger/swagger-ui-standalone-preset.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}