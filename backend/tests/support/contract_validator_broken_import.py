"""A declared validator module that raises at import time (not ImportError).

Used to prove the parser wraps arbitrary import failures into its standard
``ValueError`` error contract instead of leaking the raw exception.
"""

raise RuntimeError("broken validator module import")
