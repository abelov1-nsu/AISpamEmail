"""Official package entry point for the email analyzer."""

from .cli import main


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
