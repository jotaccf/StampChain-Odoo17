{
    'name': 'StampChain',
    'version': '17.0.2.4.0',
    'category': 'Manufacturing',
    'summary': 'Gestao de Armazem, Producao e '
               'Estampilhas IEC para Tabaco',
    'description': 'StampChain — Modulo vertical Odoo 17 Community '
                   'para gestao completa do ciclo de vida de produtos '
                   'sujeitos a IEC (tabaco). Conta corrente de estampilhas, '
                   'rastreabilidade individual, FIFO rigoroso, integracao '
                   'Wisedat, picking guiado handheld Android, QR codes, '
                   'auditoria de discrepancias, XML AT/DGAIEC.',
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
        'data/wisedat_cron.xml',
        'views/stamp_zone_views.xml',
        'views/stamp_lot_views.xml',
        'views/stamp_serial_views.xml',
        'views/stamp_movement_views.xml',
        'views/stamp_breakdown_views.xml',
        'views/stamp_recovery_views.xml',
        'views/stamp_dashboard.xml',
        'views/wisedat_config_views.xml',
        'views/wisedat_series_views.xml',
        'views/fiscal_document_views.xml',
        'views/warehouse_config_views.xml',
        'wizard/incm_reception_wizard_views.xml',
        'wizard/stamp_breakdown_wizard_views.xml',
        'wizard/min_stock_wizard_views.xml',
        'wizard/at_code_wizard_views.xml',
        'wizard/warehouse_setup_wizard_views.xml',
        'wizard/incm_ocr_reception_wizard_views.xml',
        'wizard/production_start_wizard_views.xml',
        'wizard/production_end_wizard_views.xml',
        'wizard/physical_count_wizard_views.xml',
        'views/stamp_audit_views.xml',
        'views/stamp_found_views.xml',
        'report/stamp_account_report.xml',
        'report/stamp_lot_traceability_report.xml',
        'report/picking_location_qr_report.xml',
        'views/stamp_physical_count_views.xml',
        'views/picking_handheld_views.xml',
        'wizard/warehouse_layout_wizard_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'stamp_chain/static/src/js/'
            'stamp_dashboard.js',
            'stamp_chain/static/src/xml/'
            'stamp_dashboard.xml',
            'stamp_chain/static/src/js/'
            'stamp_ocr_widget.js',
            'stamp_chain/static/src/xml/'
            'stamp_ocr_widget.xml',
            'stamp_chain/static/src/css/'
            'stamp.css',
            'stamp_chain/static/src/js/'
            'stamp_picking.js',
            'stamp_chain/static/src/xml/'
            'stamp_picking.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
