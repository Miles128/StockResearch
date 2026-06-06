"""Local .env read/write for LLM settings."""

from pathlib import Path

from stockresearch.services.env_file import read_env_map, write_env_vars


def test_write_env_vars_updates_and_preserves_comments(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "DATABASE_URL=sqlite:///./test.db\n# comment\nLLM_API_KEY=old\n",
        encoding="utf-8",
    )
    write_env_vars(
        {"LLM_API_KEY": "new-key", "LLM_BASE_URL": "https://api.example.com/v1"},
        path=env,
    )
    data = read_env_map(env)
    assert data["DATABASE_URL"] == "sqlite:///./test.db"
    assert data["LLM_API_KEY"] == "new-key"
    assert data["LLM_BASE_URL"] == "https://api.example.com/v1"
    text = env.read_text(encoding="utf-8")
    assert "# comment" in text
