"""Domain exception hierarchy for the textlayout package.

All errors raised by the deterministic core inherit from :class:`TextLayoutError`
so that the driver layers (FastAPI, MCP, CLI) can translate the whole family into
structured responses with a single ``except``.
"""

from __future__ import annotations


class TextLayoutError(Exception):
    """Base class for every error raised by the textlayout core."""


class UnknownComponentError(TextLayoutError):
    """Raised when a DSL ``component`` has no registered generator."""

    def __init__(self, component: str, available: list[str]) -> None:
        self.component = component
        self.available = available
        super().__init__(
            f"Unknown component {component!r}. Registered generators: {sorted(available)}"
        )


class UnknownTechnologyError(TextLayoutError):
    """Raised when a DSL ``technology`` is not present in the technology library."""

    def __init__(self, technology: str, available: list[str]) -> None:
        self.technology = technology
        self.available = available
        super().__init__(
            f"Unknown technology {technology!r}. Available: {sorted(available)}"
        )


class InvalidParametersError(TextLayoutError):
    """Raised when DSL parameters fail a generator's typed schema validation."""

    def __init__(self, component: str, detail: str) -> None:
        self.component = component
        self.detail = detail
        super().__init__(f"Invalid parameters for component {component!r}: {detail}")


class ExportError(TextLayoutError):
    """Raised when an exporter cannot render the geometry."""


class UnknownExporterError(TextLayoutError):
    """Raised when a requested export format has no registered exporter."""

    def __init__(self, fmt: str, available: list[str]) -> None:
        self.format = fmt
        self.available = available
        super().__init__(
            f"Unknown export format {fmt!r}. Available: {sorted(available)}"
        )


class MissingResearchError(TextLayoutError):
    """Raised when a component has geometry code but no evidence model."""

    def __init__(self, component: str, available: list[str]) -> None:
        self.component = component
        self.available = available
        super().__init__(
            f"No research model is registered for component {component!r}. "
            f"Evidence-backed components: {sorted(available)}"
        )


class VerificationFailedError(TextLayoutError):
    """Raised when an endpoint requires an artifact but verification failed."""

    def __init__(self, component: str, detail: dict[str, object]) -> None:
        self.component = component
        self.detail = detail
        super().__init__(f"Verification failed for component {component!r}; export was blocked.")
