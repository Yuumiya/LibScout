from __future__ import annotations

from pathlib import Path

import pytest
from libscout_scraper.downloader import DownloadResult, RepoDownloadError, download_repo
from libscout_scraper.models import FileRef, RepoRef

# ---------------------------------------------------------------------------
# The repo under test
# ---------------------------------------------------------------------------
OWNER = "WeetHet"
NAME = "holonomy"

# Files we know exist in WeetHet/holonomy (stable across commits)
EXPECTED_FILES: set[str] = {
    "pyproject.toml",
    "README.md",
    ".gitignore",
    "flake.nix",
    "flake.lock",
    "holonomy/__init__.py",
    "holonomy/graph.py",
    "holonomy/curves.py",
    "holonomy/generate/__init__.py",
    "holonomy/generate/model3d.py",
    "holonomy/visualise/graph.py",
    "holonomy/examples/cube.py",
    "holonomy/examples/tetrahedron.py",
    "holonomy/examples/octahedron.py",
    "holonomy/examples/dodecahedron.py",
    "holonomy/examples/square_antiprism.py",
    "holonomy/examples/truncated_tetrahedron.py",
    "holonomy/examples/sin_3_net.py",
}

# We know this repo has exactly 27 files (at the time of writing).
# Use a generous lower bound so the test doesn't break on minor additions.
MIN_FILE_COUNT = 20


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def downloaded_repo(tmp_path_factory: pytest.TempPathFactory) -> DownloadResult:
    """Download WeetHet/holonomy once for the entire test module."""
    dest = tmp_path_factory.mktemp("holonomy-download")
    result = download_repo(OWNER, NAME, dest_dir=dest)
    return result


@pytest.fixture(scope="module")
def repo_ref(downloaded_repo: DownloadResult) -> RepoRef:
    """Build a RepoRef backed by the downloaded local directory."""
    return RepoRef(
        owner=downloaded_repo.owner,
        name=downloaded_repo.name,
        default_branch=downloaded_repo.default_branch,
        local_dir=downloaded_repo.local_dir,
    )


# ---------------------------------------------------------------------------
# download_repo tests
# ---------------------------------------------------------------------------
class TestDownloadRepo:
    """Tests for the ``download_repo`` function against the real GitHub API."""

    def test_returns_download_result(self, downloaded_repo: DownloadResult) -> None:
        assert isinstance(downloaded_repo, DownloadResult)

    def test_owner_and_name(self, downloaded_repo: DownloadResult) -> None:
        assert downloaded_repo.owner == OWNER
        assert downloaded_repo.name == NAME

    def test_default_branch_is_main(self, downloaded_repo: DownloadResult) -> None:
        assert downloaded_repo.default_branch == "main"

    def test_local_dir_exists(self, downloaded_repo: DownloadResult) -> None:
        assert downloaded_repo.local_dir.is_dir()

    def test_local_dir_is_not_empty(self, downloaded_repo: DownloadResult) -> None:
        children = list(downloaded_repo.local_dir.iterdir())
        assert len(children) > 0

    def test_tarball_cleaned_up(self, downloaded_repo: DownloadResult) -> None:
        """The intermediate repo.tar.gz should have been removed after extraction."""
        parent = downloaded_repo.local_dir.parent
        assert not (parent / "repo.tar.gz").exists()

    def test_expected_files_present(self, downloaded_repo: DownloadResult) -> None:
        local = downloaded_repo.local_dir
        for rel in EXPECTED_FILES:
            assert (local / rel).is_file(), f"Expected file missing: {rel}"

    def test_pyproject_toml_content(self, downloaded_repo: DownloadResult) -> None:
        pyproject = downloaded_repo.local_dir / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        assert 'name = "holonomy"' in text
        assert "requires-python" in text

    def test_readme_content(self, downloaded_repo: DownloadResult) -> None:
        readme = downloaded_repo.local_dir / "README.md"
        text = readme.read_text(encoding="utf-8")
        assert "Holonomy" in text

    def test_custom_dest_dir(self, tmp_path: Path) -> None:
        dest = tmp_path / "custom-dest"
        result = download_repo(OWNER, NAME, dest_dir=dest)
        assert result.local_dir.exists()
        assert (result.local_dir / "pyproject.toml").is_file()

    def test_nonexistent_repo_raises(self) -> None:
        with pytest.raises(RepoDownloadError, match="not found"):
            _ = download_repo("WeetHet", "this-repo-does-not-exist-9999")


