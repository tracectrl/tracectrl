from enum import Enum
from dataclasses import dataclass
from typing import Optional

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    PASS = "PASS"
    MANUAL = "MANUAL"

class Profile(str, Enum):
    L1 = "L1"  # baseline — all deployments
    L2 = "L2"  # hardened — production deployments

class AssessmentType(str, Enum):
    AUTOMATED = "Automated"
    MANUAL = "Manual"

@dataclass
class CheckResult:
    check_id: str
    section: str
    title: str
    severity: Severity
    profile: Profile
    assessment_type: AssessmentType
    passed: bool
    finding: Optional[str]
    remediation: str
    config_path: Optional[str] = None
    rationale: Optional[str] = None  # WHY this matters — attack vector explanation
