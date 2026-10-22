###############################################################################
# Variable Fan Out test image
#
# Built on the main service image to ensure test environment matches production
# environment.  Adds dev dependencies and test files.
#
###############################################################################
FROM ghcr.io/nasa/variable-fan-out

RUN uv sync --frozen --group dev --no-cache

COPY ./tests tests

ENTRYPOINT ["/home/tests/run_tests.sh"]
