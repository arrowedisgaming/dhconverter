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
    # Stat blocks the parser recognised but could not turn into a record,
    # described by their opening lines. Without this a source written in a
    # layout the parser does not understand reports nothing at all, which is
    # indistinguishable from a source that holds no stat blocks (issue #2).
    rejected: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.adversaries) + len(self.environments)

    @property
    def blocks_detected(self) -> int:
        """Stat blocks found, whether or not they parsed."""
        return self.total + len(self.rejected)

    def __bool__(self) -> bool:
        return self.total > 0

    def extend(self, other: "ParseResult") -> None:
        self.adversaries.extend(other.adversaries)
        self.environments.extend(other.environments)
        self.rejected.extend(other.rejected)
