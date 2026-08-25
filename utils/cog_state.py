import json
from pathlib import Path

statePath = Path(__file__).parent.parent / "cog_state.json"


def loadDisabled() -> set[str]:
    if not statePath.exists():
        return set()
    try:
        data = json.loads(statePath.read_text())
    except json.JSONDecodeError, OSError:
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
