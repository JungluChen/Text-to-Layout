from __future__ import annotations

import re
from dataclasses import dataclass, field


DEVICE_PATTERNS: dict[str, list[str]] = {
    "transmon": ["transmon", "qubit"],
    "jpa": ["jpa", "parametric amplifier"],
    "resonator": ["resonator"],
    "squid": ["squid"],
    "twpa": ["twpa", "traveling wave"],
}

PARAMETER_PATTERNS: dict[str, str] = {
    "frequency_ghz": r"(\d+(?:\.\d+)?)\s*ghz\b",
    "coupling_mhz": r"(\d+(?:\.\d+)?)\s*mhz\b",
    "gain_db": r"(\d+(?:\.\d+)?)\s*db\b",
    "bandwidth_mhz": r"(\d+(?:\.\d+)?)\s*mhz\b",
}


@dataclass
class DesignIntent:
    device: str
    parameters: dict[str, float] = field(default_factory=dict)
    technology: str = "unknown"
    process: str = "unknown"

    def to_dict(self) -> dict[str, object]:
        return {
            "device": self.device,
            "parameters": dict(self.parameters),
            "technology": self.technology,
            "process": self.process,
        }


class DesignIntentParser:
    def parse(
        self,
        prompt: str,
        *,
        technology: str = "unknown",
        process: str = "unknown",
    ) -> DesignIntent:
        text = prompt.lower()
        device = "unknown"
        for dev, patterns in DEVICE_PATTERNS.items():
            if any(p in text for p in patterns):
                device = dev
                break

        parameters: dict[str, float] = {}
        for param, pattern in PARAMETER_PATTERNS.items():
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                parameters[param] = float(match.group(1))

        return DesignIntent(
            device=device,
            parameters=parameters,
            technology=technology,
            process=process,
        )
