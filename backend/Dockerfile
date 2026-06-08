FROM mambaorg/micromamba:1.5.10

# Install the conda environment first so it is cached across code changes.
COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
RUN micromamba install -y -n base -f /tmp/environment.yml \
    && micromamba clean --all --yes

WORKDIR /workspace
COPY --chown=$MAMBA_USER:$MAMBA_USER . /workspace

ENV PYTHONUNBUFFERED=1 \
    RFQ_ENVIRONMENT=production

# Railway injects $PORT at runtime; fall back to 8000 for local docker runs.
CMD micromamba run -n base uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
