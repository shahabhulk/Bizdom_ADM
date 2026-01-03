{
    'name': 'Bizdom Online Dashboard',
    "version": "18.0.0.0",
    'summary': 'Public online dashboard for Bizdom scores',
    'author': 'Your Name',
    'category': 'Customization',
    'depends': ['base', 'web', 'bizdom'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'assets': {
        'web.assets_backend': [],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}


