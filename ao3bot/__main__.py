"""Allows `python -m ao3bot ...` as well as the `ao3bot` command."""

from .cli import main

raise SystemExit(main())
