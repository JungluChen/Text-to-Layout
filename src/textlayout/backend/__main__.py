"""Run the plugin server: ``python -m textlayout.backend``."""

from __future__ import annotations

from textlayout.backend.settings import Settings


def main() -> None:
    import uvicorn

    settings = Settings.from_env()
    uvicorn.run(
        "textlayout.backend.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
