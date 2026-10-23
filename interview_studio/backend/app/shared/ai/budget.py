from dataclasses import dataclass, field


@dataclass
class RetrievalBudget:
    """A request attempt's retrieval limits."""
    used_tool_calls: int = 0
    used_chars: int = 0
    seen_chunks: set[int] = field(default_factory=set)
