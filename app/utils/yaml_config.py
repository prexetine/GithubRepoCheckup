from pathlib import Path


def load_simple_yaml(path: str) -> dict[str, str]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"config file not found: {file_path}")

    data: dict[str, str] = {}
    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data

