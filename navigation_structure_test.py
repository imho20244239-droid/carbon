"""Guard against Streamlit's implicit `pages/` multipage discovery.

This project deliberately uses a single Streamlit entry point (`app.py`) plus a
custom Chinese sidebar router. View modules must therefore live under `views/`,
not Streamlit's reserved `pages/` directory.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    forbidden = ROOT / "pages"
    views = ROOT / "views"
    app = (ROOT / "app.py").read_text(encoding="utf-8")

    assert not forbidden.exists(), (
        "Do not create a top-level pages/ directory: Streamlit will auto-register "
        "those files as independent pages and conflict with app.py's custom router."
    )
    assert views.is_dir(), "views/ package is missing"
    assert (views / "__init__.py").exists(), "views/__init__.py is missing"
    assert "from views import" in app, "app.py must import view modules from views/"
    assert "from pages import" not in app, "app.py still imports the reserved pages/ package"

    expected = {
        "overview.py", "dispatch.py", "hourly_view.py", "comparison.py",
        "stress_test.py", "validation.py", "data_notes.py",
    }
    actual = {p.name for p in views.glob("*.py")}
    missing = expected - actual
    assert not missing, f"Missing view modules: {sorted(missing)}"

    print("NAVIGATION STRUCTURE TEST PASSED")
    print("single entry: app.py")
    print("view package: views/")
    print("reserved pages/ directory: absent")


if __name__ == "__main__":
    main()
