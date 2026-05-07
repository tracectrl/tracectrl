"""Skills security checks.

Evaluates the skills.entries section of openclaw.json — third-party
integrations like Notion, GitHub, Gmail, etc. that the agent can invoke.
"""
from pathlib import Path
from typing import Any

from ..models import CheckResult, Severity, Profile, AssessmentType

# Skills known to have write or sensitive-read capabilities, grouped by risk.
# Maps skill name (lowercase) → short capability description.
_HIGH_RISK_SKILLS: dict[str, str] = {
    "notion":           "read/write Notion pages and databases",
    "github":           "read/write GitHub repositories and issues",
    "gitlab":           "read/write GitLab repositories",
    "gmail":            "send email and read inbox",
    "google-mail":      "send email and read inbox",
    "google-docs":      "read/write Google Docs",
    "google-drive":     "read/write Google Drive files",
    "gdrive":           "read/write Google Drive files",
    "google-sheets":    "read/write Google Sheets",
    "sheets":           "read/write Google Sheets",
    "jira":             "read/write Jira issues and projects",
    "confluence":       "read/write Confluence pages",
    "salesforce":       "access CRM customer data",
    "hubspot":          "access CRM customer data",
    "slack":            "post messages to Slack channels",
    "linear":           "read/write Linear issues",
    "airtable":         "read/write Airtable bases",
    "postgres":         "direct database read/write access",
    "mysql":            "direct database read/write access",
    "mongodb":          "direct database read/write access",
    "database":         "direct database access",
    "file":             "read/write local filesystem",
    "filesystem":       "read/write local filesystem",
    "code-interpreter": "execute arbitrary code",
    "python":           "execute Python code",
    "jupyter":          "execute Jupyter notebooks",
    "aws":              "AWS cloud API access",
    "azure":            "Azure cloud API access",
    "gcp":              "Google Cloud Platform API access",
    "sendgrid":         "send bulk email",
    "mailchimp":        "send bulk email",
    "twilio":           "send SMS messages",
    "stripe":           "payment and billing access",
}

_CREDENTIAL_KEY_NAMES = {"apikey", "api_key", "token", "secret", "password", "key"}


def _get_skill_entries(config: dict[str, Any]) -> dict[str, Any]:
    skills = config.get("skills", {})
    entries = skills.get("entries", {})
    return entries if isinstance(entries, dict) else {}


