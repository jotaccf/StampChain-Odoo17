FROM odoo:17.0

USER root

RUN pip3 install \
    pycryptodome>=3.15.0 \
    python-barcode>=0.15.1

USER odoo
