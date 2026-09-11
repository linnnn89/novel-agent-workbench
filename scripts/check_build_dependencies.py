"""Read-only version check for the pinned Windows build environment."""
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys


def main() -> int:
    requirements = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "requirements-windows-build.txt"
    errors = []
    for line in requirements.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, expected = line.split("==")
        try:
            actual = version(name)
        except PackageNotFoundError:
            actual = "missing"
        if actual != expected:
            errors.append(f"{name}: expected {expected}, found {actual}")
    if errors:
        print("Build dependency mismatch; run the build without -SkipInstall:\n" + "\n".join(errors), file=sys.stderr)
        return 1
    print("Pinned build dependencies verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
