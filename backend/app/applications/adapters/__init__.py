"""Registers all ATS adapters, most specific first, generic last.

detect_adapter() (see base.py) tries adapters in registration order and
returns the first match, so order here matters.
"""
from __future__ import annotations

from app.applications.adapters import base
from app.applications.adapters.base import ATSAdapter as ATSAdapter
from app.applications.adapters.base import detect_adapter as detect_adapter

try:
    # TODO(parallel-agent): confirm these once greenhouse.py/lever.py land;
    # written defensively so this module still imports (and Ashby/Generic
    # still register) if they aren't in place yet.
    from app.applications.adapters.greenhouse import greenhouse_adapter
    base.register(greenhouse_adapter)
except ImportError:
    pass

try:
    from app.applications.adapters.lever import lever_adapter
    base.register(lever_adapter)
except ImportError:
    pass

from app.applications.adapters.ashby import ashby_adapter
from app.applications.adapters.generic import generic_adapter

base.register(ashby_adapter)
base.register(generic_adapter)
