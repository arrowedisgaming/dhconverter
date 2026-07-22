"""Container for the records a parser extracts from one source file."""
from dataclasses import dataclass, field
import sys
from pathlib import Path

try:
    from .adversary import Adversary
    from .environment import Environment
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.adversary import Adversary
    from models.environment import Environment


@dataclass
class ParseResult:
    """Records extracted from a source, split by kind.

    Markdown sources yield adversaries only; PDFs may yield both.
    """

    adversaries: list[Adversary] = field(default_factory=list)
    environments: list[Environment] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.adversaries) + len(self.environments)

    def __bool__(self) -> bool:
        return self.total > 0

    def extend(self, other: "ParseResult") -> None:
        self.adversaries.extend(other.adversaries)
        self.environments.extend(other.environments)
