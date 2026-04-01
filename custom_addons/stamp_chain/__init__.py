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
            # Fix cron: corrigir nextcall, intervalo
            # e noupdate flag na BD
            cr.execute(
                "UPDATE ir_cron SET "
                "  nextcall = NOW() + interval "
                "  '15 minutes', "
                "  interval_number = 15, "
                "  interval_type = 'minutes' "
                "WHERE id = ("
                "  SELECT res_id "
                "  FROM ir_model_data "
                "  WHERE module = 'stamp_chain' "
                "  AND name = "
                "  'ir_cron_wisedat_sync'"
                ")"
            )
            cr.execute(
                "UPDATE ir_model_data "
                "SET noupdate = false "
                "WHERE module = 'stamp_chain' "
                "AND name = "
                "'ir_cron_wisedat_sync'"
            )
            # Fix defaults para configs existentes
            cr.execute(
                "UPDATE tobacco_wisedat_config "
                "SET sync_products = true "
                "WHERE sync_products IS NOT TRUE"
            )
            cr.execute(
                "UPDATE tobacco_wisedat_config "
                "SET sync_customers = true "
                "WHERE sync_customers IS NOT TRUE"
            )
        _logger.info(
            'StampChain: assets cache limpa, '
            'cron sync corrigido.'
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
