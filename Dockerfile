FROM python:3.12-slim-bookworm

ENV PATH="/usr/local/bin:/opt/sentinel/.venv/bin:$PATH" \
    SENTINEL_DATA_DIR=/opt/sentinel/data \
    SENTINEL_RUN_ON_HOST=1

COPY docker/llama /usr/local/bin/llama
COPY docker/venv /opt/sentinel/.venv
COPY src /opt/sentinel/src
COPY data /opt/sentinel/data
COPY models /opt/sentinel/models
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/llama /usr/local/bin/entrypoint.sh \
    && ln -sfn /usr/local/bin/python3 /opt/sentinel/.venv/bin/python \
    && ln -sfn python /opt/sentinel/.venv/bin/python3 \
    && printf '%s\n' \
         'home = /usr/local/bin' \
         'implementation = CPython' \
         'version_info = 3.12.14' \
         'include-system-site-packages = false' \
         > /opt/sentinel/.venv/pyvenv.cfg \
    && printf '/opt/sentinel/src\n' \
         > /opt/sentinel/.venv/lib/python3.12/site-packages/sentinel.pth \
    && find /opt/sentinel/.venv/bin -type f -exec \
         sed -i '1s|^#!.*python.*|#!/opt/sentinel/.venv/bin/python3|' {} +

WORKDIR /opt/sentinel
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
