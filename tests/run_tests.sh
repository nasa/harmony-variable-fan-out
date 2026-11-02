#!/bin/sh
###############################################################################
#
# Run the harmony-variable-fan-out test suite with coverage. Invoked as the
# entrypoint of the ghcr.io/nasa/harmony-variable-fan-out-test image; XML test
# results and coverage reports are written to /home/reports, which
# bin/run-test mounts from the host.
#
###############################################################################

pytest --cov=variable_fan_out \
       --cov-report=html:reports/coverage \
       --cov-report term \
       --junitxml=reports/test-reports/test-results.xml
