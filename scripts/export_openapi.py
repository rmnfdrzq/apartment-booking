"""Export OpenAPI specification to docs/openapi.json and docs/openapi.yaml."""

import json
import sys
from pathlib import Path

# Add project root to sys.path so app can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from app.main import app


def export_openapi() -> tuple[Path, Path]:
    """Generate and write the OpenAPI JSON and YAML files to docs/."""
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    schema = app.openapi()

    json_path = docs_dir / "openapi.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)

    yaml_path = docs_dir / "openapi.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(schema, f, sort_keys=False, allow_unicode=True)

    return json_path, yaml_path


if __name__ == "__main__":
    j, y = export_openapi()
    print(f"Successfully exported OpenAPI specification to:\n  - {j}\n  - {y}")
