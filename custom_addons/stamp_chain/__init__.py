# -*- coding: utf-8 -*-
from . import models
from . import wizard


def _clear_assets(cr):
    """Limpa cache de assets.
    Garante que CSS/JS novos sao carregados."""
    cr.execute(
        "DELETE FROM ir_attachment "
        "WHERE url LIKE '/web/assets/%%'"
    )


def post_init_hook(cr, registry):
    """Corre na primeira instalacao (-i)."""
    _clear_assets(cr)


def uninstall_hook(cr, registry):
    """Placeholder — nao usado."""
    pass
