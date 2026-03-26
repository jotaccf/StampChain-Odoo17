# -*- coding: utf-8 -*-
from . import models
from . import wizard


def post_load():
    """Corre sempre que o servidor arranca.
    Nao precisa de -i ou -u. Limpa assets
    para garantir CSS/JS actualizados."""
    import odoo
    if odoo.tools.config.get('update', {}).get(
        'stamp_chain'
    ) or odoo.tools.config.get('init', {}).get(
        'stamp_chain'
    ):
        # So limpa durante -u ou -i, nao em
        # cada arranque normal do servidor
        from odoo import sql_db
        db_name = odoo.tools.config.get('db_name')
        if db_name:
            db = sql_db.db_connect(db_name)
            with db.cursor() as cr:
                cr.execute(
                    "DELETE FROM ir_attachment "
                    "WHERE url LIKE '/web/assets/%%'"
                )


def post_init_hook(cr, registry):
    """Corre na primeira instalacao (-i)."""
    cr.execute(
        "DELETE FROM ir_attachment "
        "WHERE url LIKE '/web/assets/%%'"
    )
