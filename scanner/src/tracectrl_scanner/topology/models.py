from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Any


class NodeType(str, Enum):
    INGRESS = "INGRESS"
    AGENT = "AGENT"
    TOOL = "TOOL"
    LLM_PROVIDER = "LLM_PROVIDER"
    STORAGE = "STORAGE"
    EXTENSION = "EXTENSION"
    SCHEDULER = "SCHEDULER"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"
    SUBAGENT_SURFACE = "SUBAGENT_SURFACE"


class EdgeType(str, Enum):
    ROUTES_TO = "routes_to"
    INVOKES = "invokes"
    CALLS = "calls"
    WRITES_TO = "writes_to"
    HOOKS_INTO = "hooks_into"
    TRIGGERS = "triggers"
    SPAWNS = "spawns"
    REACHES = "reaches"


@dataclass
class Node:
    id: str
    type: NodeType
    label: str
    properties: dict[str, Any] = field(default_factory=dict)
    source: str = "static"


@dataclass
class Edge:
    id: str
    source: str
    target: str
    type: EdgeType
    properties: dict[str, Any] = field(default_factory=dict)
    source_origin: str = "static"


@dataclass
class TopologyGraph:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    openclaw_version: Optional[str] = None
    scan_timestamp: Optional[str] = None