# ---------------------------------------------------------------------------
# RepoRef.iter_files tests
# ---------------------------------------------------------------------------
class TestRepoRefIterFiles:
    """Tests for ``RepoRef.iter_files()`` backed by a local directory."""

    def test_yields_file_refs(self, repo_ref: RepoRef) -> None:
        files = list(repo_ref.iter_files())
        assert all(isinstance(f, FileRef) for f in files)

    def test_file_count(self, repo_ref: RepoRef) -> None:
        files = list(repo_ref.iter_files())
        assert len(files) >= MIN_FILE_COUNT

    def test_all_paths_are_relative(self, repo_ref: RepoRef) -> None:
        for fref in repo_ref.iter_files():
            assert not fref.path.startswith("/"), f"Path should be relative: {fref.path}"

    def test_expected_paths_included(self, repo_ref: RepoRef) -> None:
        paths = {f.path for f in repo_ref.iter_files()}
        for expected in EXPECTED_FILES:
            assert expected in paths, f"Expected path missing from iter_files: {expected}"

    def test_no_directories_in_results(self, repo_ref: RepoRef) -> None:
        assert repo_ref.local_dir is not None
        for fref in repo_ref.iter_files():
            full = repo_ref.local_dir / fref.path
            assert full.is_file(), f"iter_files yielded a non-file: {fref.path}"

    def test_file_refs_reference_parent_repo(self, repo_ref: RepoRef) -> None:
        files = list(repo_ref.iter_files())
        assert len(files) > 0
        for fref in files:
            assert fref.repo is repo_ref

    def test_empty_repo_ref_yields_nothing(self) -> None:
        """A RepoRef with no local_dir, no driver, and no traverser yields nothing."""
        empty = RepoRef(owner="x", name="y")
        assert list(empty.iter_files()) == []


# ---------------------------------------------------------------------------
# FileRef.fetch_text tests (local filesystem path)
# ---------------------------------------------------------------------------
class TestFileRefFetchText:
    """Tests for ``FileRef.fetch_text()`` reading from the local filesystem."""

    def test_fetch_pyproject_toml(self, repo_ref: RepoRef) -> None:
        fref = FileRef(repo=repo_ref, path="pyproject.toml")
        text = fref.fetch_text()
        assert 'name = "holonomy"' in text

    def test_fetch_readme(self, repo_ref: RepoRef) -> None:
        fref = FileRef(repo=repo_ref, path="README.md")
        text = fref.fetch_text()
        assert "Holonomy" in text

    def test_fetch_python_file(self, repo_ref: RepoRef) -> None:
        fref = FileRef(repo=repo_ref, path="holonomy/__init__.py")
        text = fref.fetch_text()
        # The __init__.py imports from submodules
        assert "import" in text or "def " in text or len(text) > 0

    def test_fetch_nested_python_file(self, repo_ref: RepoRef) -> None:
        fref = FileRef(repo=repo_ref, path="holonomy/examples/cube.py")
        text = fref.fetch_text()
        assert len(text) > 0

    def test_fetch_text_ignores_fetcher_when_local_dir_set(self, repo_ref: RepoRef) -> None:
        """When local_dir is available, the ContentFetcher argument is ignored."""
        call_count = 0

        def spy_fetcher(url: str) -> str:  # pyright: ignore[reportUnusedParameter]
            nonlocal call_count
            call_count += 1
            return "should not be used"

        fref = FileRef(repo=repo_ref, path="pyproject.toml")
        text = fref.fetch_text(fetcher=spy_fetcher)
        assert call_count == 0
        assert 'name = "holonomy"' in text

    def test_fetch_text_raises_without_local_dir_or_fetcher(self) -> None:
        bare_repo = RepoRef(owner=OWNER, name=NAME)
        fref = FileRef(repo=bare_repo, path="pyproject.toml")
        with pytest.raises(ValueError, match="no local_dir"):
            _ = fref.fetch_text()


# ---------------------------------------------------------------------------
# FileRef.raw_url property (still works for backward compat)
# ---------------------------------------------------------------------------
class TestFileRefRawUrl:
    """Ensure ``FileRef.raw_url`` still produces correct URLs."""

    def test_raw_url_uses_default_branch(self, repo_ref: RepoRef) -> None:
        fref = FileRef(repo=repo_ref, path="pyproject.toml")
        expected = f"https://raw.githubusercontent.com/{OWNER}/{NAME}/main/pyproject.toml"
        assert fref.raw_url == expected

    def test_raw_url_uses_sha_when_set(self, repo_ref: RepoRef) -> None:
        fref = FileRef(repo=repo_ref, path="README.md", sha="abc123")
        expected = f"https://raw.githubusercontent.com/{OWNER}/{NAME}/abc123/README.md"
        assert fref.raw_url == expected


# ---------------------------------------------------------------------------
# RepoRef property tests
# ---------------------------------------------------------------------------
class TestRepoRefProperties:
    def test_full_name(self, repo_ref: RepoRef) -> None:
        assert repo_ref.full_name == f"{OWNER}/{NAME}"

    def test_local_dir_set(self, repo_ref: RepoRef) -> None:
        assert repo_ref.local_dir is not None
        assert repo_ref.local_dir.is_dir()

    def test_driver_is_none(self, repo_ref: RepoRef) -> None:
        assert repo_ref.driver is None

    def test_traverser_is_none(self, repo_ref: RepoRef) -> None:
        assert repo_ref.traverser is None
