"""Portable, read-only DreamReader control plane."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

__version__ = (PROJECT_ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
