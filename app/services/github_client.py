import base64
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings


class GithubClientError(Exception):
    def __init__(self, message: str, error_code: str = "GITHUB_API_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class RepositoryNotFoundError(GithubClientError):
    def __init__(self) -> None:
        super().__init__("repository not found", error_code="REPO_NOT_FOUND")


@dataclass
class GithubClient:
    settings: object = field(default_factory=get_settings)
    client: httpx.AsyncClient | None = None
    _owns_client: bool = False

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-repo-checkup",
        }
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        return headers

    async def __aenter__(self) -> "GithubClient":
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=self.settings.request_timeout_seconds,
                headers=self.headers,
            )
            self._owns_client = True
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.client is not None and self._owns_client:
            await self.client.aclose()
            self.client = None
            self._owns_client = False

    async def _get(self, path: str) -> httpx.Response:
        if self.client is None:
            raise GithubClientError("github client is not initialized")
        url = f"{self.settings.github_api_base}{path}"
        try:
            response = await self.client.get(url)
        except httpx.HTTPError as exc:
            raise GithubClientError("failed to connect github api") from exc

        if response.status_code == 404:
            raise RepositoryNotFoundError()
        if response.status_code == 403:
            remaining = response.headers.get("x-ratelimit-remaining")
            if remaining == "0" or "rate limit" in response.text.lower():
                raise GithubClientError(
                    "github api rate limit exceeded, please configure github_token to increase quota",
                    error_code="GITHUB_API_LIMITED",
                )
        if response.status_code >= 400:
            raise GithubClientError(f"github api returned {response.status_code}")
        return response

    async def fetch_repo(self, owner: str, repo: str) -> dict:
        response = await self._get(f"/repos/{owner}/{repo}")
        return response.json()

    async def fetch_languages(self, owner: str, repo: str) -> dict[str, int]:
        response = await self._get(f"/repos/{owner}/{repo}/languages")
        return response.json()

    async def fetch_readme_exists(self, owner: str, repo: str) -> bool:
        try:
            response = await self._get(f"/repos/{owner}/{repo}/readme")
            return response.status_code == 200
        except RepositoryNotFoundError:
            return False
        except GithubClientError:
            return False

    async def fetch_release_exists(self, owner: str, repo: str) -> bool:
        try:
            response = await self._get(f"/repos/{owner}/{repo}/releases?per_page=1")
            releases = response.json()
            return isinstance(releases, list) and len(releases) > 0
        except GithubClientError:
            return False

    async def fetch_branch(self, owner: str, repo: str, branch: str) -> dict:
        response = await self._get(f"/repos/{owner}/{repo}/branches/{branch}")
        return response.json()

    async def fetch_tree(self, owner: str, repo: str, branch: str) -> dict:
        branch_data = await self.fetch_branch(owner, repo, branch)
        tree_sha = branch_data["commit"]["commit"]["tree"]["sha"]
        response = await self._get(f"/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1")
        return response.json()

    async def fetch_file_content(self, owner: str, repo: str, path: str, branch: str) -> dict:
        safe_path = path.strip("/")
        response = await self._get(f"/repos/{owner}/{repo}/contents/{safe_path}?ref={branch}")
        payload = response.json()
        if isinstance(payload, list):
            raise GithubClientError("path points to a directory", error_code="PATH_IS_DIRECTORY")
        if payload.get("encoding") == "base64":
            payload["decoded_content"] = base64.b64decode(payload.get("content", "")).decode("utf-8", errors="replace")
        elif payload.get("download_url"):
            try:
                raw_response = await self.client.get(payload["download_url"])
                raw_response.raise_for_status()
                payload["decoded_content"] = raw_response.text
            except httpx.HTTPError as exc:
                raise GithubClientError("failed to download file content") from exc
        else:
            payload["decoded_content"] = payload.get("content", "")
        return payload
