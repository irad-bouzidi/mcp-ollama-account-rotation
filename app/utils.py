import json
from pathlib import Path


def read_json(path: Path) -> dict[str, object] | list[object]:
    with open(path) as f:
        return json.load(f)  # type: ignore[no-any-return]


def atomic_write_json(path: Path, data: dict[str, object] | list[object]) -> None:
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False, suffix=".tmp") as tf:
        json.dump(data, tf, indent=2)
        tmp_path = tf.name
    os.replace(tmp_path, str(path))
