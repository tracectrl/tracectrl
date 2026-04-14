"""Tool category and direction inference from tool name and description."""

TOOL_CATEGORY_RULES = [
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in ["exec", "run_code", "python", "bash", "shell", "eval", "compile"]), "code_execution"),
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in ["send_email", "send_mail", "email", "smtp"]), "email"),
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in ["http", "fetch", "request", "curl", "scrape", "browse", "web"]), "external_api"),
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in ["write_file", "save_file", "create_file", "delete_file", "rm ", " mv "]), "file_system"),
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in ["vector", "embed", "upsert", "add_document", "index"]), "memory_write"),
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in ["search", "query", "retrieve", "recall", "lookup"]), "memory_read"),
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in ["human", "approval", "confirm", "ask_user", "hitl"]), "human_interaction"),
    (lambda n, d: True, "internal_api"),
]


def infer_tool_category(tool_name: str, tool_description: str = "") -> str:
    """Classify a tool into a risk category based on its name and description."""
    for match_fn, category in TOOL_CATEGORY_RULES:
        if match_fn(tool_name, tool_description):
            return category
    return "internal_api"


# Tool direction inference: input (ingress), output (egress), or internal
TOOL_DIRECTION_RULES = [
    # INPUT/INGRESS patterns - data coming IN to the system
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in
        ["receive", "fetch", "get_", "read_", "check_", "poll", "listen", "watch",
         "webhook_handler", "api_handler", "endpoint", "upload_handler", "inbound",
         "retrieve", "download", "pull", "import", "load", "inbox", "accept"]), "input"),

    # OUTPUT/EGRESS patterns - data going OUT of the system
    (lambda n, d: any(k in n.lower() or k in d.lower() for k in
        ["send", "post", "put", "push", "publish", "emit", "write", "create",
         "execute", "run", "call", "invoke", "trigger", "dispatch", "submit",
         "export", "transmit", "deliver", "forward", "outbound"]), "output"),

    # Default to internal
    (lambda n, d: True, "internal"),
]


def infer_tool_direction(tool_name: str, tool_description: str = "") -> str:
    """Determine if a tool is input (ingress), output (egress), or internal.

    Returns:
        "input": Data flowing INTO the system (webhooks, file uploads, email receipts)
        "output": Data flowing OUT of the system (send email, API calls, file writes)
        "internal": Internal processing (searches, queries, transformations)
    """
    for match_fn, direction in TOOL_DIRECTION_RULES:
        if match_fn(tool_name, tool_description):
            return direction
    return "internal"


TRIGGER_TYPE_PATTERNS = [
    (["email", "mail", "imap", "smtp", "inbox"], "email"),
    (["upload", "file_upload", "document_upload"], "upload"),
    (["webhook", "http_trigger", "api_trigger"], "webhook"),
    (["schedule", "cron", "timer", "periodic"], "scheduled"),
    (["manual", "user_request", "direct"], "manual"),
]


def infer_trigger_type(span_name: str, func_name: str = "") -> str | None:
    """Infer trigger type from span name or function name."""
    combined = f"{span_name.lower()} {func_name.lower()}"
    for patterns, trigger_type in TRIGGER_TYPE_PATTERNS:
        if any(pattern in combined for pattern in patterns):
            return trigger_type
    return None
