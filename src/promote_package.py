"""Promote community libraries (packages) from awesome-*-creations repos."""
import logging
import os
import json
import re
from atproto import client_utils

import requests
from helper.login_mastodon import login_mastodon
from helper.login_bluesky import login_bluesky

import config


class PromotePackage():
    """
    Cycle through package metadata and promote one library per run.

    Skips packages that have already been promoted at the same version.
    Re-promotes when a newer version is detected (PyPI version for PyLadies
    packages; ``last_updated`` timestamp for RLadies packages).
    """

    def __init__(self, config_dict=None, no_dry_run=True):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

        self.no_dry_run = no_dry_run
        self.config_dict = config_dict

    def get_config(self):
        """Load configuration from environment or provided dict."""
        if (self.config_dict is None) and (self.no_dry_run):
            self.config_dict = {
                "platform": os.getenv("PLATFORM"),
                "counter": self._ensure_metadata_prefix(
                    os.getenv("COUNTER", "")
                ),
                "password": os.getenv("PASSWORD"),
                "username": os.getenv("USERNAME"),
                "client_name": os.getenv("CLIENT_NAME"),
                "json_file": self._ensure_metadata_prefix(
                    os.getenv("JSON_FILE", "")
                ),
                "archive_file": self._ensure_metadata_prefix(
                    os.getenv("ARCHIVE_FILE", "")
                ),
            }
            if self.config_dict["platform"] == "mastodon":
                self.config_dict["api_base_url"] = config.API_BASE_URL
                self.config_dict["mastodon_visibility"] = (
                    config.MASTODON_VISIBILITY
                )
                self.config_dict["client_id"] = os.getenv("CLIENT_ID")
                self.config_dict["client_secret"] = os.getenv("CLIENT_SECRET")
                self.config_dict["access_token"] = os.getenv("ACCESS_TOKEN")
                self.config_dict["client_cred_file"] = os.getenv(
                    "BOT_CLIENTCRED_SECRET"
                )
            else:
                self.config_dict["api_base_url"] = "bluesky"
        else:
            if self.config_dict:
                self.config_dict["json_file"] = self._ensure_metadata_prefix(
                    self.config_dict.get("json_file", "")
                )
                self.config_dict["counter"] = self._ensure_metadata_prefix(
                    self.config_dict.get("counter", "")
                )
                self.config_dict["archive_file"] = self._ensure_metadata_prefix(
                    self.config_dict.get("archive_file", "")
                )

    @staticmethod
    def _ensure_metadata_prefix(value: str, prefix: str = "metadata/") -> str:
        if not value:
            return value
        # Check whether the path already contains 'metadata' as a proper segment
        # (e.g. "metadata/file.txt" or "../metadata/file.txt"), not just as a
        # substring (e.g. "my-metadata/file.txt" would previously be a false positive).
        segments = value.replace("\\", "/").split("/")
        if prefix.rstrip("/") in segments:
            return value
        return prefix + value

    def promote_package(self):
        """Core method: read metadata, pick next library, post about it."""
        self.get_config()

        client_name = self.config_dict.get("client_name", "unknown")
        self.logger.info("Initializing %s Bot", client_name)
        self.logger.info("=" * (len(client_name) + 17))
        self.logger.info(
            " > Connecting to %s",
            self.config_dict.get("api_base_url", "")
        )

        if self.no_dry_run:
            if self.config_dict["platform"] == "mastodon":
                _, client = login_mastodon(self.config_dict)
            elif self.config_dict["platform"] == "bluesky":
                client = login_bluesky(self.config_dict)
            else:
                client = None
        else:
            client = None

        packages = self.read_metadata_json()
        if not packages:
            self.logger.info("No packages found in metadata — nothing to do.")
            return

        counter_name = self.read_counter_name()
        self.process_packages(packages, counter_name, client)

    def process_packages(self, packages, counter_name, client):
        """Find the next package to promote and post it.

        Starting from the package after ``counter_name``, iterates through the
        full list (wrapping around) until it finds one that is due for promotion.
        A package is skipped when:
          - Its version is known and matches the archived version (version-tracked).
          - Its version cannot be determined but it has been promoted before
            (no-version sentinel: archived value is "").
        If every package is already up-to-date, nothing is posted and the
        counter is left unchanged.
        """
        n = len(packages)

        start_index = 0
        for i, pkg in enumerate(packages):
            if pkg.get("name") == counter_name:
                start_index = i
                break

        archive = self.read_archive()

        for offset in range(1, n + 1):
            candidate_index = (start_index + offset) % n
            package = packages[candidate_index]
            package_name = package.get("name", "unknown")

            self.logger.info("Considering package: %s", package_name)

            current_version = self.get_current_version(package)
            archived_value = archive.get(package_name)  # None = not yet promoted

            # Decide whether to skip this package.
            # Case A: version is deterministic and unchanged.
            if current_version is not None and current_version == archived_value:
                self.logger.info(
                    "Skipping %s — already promoted at version %s.",
                    package_name,
                    current_version,
                )
                continue
            # Case B: version cannot be determined but package was promoted before
            # (sentinel "" stored in archive to signal "promoted, no version info").
            if current_version is None and archived_value is not None:
                self.logger.info(
                    "Skipping %s — already promoted (no version info available).",
                    package_name,
                )
                continue

            # ── Found a package to promote ──────────────────────────────────
            self.logger.info("Promoting package: %s", package_name)
            if current_version:
                self.logger.info("  Version: %s", current_version)

            if self.no_dry_run:
                result = self.send_post(package, client)
                if result == "success":
                    self.logger.info(
                        "Successfully promoted %s.", package_name
                    )
                    # Store version string, or "" as a sentinel when unavailable.
                    archive[package_name] = (
                        current_version if current_version is not None else ""
                    )
                    self.write_archive(archive)
                else:
                    self.logger.warning(
                        "Post failed for %s.", package_name
                    )
            else:
                # Show the formatted post text in dry-run mode
                platform = self.config_dict.get("platform", "")
                if platform == "mastodon":
                    post_text = self.build_post_mastodon(package)
                elif platform == "bluesky":
                    post_text = self.build_post_bluesky(package).build_text()
                else:
                    post_text = ""

                self.logger.info(
                    "[DRY RUN] Would promote: %s (%s)\n%s",
                    package_name,
                    package.get("repo_url", ""),
                    post_text,
                )

            self.update_counter(package_name)
            return

        # All packages are already up-to-date — nothing to post this run.
        self.logger.info(
            "All packages already promoted at their current version — nothing to post."
        )

    # ------------------------------------------------------------------
    # Archive helpers
    # ------------------------------------------------------------------

    def read_archive(self) -> dict:
        """Read the promotion archive. Returns {} if not found."""
        archive_file = self.config_dict.get("archive_file", "")
        if not archive_file:
            self.logger.warning(
                "ARCHIVE_FILE not configured — version tracking disabled. "
                "Packages may be re-promoted every cycle."
            )
            return {}
        try:
            with open(archive_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def write_archive(self, archive: dict):
        """Persist the promotion archive."""
        archive_file = self.config_dict.get("archive_file", "")
        if not archive_file:
            return
        with open(archive_file, "w", encoding="utf-8") as f:
            json.dump(archive, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Version helpers
    # ------------------------------------------------------------------

    def get_pypi_version(self, pypi_url: str) -> str | None:
        """Fetch the latest version of a package from the PyPI JSON API."""
        if not pypi_url:
            return None
        # Extract the package name from the canonical PyPI URL pattern
        # "/project/<name>/", guarding against version segments like "/project/foo/1.0/".
        match = re.search(r"/project/([^/]+)", pypi_url)
        package_name = match.group(1) if match else pypi_url.rstrip("/").split("/")[-1]
        url = f"https://pypi.org/pypi/{package_name}/json"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json().get("info", {}).get("version")
        except requests.RequestException as e:
            self.logger.info("Could not fetch PyPI version for %s: %s", package_name, e)
        return None

    def get_current_version(self, package: dict) -> str | None:
        """
        Return the current version string for a package.

        - PyLadies packages: latest version from PyPI (via pypi_url).
        - RLadies packages: last_updated timestamp from metadata.
        """
        client_name = self.config_dict.get("client_name", "")
        if client_name == "pyladies_bot":
            return self.get_pypi_version(package.get("pypi_url", ""))
        if client_name == "rladies_bot":
            last_updated = package.get("last_updated", "")
            return last_updated if last_updated else None
        return None

    # ------------------------------------------------------------------
    # Counter helpers
    # ------------------------------------------------------------------

    def update_counter(self, counter_name):
        """Write the name of the just-promoted library to the counter file."""
        with open(
            self.config_dict["counter"], "w", encoding="utf-8"
        ) as txt_file:
            txt_file.write(counter_name)

    def read_counter_name(self) -> str:
        """Read the last-promoted library name from the counter file."""
        try:
            with open(
                self.config_dict["counter"], "r", encoding="utf-8"
            ) as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""

    def read_metadata_json(self) -> list[dict]:
        """Read package metadata JSON. Returns [] if the file doesn't exist yet."""
        try:
            with open(self.config_dict["json_file"], "rb") as fp:
                self.logger.info("=============================================")
                packages = json.load(fp)
                self.logger.info("Package meta data successfully loaded.")
                self.logger.info("=============================================")
                return packages
        except FileNotFoundError:
            self.logger.warning(
                "Metadata file %s not found — run the packages data workflow first.",
                self.config_dict["json_file"],
            )
            return []

    def define_tags(self) -> str:
        """Return community-specific hashtags."""
        client_name = self.config_dict.get("client_name", "")
        if client_name == "pyladies_bot":
            return "#pyladies #python #opensource "
        if client_name == "rladies_bot":
            return "#rladies #rstats #opensource "
        return "#opensource "

    def get_bluesky_did(self, handle: str):
        """Resolve a Bluesky handle to a DID."""
        url = (
            f"https://bsky.social/xrpc/com.atproto.identity.resolveHandle?"
            f"handle={handle.lstrip('@')}"
        )
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json().get("did")
        except requests.RequestException as e:
            self.logger.info("Could not resolve Bluesky DID: %s", e)
        return None

    @staticmethod
    def _check_handle(handle: str) -> str:
        if handle and len(handle) > 1 and not handle.startswith("@"):
            return f"@{handle}"
        return handle

    def build_post_mastodon(self, package: dict) -> str:
        """Build a Mastodon post for the given package."""
        name = package.get("name", "")
        description = package.get("description", "")
        repo_url = package.get("repo_url", "")
        maintainer_name = package.get("maintainer_name", "")
        mastodon_handle = self._check_handle(package.get("mastodon", ""))
        tags = self.define_tags()

        post = f'📦 {name}\n\n'
        if description:
            post += f"{description}\n\n"

        if maintainer_name:
            post += f"👤 {maintainer_name}"
            if mastodon_handle:
                post += f" ({mastodon_handle})"
            post += "\n\n"

        post += f"🔗 {repo_url}\n\n{tags}"

        self.logger.info("*****************************")
        self.logger.info(post)
        self.logger.info("*****************************")

        return post

    def build_post_bluesky(self, package: dict):
        """Build a Bluesky TextBuilder post for the given package."""
        bluesky_max_graphemes = 300
        name = package.get("name", "")
        description = package.get("description", "")
        repo_url = package.get("repo_url", "")
        maintainer_name = package.get("maintainer_name", "")
        bluesky_handle = self._check_handle(package.get("bluesky", ""))
        tags = self.define_tags()
        tag_list = [t.strip() for t in tags.split("#") if t.strip()]

        did = (
            self.get_bluesky_did(bluesky_handle) if bluesky_handle else None
        )

        def _build(tag_subset):
            tb = client_utils.TextBuilder()
            tb.text(f"📦 {name}\n\n")
            if description:
                tb.text(description)
                tb.text("\n\n")
            if maintainer_name:
                tb.text(f"👤 {maintainer_name}")
                if bluesky_handle and did:
                    tb.mention(f" ({bluesky_handle})", did)
                elif bluesky_handle:
                    tb.text(f" ({bluesky_handle})")
                tb.text("\n\n")
            tb.text("🔗 ")
            tb.link(repo_url, repo_url)
            tb.text("\n\n")
            for tag_clean in tag_subset:
                tb.tag(f"#{tag_clean} ", tag_clean)
            return tb

        for count in range(len(tag_list), -1, -1):
            text_builder = _build(tag_list[:count])
            if len(text_builder.build_text()) <= bluesky_max_graphemes:
                return text_builder

        return _build([])

    def send_post(self, package: dict, client) -> str:
        """Build and send the post for a package."""
        self.logger.info(
            "Preparing post on %s (%s) ...",
            self.config_dict["client_name"],
            self.config_dict["platform"],
        )

        platform = self.config_dict.get("platform", "")

        if platform == "mastodon":
            post_txt = self.build_post_mastodon(package)
            try:
                client.status_post(post_txt)
                self.logger.info("Posted 🎉")
                return "success"
            except Exception as e:
                self.logger.exception("Post failed: %s", e)
                return "failed"

        if platform == "bluesky":
            post_txt = self.build_post_bluesky(package)
            try:
                client.send_post(text=post_txt)
                self.logger.info("Posted 🎉")
                return "success"
            except Exception as e:
                self.logger.exception("Post failed: %s", e)
                return "failed"

        return "failed"


if __name__ == "__main__":
    promote_package_handler = PromotePackage(
        config_dict=None, no_dry_run=True
    )
    promote_package_handler.promote_package()
