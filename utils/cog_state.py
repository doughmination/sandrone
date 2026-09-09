import json
from pathlib import Path

statePath = Path(__file__).parent.parent / "cog_state.json"


def discoverCogHandles(cogsDir: Path) -> list[str]:
    """Every cog under ``cogsDir``, named by its path relative to that dir.

    ``eightball.py`` -> ``"eightball"``; ``fun/eightball.py`` -> ``"fun.eightball"``.
    The handle is what a human types into ``/cog load`` and what gets stored in
    ``cog_state.json``; prefix it with ``commands.cogs.`` to get an import path.
    """
    handles = []
    for path in cogsDir.rglob("*.py"):
        if path.stem == "__init__":
            continue
        relative = path.relative_to(cogsDir).with_suffix("")
        handles.append(".".join(relative.parts))
    return sorted(handles)


def loadDisabled() -> set[str]:
    if not statePath.exists():
        return set()
    try:
        data = json.loads(statePath.read_text())
    except (json.JSONDecodeError, OSError):
        return set()
    return set(data.get("disabled", []))


def saveDisabled(disabled: set[str]) -> None:
    statePath.write_text(json.dumps({"disabled": sorted(disabled)}, indent=2) + "\n")


def setDisabled(name: str, disabled: bool) -> None:
    current = loadDisabled()
    if disabled:
        current.add(name)
    else:
        current.discard(name)
    saveDisabled(current)
