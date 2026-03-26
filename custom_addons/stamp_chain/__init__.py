# -*- coding: utf-8 -*-
from . import models
from . import wizard


def post_init_hook(cr, registry):
    """Limpa cache de assets a cada update.
    Garante que CSS/JS novos sao carregados."""
    cr.execute(
        "DELETE FROM ir_attachment "
        "WHERE url LIKE '/web/assets/%%'"
    )
