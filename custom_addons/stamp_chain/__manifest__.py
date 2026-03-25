{
    'name': 'StampChain',
    'version': '17.0.1.2.0',
    'category': 'Manufacturing',
    'summary': 'Gestão de Armazém, Produção e '
               'Estampilhas IEC para Tabaco',
    'description': '''
        StampChain — Módulo vertical Odoo 17
        Community para gestão completa do ciclo
        de vida de produtos sujeitos a IEC
        (tabaco).

        Funcionalidades:
        - Conta corrente de estampilhas IEC
          por zona geográfica
        - Rastreabilidade individual por
          número de série
        - FIFO rigoroso por lote INCM
        - Integração bidirecional Wisedat
        - Picking guiado por handheld Android
          via browser nativo
        - QR codes para prateleiras e produtos
        - Controlo de qualidade inline
        - Arquitectura XML AT/DGAIEC (v2.0)
    ''',
    'author': 'StampChain Development',
    'license': 'LGPL-3',
    'depends': [
        'stock',
        'mrp',
        'sale_management',
        'purchase',
        'account',
        'delivery',
        'mail',
        'barcodes_generator_location',
        'barcodes_generator_product',
        'product_multi_barcode',
        'stock_picking_product_barcode_report',
        'quality_control_oca',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/stamp_zones.xml',
        'data/sequences.xml',
        'views/stamp_zone_views.xml',
        'views/stamp_lot_views.xml',
        'views/stamp_serial_views.xml',
        'views/stamp_movement_views.xml',
        'views/stamp_breakdown_views.xml',
        'views/stamp_recovery_views.xml',
        'views/stamp_dashboard.xml',
        'views/wisedat_config_views.xml',
        'views/fiscal_document_views.xml',
        'views/warehouse_config_views.xml',
        'wizard/incm_reception_wizard_views.xml',
        'wizard/stamp_breakdown_wizard_views.xml',
        'wizard/min_stock_wizard_views.xml',
        'wizard/at_code_wizard_views.xml',
        'wizard/warehouse_setup_wizard_views.xml',
        'report/stamp_account_report.xml',
        'report/stamp_lot_traceability_report.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'stamp_chain/static/src/js/'
            'stamp_dashboard.js',
            'stamp_chain/static/src/xml/'
            'stamp_dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
