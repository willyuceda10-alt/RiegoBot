import sys


def python_version_ok() -> bool:
    return sys.version_info >= (3, 11)
