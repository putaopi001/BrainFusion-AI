FROM python:3.9-slim-bookworm@sha256:a02e9c5406c416c504d6c9a1a306ff4080c3173f1008d192f953bd20382a2d5c AS radiomics

WORKDIR /opt/radiomics
COPY requirements-radiomics-linux-amd64.txt requirements-radiomics-docopt.txt ./
COPY tools/extract_selected_radiomics.py tools/write_radiomics_provenance.py ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements-radiomics-docopt.txt \
 && python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements-radiomics-linux-amd64.txt
COPY Dockerfile ./source-Dockerfile
RUN python -m pip check && python write_radiomics_provenance.py

FROM python:3.10-slim-bookworm@sha256:5be5aaecb962a41567bc8041f1e9e3432cb085b037fe057f9a562630b2e4b370 AS api

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UPLOAD_DIR=/app/runtime/uploads
ENV FEATURE_JOBS_DIR=/app/runtime/feature_jobs
ARG INSTALL_PROFILE=core

# core is the light web profile; full matches the Compose AI/research deployment.
COPY requirements-core.txt requirements-docker-core-py310-linux-amd64.txt requirements-docker-full-py310-linux-amd64.txt ./
RUN if [ "$INSTALL_PROFILE" = "full" ]; then \
        pip install --no-cache-dir --only-binary=:all: --require-hashes \
        --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple \
        -r requirements-docker-full-py310-linux-amd64.txt; \
    elif [ "$INSTALL_PROFILE" = "core" ]; then \
        pip install --no-cache-dir --only-binary=:all: --require-hashes \
        -r requirements-docker-core-py310-linux-amd64.txt; \
    else echo "Unsupported INSTALL_PROFILE: $INSTALL_PROFILE" >&2; exit 2; fi

COPY app ./app
COPY tools ./tools
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# PyRadiomics 3.1.0 has no supported CPython 3.10 wheel. Embed the independently
# locked Linux CPython 3.9 worker without changing the web/API interpreter.
FROM api AS full
COPY --from=radiomics /usr/local /opt/radiomics
COPY --from=radiomics /opt/radiomics/source.json /opt/radiomics/source.json
RUN printf '#!/bin/sh\nexport PYTHONHOME=/opt/radiomics\nexport LD_LIBRARY_PATH=/opt/radiomics/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\nexec /opt/radiomics/bin/python3.9 "$@"\n' > /opt/radiomics/run-python \
 && chmod 0755 /opt/radiomics/run-python \
 && /opt/radiomics/run-python -c "import sys, radiomics, numpy, SimpleITK; assert sys.version_info[:2] == (3, 9); print(radiomics.__version__, numpy.__version__, SimpleITK.Version_VersionString())" \
 && /opt/radiomics/run-python -m pip check

# Keep the default image lightweight; Compose explicitly selects the full target.
FROM api AS core
