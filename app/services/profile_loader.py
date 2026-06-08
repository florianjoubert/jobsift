"""Load the candidate profile/CV from profile.md (gitignored)."""

from pathlib import Path

_DEFAULT = Path("profile.md")


def load_profile(path: Path | str = _DEFAULT) -> str:
    """Read the candidate profile file.

    Returns:
        File contents as a UTF-8 string, or an empty string if the file does not exist.
    """
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""
