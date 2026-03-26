def migrate(cr, version):
    """Limpa assets cache apos update."""
    cr.execute(
        "DELETE FROM ir_attachment "
        "WHERE url LIKE '/web/assets/%%'"
    )