def _has_plaintext_credential(skill_cfg: Any) -> bool:
    """Return True if any credential key in the skill config holds a plaintext value."""
    if not isinstance(skill_cfg, dict):
        return False
    for k, v in skill_cfg.items():
        if k.lower() in _CREDENTIAL_KEY_NAMES and isinstance(v, str) and v:
            import re
            if re.match(r"^\$\{.+\}$", v):
                continue  # env var reference — safe
            return True
    return False


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    entries = _get_skill_entries(config)

    if not entries:
        # No skills configured — all checks pass trivially.
        results.append(CheckResult(
            check_id="OC-SKILL-001",
            section="Skills",
            title="Skill credentials use environment variable references",
            severity=Severity.HIGH,
            profile=Profile.L1,
            assessment_type=AssessmentType.AUTOMATED,
            passed=True,
            finding=None,
            remediation="Store skill API keys as ${ENV_VAR} references instead of plaintext values.",
            config_path="skills.entries",
            rationale="Plaintext credentials in skills.entries can be read by any process with config file access and leaked via logs or version control.",
        ))
        results.append(CheckResult(
            check_id="OC-SKILL-002",
            section="Skills",
            title="High data-risk skills are acknowledged and intentional",
            severity=Severity.HIGH,
            profile=Profile.L1,
            assessment_type=AssessmentType.AUTOMATED,
            passed=True,
            finding=None,
            remediation="For each high-risk skill, ensure the agent's SOUL.md scope is restricted to prevent data exfiltration via prompt injection.",
            config_path="skills.entries",
            rationale="Skills with write access to external services (Notion, GitHub, Gmail, etc.) can be abused by a prompt-injected agent to exfiltrate or corrupt data.",
        ))
        results.append(CheckResult(
            check_id="OC-SKILL-003",
            section="Skills",
            title="Skill surface area is within recommended limits",
            severity=Severity.MEDIUM,
            profile=Profile.L1,
            assessment_type=AssessmentType.AUTOMATED,
            passed=True,
            finding=None,
            remediation="Remove unused skills from skills.entries to reduce the agent's blast radius.",
            config_path="skills.entries",
            rationale="Each additional skill increases the blast radius if the agent is compromised. Only enable skills that are actively used.",
        ))
        results.append(CheckResult(
            check_id="OC-SKILL-004",
            section="Skills",
            title="All configured skills have a known risk profile",
            severity=Severity.MEDIUM,
            profile=Profile.L2,
            assessment_type=AssessmentType.MANUAL,
            passed=True,
            finding=None,
            remediation="Document the data access scope for each unrecognized skill and ensure it follows least-privilege.",
            config_path="skills.entries",
            rationale="Unrecognized skills may have undocumented capabilities. A manual review ensures no unexpected data access is granted.",
        ))
        return results

    skill_names = list(entries.keys())

    # OC-SKILL-001: Plaintext credentials in skills.entries
    plaintext_skills = [
        name for name, cfg in entries.items()
        if _has_plaintext_credential(cfg)
    ]
    results.append(CheckResult(
        check_id="OC-SKILL-001",
        section="Skills",
        title="Skill credentials use environment variable references",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=len(plaintext_skills) == 0,
        finding=(
            f"Plaintext credentials in skills: {', '.join(plaintext_skills)}. "
            "Use ${{ENV_VAR}} references instead."
        ) if plaintext_skills else None,
        remediation="Replace inline API keys with ${ENV_VAR} references (e.g. ${NOTION_API_KEY}) and store values in a .env file excluded from version control.",
        config_path="skills.entries.<name>.apiKey",
        rationale="Plaintext credentials in skills.entries can be read by any process with config file access and leaked via logs or version control.",
    ))

    # OC-SKILL-002: High data-risk skills
    risky: list[tuple[str, str]] = [
        (name, _HIGH_RISK_SKILLS[name.lower()])
        for name in skill_names
        if name.lower() in _HIGH_RISK_SKILLS
    ]
    if risky:
        detail = "; ".join(f"{n} ({cap})" for n, cap in risky)
        finding = f"{len(risky)} high data-risk skill(s) active: {detail}"
    else:
        finding = None
    results.append(CheckResult(
        check_id="OC-SKILL-002",
        section="Skills",
        title="High data-risk skills are acknowledged and intentional",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=len(risky) == 0,
        finding=finding,
        remediation="For each high-risk skill, restrict the agent's SOUL.md to explicitly forbid using the skill to access data outside its intended scope. Consider using read-only API keys where the service supports it.",
        config_path="skills.entries",
        rationale="Skills with write access to external services (Notion, GitHub, Gmail, etc.) can be abused by a prompt-injected agent to exfiltrate or corrupt data.",
    ))

    # OC-SKILL-003: Surface area — more than 5 active skills is high blast radius
    skill_count = len(skill_names)
    threshold = 5
    results.append(CheckResult(
        check_id="OC-SKILL-003",
        section="Skills",
        title="Skill surface area is within recommended limits",
        severity=Severity.MEDIUM,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=skill_count <= threshold,
        finding=(
            f"{skill_count} skills configured ({', '.join(skill_names)}). "
            f"Recommended maximum is {threshold}."
        ) if skill_count > threshold else None,
        remediation="Remove unused skills from skills.entries. Each active skill increases the agent's blast radius if compromised via prompt injection.",
        config_path="skills.entries",
        rationale="Each additional skill increases the blast radius if the agent is compromised. Only enable skills that are actively used.",
    ))

    # OC-SKILL-004: Unknown skills — not in the known catalog (manual review needed)
    unknown = [name for name in skill_names if name.lower() not in _HIGH_RISK_SKILLS]
    results.append(CheckResult(
        check_id="OC-SKILL-004",
        section="Skills",
        title="All configured skills have a known risk profile",
        severity=Severity.MEDIUM,
        profile=Profile.L2,
        assessment_type=AssessmentType.MANUAL,
        passed=len(unknown) == 0,
        finding=(
            f"Unrecognized skills with no known risk profile: {', '.join(unknown)}. "
            "Manual review required."
        ) if unknown else None,
        remediation="Document the data access scope for each unrecognized skill and ensure it follows least-privilege. Add it to your internal integration registry.",
        config_path="skills.entries",
        rationale="Unrecognized skills may have undocumented capabilities. A manual review ensures no unexpected data access is granted.",
    ))

    return results
