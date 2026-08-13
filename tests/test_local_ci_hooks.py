from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.run_local_ci import GITLEAKS_VERSION, classify_ci_paths, python_files


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_ci_path_classification_matches_workflow_boundaries():
    assert classify_ci_paths(["server/routes/chat.py"]) == (True, False)
    assert classify_ci_paths(["frontend-react/src/App.tsx"]) == (False, True)
    assert classify_ci_paths(["README.md"]) == (True, True)
    assert classify_ci_paths([".pre-commit-config.yaml"]) == (True, True)
    assert classify_ci_paths(["docs/FASTAPI_README.md"]) == (False, False)


def test_python_files_keep_only_existing_added_or_modified_candidates(monkeypatch):
    with TemporaryDirectory(prefix="local-ci-hook-", dir=REPO_ROOT) as temporary:
        root = Path(temporary)
        monkeypatch.setattr("scripts.run_local_ci.REPO_ROOT", root)
        (root / "server").mkdir()
        (root / "server" / "app.py").write_text("", encoding="utf-8")

        assert python_files(["server/app.py", "server/deleted.py", "README.md"]) == [
            "server/app.py"
        ]


def test_local_runner_pins_ci_gitleaks_version():
    runner = (REPO_ROOT / "scripts" / "run_local_ci.py").read_text(encoding="utf-8")

    assert f'GITLEAKS_VERSION = "{GITLEAKS_VERSION}"' in runner
