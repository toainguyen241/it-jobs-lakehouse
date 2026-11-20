FROM apache/airflow:2.10.2-python3.11@sha256:7c68d8ac3cf1b2c69eeb91da64c1578dc8376d33abf34267bf6e547d071cae39

ARG DEBIAN_SNAPSHOT=20260825T000000Z

USER airflow

# ---- Python deps ----
COPY --chown=airflow:root pyproject.toml uv.lock /opt/airflow/
WORKDIR /opt/airflow

RUN python -m venv /opt/airflow/pipeline_venv && \
    /opt/airflow/pipeline_venv/bin/pip install --no-cache-dir "uv==0.12.5" && \
    /opt/airflow/pipeline_venv/bin/uv export --frozen --no-hashes --no-dev \
        --format requirements-txt > /tmp/requirements.txt && \
    /opt/airflow/pipeline_venv/bin/pip install --no-cache-dir \
        -r /tmp/requirements.txt


USER root
RUN set -eux; \
    printf '%s\n' \
        "deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}/ bookworm main" \
        "deb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}/ bookworm-security main" \
        > /etc/apt/sources.list.d/debian-snapshot.list; \
    rm -f /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        wget \
        gnupg \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        libpango-1.0-0 \
        libcairo2 \
    ; \
    wget -q https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_151.0.7922.173-1_amd64.deb \
        -O /tmp/google-chrome.deb; \
    echo "878e5ab495b8a694980fca61bc09b37e651ccedce2291c73434d16e48a2646fd  /tmp/google-chrome.deb" \
        | sha256sum -c -; \
    apt-get install -y --no-install-recommends /tmp/google-chrome.deb; \
    rm -f /tmp/google-chrome.deb; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

USER airflow

# ---- Copy source code ----
COPY --chown=airflow:root src/ /opt/airflow/src/
COPY --chown=airflow:root dags/ /opt/airflow/dags/
COPY --chown=airflow:root scripts/publish_marts_to_supabase.py /opt/airflow/scripts/
COPY --chown=airflow:root transform_dbt/ /opt/airflow/transform_dbt/
COPY --chown=airflow:root crawl_itviec.py /opt/airflow/

ENV PYTHONPATH=/opt/airflow
