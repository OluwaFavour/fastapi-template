"""
Project setup script — run once after cloning the template.

Replaces placeholder names throughout the codebase with your project name.
"""

import os
import re
from pathlib import Path

# Files to skip (binary, git, cache, etc.)
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "htmlcov", ".mypy_cache", ".ruff_cache"}
SKIP_EXTENSIONS = {".pyc", ".pyo", ".ico", ".png", ".jpg", ".jpeg", ".gif", ".woff", ".woff2", ".ttf", ".eot"}

# Placeholder values used in the template
PLACEHOLDER_APP_NAME = "FastAPI Template"
PLACEHOLDER_MODULE_NAME = "fastapi_template"
PLACEHOLDER_SLUG = "fastapi-template"
PLACEHOLDER_EXAMPLE_APP = "example_app"


def slugify(name: str) -> str:
    """Convert a human-readable name to a URL slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def to_module_name(name: str) -> str:
    """Convert a human-readable name to a Python module name."""
    module = name.lower().strip()
    module = re.sub(r"[^\w\s]", "", module)
    module = re.sub(r"[\s-]+", "_", module)
    module = re.sub(r"_+", "_", module)
    return module.strip("_")


def replace_in_file(filepath: Path, replacements: list[tuple[str, str]]) -> bool:
    """Replace all occurrences in a file. Returns True if any changes were made."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        return False

    original = content
    for old, new in replacements:
        content = content.replace(old, new)

    if content != original:
        filepath.write_text(content, encoding="utf-8")
        return True
    return False


def rename_directory(root: Path, old_name: str, new_name: str) -> Path | None:
    """Rename a directory if it exists. Returns new path or None."""
    old_path = root / old_name
    new_path = root / new_name
    if old_path.exists() and old_path.is_dir():
        old_path.rename(new_path)
        return new_path
    return None


def main():
    print("=" * 60)
    print("  FastAPI Template — Project Setup")
    print("=" * 60)
    print()

    # Gather inputs
    project_name = input("Project name (human-readable, e.g. 'My Cool API'): ").strip()
    if not project_name:
        print("Error: Project name cannot be empty.")
        return

    slug = slugify(project_name)
    module = to_module_name(project_name)

    print(f"\n  Display name:  {project_name}")
    print(f"  Slug:          {slug}")
    print(f"  Module name:   {module}")

    # Ask about example app
    print()
    example_app_name = input(
        f"First app module name (default: keep '{PLACEHOLDER_EXAMPLE_APP}'): "
    ).strip()
    if example_app_name:
        example_module = to_module_name(example_app_name)
    else:
        example_module = PLACEHOLDER_EXAMPLE_APP

    if example_module != PLACEHOLDER_EXAMPLE_APP:
        print(f"  App module:    {example_module}")

    print()
    confirm = input("Proceed? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    # Build replacement pairs
    replacements: list[tuple[str, str]] = [
        (PLACEHOLDER_APP_NAME, project_name),
        (PLACEHOLDER_SLUG, slug),
    ]
    if example_module != PLACEHOLDER_EXAMPLE_APP:
        replacements.append((PLACEHOLDER_EXAMPLE_APP, example_module))

    # Walk the project and replace in files
    project_root = Path(__file__).parent
    changed_files = 0
    total_files = 0

    for dirpath, dirnames, filenames in os.walk(project_root):
        # Skip unwanted directories
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            filepath = Path(dirpath) / filename

            if filepath.suffix in SKIP_EXTENSIONS:
                continue
            if filepath.name == "setup_project.py":
                continue

            total_files += 1
            if replace_in_file(filepath, replacements):
                changed_files += 1
                print(f"  Updated: {filepath.relative_to(project_root)}")

    # Rename example_app directory if needed
    if example_module != PLACEHOLDER_EXAMPLE_APP:
        example_dir = project_root / "app" / "apps" / PLACEHOLDER_EXAMPLE_APP
        if example_dir.exists():
            new_dir = example_dir.parent / example_module
            example_dir.rename(new_dir)
            print(f"  Renamed: app/apps/{PLACEHOLDER_EXAMPLE_APP} → app/apps/{example_module}")

    print()
    print(f"Done! Updated {changed_files}/{total_files} files.")
    print()
    print("Next steps:")
    print(f"  1. Review the changes: git diff")
    print(f"  2. Update .env with your actual values")
    print(f"  3. Run: python manage.py migrate")
    print(f"  4. Run: python manage.py runserver")
    print(f"  5. Delete this script: rm setup_project.py")


if __name__ == "__main__":
    main()
