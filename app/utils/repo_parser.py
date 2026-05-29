from dataclasses import dataclass
from urllib.parse import urlparse

from pydantic import HttpUrl


class RepoUrlParseError(ValueError):
    pass


@dataclass
class ParsedRepoUrl:
    owner: str
    repo: str


def parse_repo_url(repo_url: str | HttpUrl) -> ParsedRepoUrl:
    repo_url_str = str(repo_url).strip()
    parsed = urlparse(repo_url_str)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise RepoUrlParseError("only github repository urls are supported")

    path = parsed.path.strip("/")
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        raise RepoUrlParseError("invalid github repository url")

    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        raise RepoUrlParseError("invalid github repository url")

    return ParsedRepoUrl(owner=owner, repo=repo)
