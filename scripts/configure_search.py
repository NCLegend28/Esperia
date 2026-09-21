"""Initialize owner-selected local search configuration without printing secrets.

Example: uv run scripts/configure_search.py --image searxng/searxng@sha256:DIGEST
Then docker compose --env-file .local/dev/search/compose.env -f compose.search.yml up -d
The existing secret is retained on rerun. Only development search files are written.
"""

import argparse
import json
import os
import re
import secrets
from pathlib import Path


def configure(
    workspace: Path, image: str, port: int, cpus: float, memory_mb: int
) -> None:
    """Create an isolated dev-service profile and explicit Esperia connection file."""
    if not re.fullmatch(r"[a-zA-Z0-9./_-]+@sha256:[a-f0-9]{64}", image):
        raise ValueError("Use an immutable registry image digest")
    if not 1024 <= port <= 65535 or not 0 < cpus <= 16 or not 128 <= memory_mb <= 16384:
        raise ValueError("Invalid development service resource limits")
    root = workspace.resolve() / ".local/dev/search"
    config = root / "config"
    config.mkdir(parents=True, exist_ok=True)
    settings = config / "settings.yml"
    try:
        descriptor = os.open(settings, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if not settings.is_file() or settings.is_symlink():
            raise ValueError(
                "Existing search settings must be a regular file"
            ) from None
    else:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(
                "use_default_settings: true\nserver:\n"
                f"  secret_key: {json.dumps(secrets.token_urlsafe(48))}\n"
                "  limiter: false\nsearch:\n  formats: [html, json]\n"
            )
    (root / "compose.env").write_text(
        f"ESPERIA_SEARCH_IMAGE={image}\nESPERIA_SEARCH_PORT={port}\n"
        f"ESPERIA_SEARCH_CPUS={cpus}\nESPERIA_SEARCH_MEMORY_MB={memory_mb}\n"
    )
    profile = root / "esperia.json"
    profile.write_text(
        json.dumps(
            {
                "source_search": "tools",
                "search": {"endpoint": f"http://127.0.0.1:{port}/search"},
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Development search configuration ready: {profile}")


def main() -> None:
    """Accept explicit image/port/capacity choices; never pull or start a service."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--image", required=True)
    parser.add_argument("--port", type=int, default=8082)
    parser.add_argument("--cpus", type=float, default=1.0)
    parser.add_argument("--memory-mb", type=int, default=512)
    args = parser.parse_args()
    configure(args.workspace, args.image, args.port, args.cpus, args.memory_mb)


if __name__ == "__main__":
    main()
