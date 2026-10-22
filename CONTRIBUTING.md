# Contributing to the Harmony Variable Fan Out Service

Thanks for contributing!

## Making Changes

To allow us to incorporate your changes, please use the [Fork-and-Pull](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/getting-started/about-collaborative-development-models#fork-and-pull-model) development model:

1. Fork this repository to your personal account.
2. Create a branch and make your changes.
3. Test the changes locally/in your personal fork.
4. Submit a pull request to open a discussion about your proposed changes.
5. The maintainers will talk with you about it and decide to merge or request additional changes.

For larger items, consider contacting the maintainers first to coordinate development efforts.

## Commits

Our ticketing and CI/CD tools are configured to sync statuses amongst each other. Commits play an important role in this process. Please start all commits with the Jira ticket number associated with your feature, task, or bug. All commit messages should follow the format "[Jira Project]-XXXX - [Your commit message here]", for example: "DAS-1234 - Add amazing feature to the Harmony Variable Fan Out Service."

## General coding practices

This repository uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting (`ruff format` follows [black](https://black.readthedocs.io/en/stable/) style). Both run as [pre-commit](https://pre-commit.com/) hooks; install them with `uv run pre-commit install`, or run them on demand with `uv run pre-commit run --all-files`. Additionally, type hints are encouraged in all function signatures.

When adding or updating functionality, please ensure unit tests are added to a `pytest` module in the `tests` directory, which should cover each branch of the code.

## Disclaimer

Harmony Variable Fan Out Service maintainers will review all pull requests submitted as they have time.  Only requests that meet the standard of quality set forth by existing code, following the patterns set forth by existing code, and adhering to existing design patterns will be considered and/or accepted.

For general tips on open source contributions, see [Contributing to Open Source on GitHub](https://guides.github.com/activities/contributing-to-open-source/).
