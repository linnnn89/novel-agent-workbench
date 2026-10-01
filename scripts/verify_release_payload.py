"""Inspect only program files, including compressed Python code, before release."""
import marshal
import re
import sys
import types
import zipfile
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

REPO = Path(__file__).resolve().parents[1]
PRIVATE_PATHS = (str(Path.home()), str(REPO), str(REPO.parent))
MARKERS = tuple(value.lower().encode(encoding) for path in PRIVATE_PATHS
                for value in (path, path.replace("\\", "/"), path.replace("\\", "\\\\"))
                for encoding in ("utf-8", "utf-16le"))
FORBIDDEN = re.compile(r"(^|/)(用户数据|workspace_projects|app_projects|\.git|backups|run_logs|usage_logs)(/|$)|"
                       r"(^|/)(secrets[^/]*|[^/]*\.local\.json|pending_chapter_input\.json|\.env[^/]*)$", re.I)


def inspect(data, label):
    if isinstance(data, types.CodeType):
        inspect(data.co_filename, label)
        for value in data.co_consts: inspect(value, label)
    elif isinstance(data, str):
        inspect(data.encode("utf-8"), label)
    elif isinstance(data, bytes):
        if any(marker in data.lower() for marker in MARKERS):
            raise RuntimeError(f"Private local path detected in {label}")
        if re.search(rb"(?<![A-Za-z0-9_-])(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})(?![A-Za-z0-9_-])", data):
            raise RuntimeError(f"Credential-shaped content detected in {label}")


def main():
    app = Path(sys.argv[1]).resolve()
    exe = app / "NovelAgentWorkbench.exe"
    if not exe.is_file() or not (app / "_internal" / "build_info.json").is_file():
        raise RuntimeError("Missing complete EXE build")
    files = [exe, *(app / "_internal").rglob("*")]
    count = 0
    for file in files:
        if file.is_symlink(): raise RuntimeError("Release payload contains a link")
        if not file.is_file(): continue
        name = file.relative_to(app).as_posix()
        if FORBIDDEN.search(name) or file.suffix.lower() in {".log", ".db", ".sqlite", ".sqlite3", ".nawpkg"}:
            raise RuntimeError(f"Personal/runtime data filename detected: {name}")
        inspect(file.read_bytes(), name)
        # DLLs can contain ZIP signature constants without being archives.
        if file.suffix.lower() == ".zip":
            with zipfile.ZipFile(file) as archive:
                for entry in archive.namelist():
                    if FORBIDDEN.search(entry): raise RuntimeError("Forbidden nested archive entry")
                    data = archive.read(entry)
                    inspect(data, name + "/" + entry)
                    if entry.endswith(".pyc"): inspect(marshal.loads(data[16:]), name + "/" + entry)
        count += 1
    archive = CArchiveReader(str(exe))
    for name, entry in archive.toc.items():
        if entry[-1] == "s": inspect(marshal.loads(archive.extract(name)), name)
        elif entry[-1] == "z":
            pyz = archive.open_embedded_archive(name)
            for module in pyz.toc: inspect(pyz.extract(module), module)
    print(f"PASS: {count} program files and embedded Python code checked; no private paths or forbidden data detected")


if __name__ == "__main__": main()
