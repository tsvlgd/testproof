from __future__ import annotations

import json
from dataclasses import asdict

from testproof.models import Report


def to_json(report: Report) -> str:
    return json.dumps(asdict(report), indent=2, sort_keys=True)
