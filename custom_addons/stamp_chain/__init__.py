# -*- coding: utf-8 -*-
from . import models
from . import wizard


def post_load():
    """Corre sempre que o servidor arranca.
    Limpa assets durante -u ou -i para
    garantir CSS/JS actualizados."""
    import logging
    _logger = logging.getLogger(__name__)
    try:
        import odoo
        update = odoo.tools.config.get('update')
        init = odoo.tools.config.get('init')
        updating = (
            (isinstance(update, dict)
             and update.get('stamp_chain'))
            or (isinstance(init, dict)
                and init.get('stamp_chain'))
        )
        if not updating:
            return
        from odoo import sql_db
        db_name = odoo.tools.config.get('db_name')
        if not db_name:
            return
        db = sql_db.db_connect(db_name)
        with db.cursor() as cr:
            cr.execute(
                "DELETE FROM ir_attachment "
                "WHERE url LIKE '/web/assets/%%'"
            )
        _logger.info(
            'StampChain: assets cache limpa.'
        )
    except Exception as e:
        _logger.warning(
            'StampChain post_load: %s', e
        )


def post_init_hook(env):
    """Corre na primeira instalacao (-i).
    Odoo 17 passa env (nao cr, registry)."""
    env.cr.execute(
        "DELETE FROM ir_attachment "
        "WHERE url LIKE '/web/assets/%%'"
    )
