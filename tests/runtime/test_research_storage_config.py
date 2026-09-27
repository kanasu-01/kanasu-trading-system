from core.config.app_config import AppConfig
from core.config.loaders import load_app_config


def test_research_storage_defaults_are_separate_from_historical_storage():
    config = AppConfig()

    assert config.historical_database_path == "data/historical.sqlite3"
    assert config.research_database_path == "data/research.sqlite3"
    assert config.research_artifact_root == "data/research_artifacts"

    assert len({
        config.historical_database_path,
        config.research_database_path,
        config.research_artifact_root,
    }) == 3


def test_research_storage_loader_uses_approved_defaults(monkeypatch):
    monkeypatch.delenv(
        "RESEARCH_DATABASE_PATH",
        raising=False,
    )
    monkeypatch.delenv(
        "RESEARCH_ARTIFACT_ROOT",
        raising=False,
    )

    config = load_app_config()

    assert config.research_database_path == "data/research.sqlite3"
    assert config.research_artifact_root == "data/research_artifacts"


def test_research_storage_paths_are_overridable(monkeypatch):
    monkeypatch.setenv(
        "RESEARCH_DATABASE_PATH",
        "custom/catalog/research.sqlite3",
    )
    monkeypatch.setenv(
        "RESEARCH_ARTIFACT_ROOT",
        "custom/artifacts",
    )

    config = load_app_config()

    assert config.research_database_path == (
        "custom/catalog/research.sqlite3"
    )
    assert config.research_artifact_root == "custom/artifacts"
