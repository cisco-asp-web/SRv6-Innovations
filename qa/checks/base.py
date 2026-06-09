from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Severity(Enum):
    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"   # check itself could not run (SSH failure, parse error, etc.)
    SKIP = "SKIP"     # upstream layer failed, result would be meaningless


@dataclass
class CheckResult:
    id: str
    name: str
    layer: int
    severity: Severity
    message: str
    detail: Optional[str] = None    # raw output or traceback — shown with --verbose
    duration_ms: int = 0
