"""GitHub Pages Publisher.

Automatically deploys results to GitHub Pages.
Uses VBT_TOKEN environment variable for authentication.
"""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import date
from pathlib import Path

logger = logging.getLogger("ensemble")

# Default directories
PROJECT_DIR = Path(__file__).parent.parent.parent
PAGES_DIR = PROJECT_DIR / "docs"


class GitHubPublisher:
    """GitHub Pages deployment manager."""

    def __init__(
        self,
        repo_dir: Path | str | None = None,
        pages_dir: Path | str | None = None,
        remote: str = "origin",
        branch: str = "master",
        token_env: str = "VBT_TOKEN",
    ):
        """Initialize publisher.

        Args:
            repo_dir: Git repository root directory
            pages_dir: GitHub Pages directory (docs)
            remote: Git remote name
            branch: Branch to deploy to
            token_env: Environment variable name for GitHub token
        """
        self.repo_dir = Path(repo_dir) if repo_dir else PROJECT_DIR
        self.pages_dir = Path(pages_dir) if pages_dir else PAGES_DIR
        self.remote = remote
        self.branch = branch
        self.token_env = token_env

    def _run_git(self, *args, check: bool = True) -> subprocess.CompletedProcess:
        """Run git command."""
        cmd = ["git", "-C", str(self.repo_dir)] + list(args)
        logger.debug(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        if check and result.returncode != 0:
            logger.error(f"Git command failed: {result.stderr}")
            raise RuntimeError(f"Git command failed: {result.stderr}")

        return result

    def is_git_repo(self) -> bool:
        """Check if directory is a git repository."""
        result = self._run_git("rev-parse", "--is-inside-work-tree", check=False)
        return result.returncode == 0

    def has_remote(self) -> bool:
        """Check if remote is configured."""
        result = self._run_git("remote", "get-url", self.remote, check=False)
        return result.returncode == 0

    def get_status(self) -> str:
        """Get git status for pages directory."""
        result = self._run_git("status", "--porcelain", str(self.pages_dir))
        return result.stdout.strip()

    def get_token(self) -> str | None:
        """Get GitHub token from environment."""
        return os.environ.get(self.token_env)

    def setup_remote_with_token(self, repo_url: str) -> bool:
        """Set up remote with token authentication.

        Args:
            repo_url: Repository URL (e.g., github.com/user/repo)

        Returns:
            Success status
        """
        token = self.get_token()
        if not token:
            logger.warning(f"Token not found in {self.token_env}")
            return False

        # Format: https://<token>@github.com/user/repo.git
        if not repo_url.startswith("https://"):
            repo_url = f"https://{repo_url}"
        if not repo_url.endswith(".git"):
            repo_url = f"{repo_url}.git"

        # Insert token into URL
        auth_url = repo_url.replace("https://", f"https://{token}@")

        try:
            # Check if remote exists
            if self.has_remote():
                self._run_git("remote", "set-url", self.remote, auth_url)
            else:
                self._run_git("remote", "add", self.remote, auth_url)

            logger.info(f"Remote configured: {self.remote}")
            return True

        except RuntimeError as e:
            logger.error(f"Failed to set up remote: {e}")
            return False

    def init_repo(self, repo_url: str | None = None) -> bool:
        """Initialize git repository if not exists.

        Args:
            repo_url: Repository URL for remote

        Returns:
            Success status
        """
        if self.is_git_repo():
            logger.info("Git repository already exists")
            return True

        try:
            self._run_git("init")
            logger.info(f"Initialized git repository: {self.repo_dir}")

            if repo_url:
                self.setup_remote_with_token(repo_url)

            return True

        except RuntimeError as e:
            logger.error(f"Failed to initialize repository: {e}")
            return False

    def publish(
        self,
        as_of_date: date | None = None,
        commit_message: str | None = None,
        push: bool = True,
    ) -> bool:
        """Publish to GitHub Pages.

        Args:
            as_of_date: Date of results
            commit_message: Commit message (auto-generated if None)
            push: Whether to push to remote

        Returns:
            Success status
        """
        if not self.is_git_repo():
            logger.warning("Not a git repository. Skipping deployment.")
            return False

        if not self.pages_dir.exists():
            logger.warning(f"Pages directory not found: {self.pages_dir}")
            return False

        # Check for changes
        status = self.get_status()
        if not status:
            logger.info("No changes to deploy.")
            return True

        logger.info(f"Changed files:\n{status}")

        # Generate commit message
        if commit_message is None:
            if as_of_date is None:
                as_of_date = date.today()
            date_str = as_of_date.strftime("%Y-%m-%d")
            commit_message = f"Update results for {date_str}"

        try:
            # Stage docs folder
            self._run_git("add", str(self.pages_dir))

            # Commit
            self._run_git("commit", "-m", commit_message)
            logger.info(f"Committed: {commit_message}")

            # Push
            if push:
                if not self.has_remote():
                    logger.warning(f"Remote '{self.remote}' not configured. Skipping push.")
                    return True

                self._run_git("push", self.remote, self.branch)
                logger.info(f"Pushed to: {self.remote}/{self.branch}")

            return True

        except RuntimeError as e:
            logger.error(f"Deployment failed: {e}")
            return False

    def setup_pages_dir(self) -> None:
        """Set up GitHub Pages directory."""
        self.pages_dir.mkdir(parents=True, exist_ok=True)

        # Create .nojekyll file
        nojekyll = self.pages_dir / ".nojekyll"
        if not nojekyll.exists():
            nojekyll.touch()
            logger.info(f"Created .nojekyll: {nojekyll}")

        # Create README
        readme = self.pages_dir / "README.md"
        if not readme.exists():
            readme.write_text(
                "# Deep-Ensemble Stock Scanner Results\n\n"
                "This directory contains auto-generated results for GitHub Pages.\n\n"
                "## Models Used\n"
                "- Chronos-Bolt (Amazon)\n"
                "- TTM (IBM)\n"
                "- Moirai (Salesforce)\n",
                encoding="utf-8"
            )
            logger.info(f"Created README.md: {readme}")


def publish_to_github_pages(
    as_of_date: date | None = None,
    commit_message: str | None = None,
    push: bool = True,
    repo_dir: Path | str | None = None,
    repo_url: str | None = None,
) -> bool:
    """Publish to GitHub Pages (convenience function).

    Args:
        as_of_date: Date of results
        commit_message: Commit message
        push: Whether to push to remote
        repo_dir: Git repository directory
        repo_url: Repository URL (for initial setup)

    Returns:
        Success status
    """
    publisher = GitHubPublisher(repo_dir=repo_dir)

    # Initialize if needed
    if not publisher.is_git_repo():
        if repo_url:
            publisher.init_repo(repo_url)
        else:
            logger.warning("Not a git repository and no repo_url provided")
            return False

    publisher.setup_pages_dir()
    return publisher.publish(as_of_date, commit_message, push)
