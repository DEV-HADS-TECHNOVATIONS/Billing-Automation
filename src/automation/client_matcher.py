from __future__ import annotations

import json
import re
from pathlib import Path

from .errors import ClientMatchError
from .settings import PROJECT_ROOT, resolve_project_path


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def load_clients(path: str | Path = "./config/clients.json") -> list[dict]:
    file_path = resolve_project_path(path)
    if not file_path.is_file():
        raise ClientMatchError(f"Client configuration not found: {file_path}")
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ClientMatchError(f"Cannot read clients JSON: {exc}") from exc

    if isinstance(data, list):
        clients = data
    elif isinstance(data, dict) and isinstance(data.get("clients"), list):
        clients = data["clients"]
    elif isinstance(data, dict):
        clients = [
            ({"name": key, **value} if isinstance(value, dict) else {"name": key})
            for key, value in data.items()
        ]
    else:
        raise ClientMatchError("clients.json must contain a list or client dictionary.")

    valid = [c for c in clients if isinstance(c, dict) and c.get("name")]
    if not valid:
        raise ClientMatchError("No valid client records were found in clients.json.")
    return valid


def identify_client(excel_filename: str,
                    clients_path: str | Path = "./config/clients.json") -> dict:
    """Match filename using configured filename_keywords/keywords or client name.

    Add optional JSON property filename_keywords for ambiguous or unusual names.
    """
    filename = _normalise(Path(excel_filename).stem)
    clients = load_clients(clients_path)
    matches: list[tuple[int, dict]] = []

    for client in clients:
        raw_keywords = client.get("filename_keywords") or client.get("keywords") or []
        if isinstance(raw_keywords, str):
            raw_keywords = [raw_keywords]

        name = str(client["name"])
        # Use the full name and its first distinctive token as basic aliases.
        words = _normalise(name).split()
        aliases = [name]
        if words:
            aliases.append(words[0])
        aliases.extend(str(x) for x in raw_keywords)

        matched_aliases = []
        for alias in aliases:
            key = _normalise(alias)
            if not key:
                continue
            if re.search(r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])", filename):
                matched_aliases.append(key)

        if matched_aliases:
            matches.append((max(map(len, matched_aliases)), client))

    if not matches:
        raise ClientMatchError(f"No client matched Excel filename: {excel_filename}")

    highest_score = max(score for score, _ in matches)
    best = [client for score, client in matches if score == highest_score]
    # If more than one client is matched, fail closed rather than selecting arbitrarily.
    unique_names = {str(c["name"]).casefold() for c in best}
    if len(unique_names) != 1:
        raise ClientMatchError(
            f"Ambiguous client match for '{excel_filename}': "
            + ", ".join(sorted(unique_names))
        )
    return best[0]
