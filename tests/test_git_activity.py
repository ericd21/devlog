import subprocess
import time

import pytest

from devlog import git_activity


def _run(args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _run(["git", "init"], cwd=repo_path)
    _run(["git", "config", "user.email", "test@example.com"], cwd=repo_path)
    _run(["git", "config", "user.name", "Test User"], cwd=repo_path)
    return repo_path


def _commit(repo_path, filename, message):
    (repo_path / filename).write_text(message)
    _run(["git", "add", filename], cwd=repo_path)
    _run(["git", "commit", "-m", message], cwd=repo_path)


def test_get_commits_parses_hash_author_date_message(repo):
    _commit(repo, "a.txt", "First commit")

    commits = git_activity.get_commits(str(repo), since="10 years ago")

    assert len(commits) == 1
    commit = commits[0]
    assert len(commit["hash"]) == 40
    assert commit["author"] == "Test User"
    assert commit["message"] == "First commit"
    assert "T" in commit["date"]  # ISO 8601 timestamp


def test_get_commits_returns_newest_first(repo):
    _commit(repo, "a.txt", "First commit")
    _commit(repo, "b.txt", "Second commit")

    commits = git_activity.get_commits(str(repo), since="10 years ago")

    assert [c["message"] for c in commits] == ["Second commit", "First commit"]


def test_get_commits_respects_since_filter(repo):
    _commit(repo, "a.txt", "Old commit")
    time.sleep(2)

    commits = git_activity.get_commits(str(repo), since="1 second ago")

    assert commits == []


def test_get_commits_empty_repo_returns_empty_list(repo):
    commits = git_activity.get_commits(str(repo), since="10 years ago")
    assert commits == []


def test_get_commits_not_a_git_repo_raises(tmp_path):
    not_a_repo = tmp_path / "plain_dir"
    not_a_repo.mkdir()

    with pytest.raises(git_activity.GitActivityError):
        git_activity.get_commits(str(not_a_repo), since="1 week ago")


def test_get_commits_bad_path_raises(tmp_path):
    missing = tmp_path / "does_not_exist"

    with pytest.raises(git_activity.GitActivityError):
        git_activity.get_commits(str(missing), since="1 week ago")
