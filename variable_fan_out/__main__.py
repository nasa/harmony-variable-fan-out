"""
Entrypoint for variable_fan_out service.
"""

import argparse

import harmony_service_lib

from .adapter import VariableFanOutAdapter


def main():
    """
    Parses command line arguments and invokes the appropriate method to respond to them
    Returns
    -------
    None
    """
    parser = argparse.ArgumentParser(
        prog="variable_fan_out", description="Run the variable fan out service"
    )
    harmony_service_lib.setup_cli(parser)
    args = parser.parse_args()
    if harmony_service_lib.is_harmony_cli(args):
        harmony_service_lib.run_cli(parser, args, VariableFanOutAdapter)
    else:
        parser.error("Only --harmony CLIs are supported")


if __name__ == "__main__":
    main()
