"""Diagnostic: track when any ideer logger gets disabled=True under pytest."""

import logging
import traceback

orig_issubclass = issubclass

# Patch logging.Logger class to intercept disabled=True on any ideer logger
_orig_setattr = logging.Logger.__setattr__


def _traced_setattr(self, name, value):
    if name == "disabled" and value and "ideer" in self.name:
        print(f"\n=== LOGGER DIAG: {self.name} disabled -> {value} ===")
        for line in traceback.format_stack()[-12:-1]:
            print(f"    {line.strip()}")
    _orig_setattr(self, name, value)


logging.Logger.__setattr__ = _traced_setattr
