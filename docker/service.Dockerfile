###############################################################################
#
# Service image for ghcr.io/nasa/variable-fan-out, a Harmony backend service
# that fans out a request for all variables to multiple downstream service
# containers via stac customization
#
# This image installs dependencies via UV. The service code is then copied
# into the Docker image.
###############################################################################
FROM python:3.14-slim

LABEL project="variable-fan-out"

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR "/home"

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-cache

# Copy service code.
COPY ./variable_fan_out variable_fan_out

ENV PATH="/home/.venv/bin:$PATH"

# Configure a container to be executable via the `docker run` command.
ENTRYPOINT ["python", "-m", "variable_fan_out"]
