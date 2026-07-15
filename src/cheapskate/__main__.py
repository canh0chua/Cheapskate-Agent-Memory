"""Cheapskate Agent Memory - command-line interface."""

from cheapskate.hooks import run_hooks
from cheapskate.cli import main

if __name__ == "__main__":
    # Run session start hooks before CLI executes
    run_hooks('on_session_start', project=None)
    main()
