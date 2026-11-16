# Hugging Face Docker Space: ResolveIT API + background worker + verified INT8 bundle.
# Build context is assembled by scripts/deploy/assemble_hf_space.py (code subset + bundle).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
    PYTHONPATH=/app/apps/api:/app/apps/worker:/app/enterprise \
    RESOLVEIT_BUNDLE_DIR=/app/bundle RESOLVEIT_ENCODER_THREADS=2 PORT=7860
WORKDIR /app
COPY requirements-runtime.txt requirements-model.txt ./
COPY packages/resolveit-core packages/resolveit-core
COPY packages/resolveit-frames packages/resolveit-frames
COPY apps/api apps/api
COPY apps/worker apps/worker
COPY enterprise enterprise
COPY scripts/bootstrap_db.py scripts/bootstrap_db.py
COPY infra/migrations infra/migrations
COPY alembic.ini .
RUN pip install --no-cache-dir -r requirements-runtime.txt -r requirements-model.txt \
    ./packages/resolveit-core ./apps/api
COPY bundle bundle
COPY hfspace_entrypoint.sh /usr/local/bin/resolveit-space
RUN sed -i 's/\r$//' /usr/local/bin/resolveit-space && chmod 755 /usr/local/bin/resolveit-space \
    && useradd --create-home --uid 1000 resolveit && chown -R resolveit /app
USER resolveit
EXPOSE 7860
CMD ["/usr/local/bin/resolveit-space"]
