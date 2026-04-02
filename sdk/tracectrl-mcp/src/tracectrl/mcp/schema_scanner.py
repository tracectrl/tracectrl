"""Schema scanner — detects injection patterns in MCP tool descriptors."""

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "your new role is",
    "you are now",
    "disregard your",
    "new instructions:",
    "system prompt:",
    "forget your instructions",
    "override your",
]


def scan_tool_schema(tool_name: str, tool_description: str,
                     input_schema: dict | None = None) -> dict | None:
    text = f"{tool_description} {tool_name}".lower()
    if input_schema:
        text += f" {str(input_schema)}".lower()

    for pattern in INJECTION_PATTERNS:
        if pattern in text:
            return {"pattern": pattern, "tool_name": tool_name}
    return None
