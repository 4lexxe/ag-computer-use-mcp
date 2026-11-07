"""Build distributable artifacts from an explicit source allowlist."""

import hashlib
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "pyproject.toml",
    "MANIFEST.in",
    "requirements.txt",
    ".gitignore",
    "windows_computer_use_mcp.py",
    "overlay.py",
)
DIRECTORIES = ("src", "tests", "docs", "examples", "scripts", ".github")
FORBIDDEN = {".local", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
RUNTIME_FILES = {"overlay_status.txt", "overlay_status.json", ".env"}
PUBLIC_MEDIA = {
    "docs/media/antigravity-in-action.gif",
    "docs/media/antigravity-in-action.mp4",
    "docs/media/usage-poster.png",
    "docs/media/overlay-preview.gif",
}


def source_files(root=ROOT):
    for name in ROOT_FILES:
        yield root / name
    for directory in DIRECTORIES:
        for path in sorted((root / directory).rglob("*")):
            relative = path.relative_to(root)
            if (
                path.is_file()
                and not path.is_symlink()
                and not any(
                    part in FORBIDDEN or part.endswith(".egg-info") for part in relative.parts
                )
                and path.name not in RUNTIME_FILES
                and (
                    path.suffix in {".py", ".md", ".json", ".yml", ".svg"}
                    or relative.as_posix() in PUBLIC_MEDIA
                )
            ):
                yield path


def verify_members(names):
    for name in names:
        path = Path(name)
        if (
            any(part in FORBIDDEN for part in path.parts)
            or path.name in RUNTIME_FILES
            or path.suffix.lower() in {".jpg", ".jpeg", ".pyc"}
        ):
            raise RuntimeError(f"Local runtime/private file in distribution: {name}")


def main():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    subprocess.run([sys.executable, "-m", "build", "--outdir", str(output)], cwd=ROOT, check=True)
    wheel = output / f"windows_computer_use_mcp-{version}-py3-none-any.whl"
    sdist = output / f"windows_computer_use_mcp-{version}.tar.gz"
    prefix = f"windows-computer-use-mcp-{version}"
    source_zip = output / f"{prefix}-source.zip"
    with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in source_files():
            archive.write(path, f"{prefix}/{path.relative_to(ROOT).as_posix()}")
    for path in (wheel, source_zip):
        with zipfile.ZipFile(path) as archive:
            verify_members(archive.namelist())
    with tarfile.open(sdist) as archive:
        verify_members(archive.getnames())
    artifacts = (wheel, sdist, source_zip)
    hashes = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in artifacts]
    (output / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    for path in artifacts:
        print(f"Built {path.name} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
