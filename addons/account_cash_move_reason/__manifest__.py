{
    'name': "Types d'operation de caisse",
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': "Gestion des types d'operation, brouillard de caisse, PDF, transfert interne et mise en forme Sage des rapports OCA",
    'author': 'Custom',
    'depends': ['account', 'account_financial_report', 'account_reconcile_oca'],
    'data': [
        'wizard/cash_brouillard_wizard_view.xml',
        'views/cash_move_reason_views.xml',
        'reports/cash_brouillard_report.xml',
        'reports/general_ledger_sage.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
