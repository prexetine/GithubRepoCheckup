import asyncio

from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.models.schemas import (
    AIAnalyzeRequest,
    AIReportResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    ErrorResponse,
    ExamplesResponse,
    HealthResponse,
    RepoFileResponse,
    RepoTreeResponse,
)
from app.services.ai_report import build_ai_report
from app.services.analyzer import build_analysis_payload
from app.services.github_client import GithubClient, GithubClientError, RepositoryNotFoundError
from app.services.repo_browser import build_repo_file_payload, build_repo_tree_payload
from app.utils.repo_parser import RepoUrlParseError, parse_repo_url
from app.utils.ttl_cache import TTLCache


router = APIRouter(tags=["repo-checkup"])
settings = get_settings()
analyze_cache: TTLCache[AnalyzeResponse] = TTLCache(ttl_seconds=settings.cache_ttl_seconds)
tree_cache: TTLCache[RepoTreeResponse] = TTLCache(ttl_seconds=settings.cache_ttl_seconds)
file_cache: TTLCache[RepoFileResponse] = TTLCache(ttl_seconds=settings.cache_ttl_seconds)
repo_data_cache: TTLCache[dict] = TTLCache(ttl_seconds=settings.cache_ttl_seconds)
repo_tree_data_cache: TTLCache[dict] = TTLCache(ttl_seconds=settings.cache_ttl_seconds)

EXAMPLE_REPOS = [
    "https://github.com/vercel/next.js",
    "https://github.com/facebook/react",
    "https://github.com/microsoft/vscode",
]


def _repo_key(owner: str, repo: str) -> str:
    return f"{owner}/{repo}".lower()


async def _get_repo_data(github_client: GithubClient, owner: str, repo: str) -> dict:
    cache_key = _repo_key(owner, repo)
    cached = repo_data_cache.get(cache_key)
    if cached is not None:
        return cached

    repo_data = await github_client.fetch_repo(owner, repo)
    repo_data_cache.set(cache_key, repo_data)
    return repo_data


async def _get_repo_tree_data(github_client: GithubClient, owner: str, repo: str, default_branch: str) -> dict:
    cache_key = f"{_repo_key(owner, repo)}::{default_branch}"
    cached = repo_tree_data_cache.get(cache_key)
    if cached is not None:
        return cached

    tree_data = await github_client.fetch_tree(owner, repo, default_branch)
    repo_tree_data_cache.set(cache_key, tree_data)
    return tree_data


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        success=True,
        message="ok",
        data={"status": "running"},
    )


@router.get("/examples", response_model=ExamplesResponse)
async def examples() -> ExamplesResponse:
    return ExamplesResponse(success=True, message="ok", data=EXAMPLE_REPOS)


@router.post(
    "/analyze/ai",
    response_model=AIReportResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def analyze_ai(payload: AIAnalyzeRequest) -> AIReportResponse:
    report = await build_ai_report(
        enable_ai=True,
        repo=payload.repo,
        score=payload.score,
        health=payload.health,
        metrics=payload.metrics,
    )
    return AIReportResponse(
        success=True,
        message="ai analyze success",
        data=report,
    )


@router.get(
    "/repo/tree",
    response_model=RepoTreeResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def repo_tree(repoUrl: str) -> RepoTreeResponse:
    cached = tree_cache.get(repoUrl)
    if cached is not None:
        return cached

    try:
        parsed = parse_repo_url(repoUrl)
    except RepoUrlParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                success=False,
                message=str(exc),
                errorCode="INVALID_GITHUB_REPO_URL",
                data=None,
            ).model_dump(),
        ) from exc

    try:
        async with GithubClient() as github_client:
            repo_data = await _get_repo_data(github_client, parsed.owner, parsed.repo)
            tree_data = await _get_repo_tree_data(
                github_client,
                parsed.owner,
                parsed.repo,
                repo_data["default_branch"],
            )
    except RepositoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                success=False,
                message="repository not found",
                errorCode="REPO_NOT_FOUND",
                data=None,
            ).model_dump(),
        ) from exc
    except GithubClientError as exc:
        status_code = status.HTTP_429_TOO_MANY_REQUESTS if exc.error_code == "GITHUB_API_LIMITED" else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status_code,
            detail=ErrorResponse(
                success=False,
                message=exc.message,
                errorCode=exc.error_code,
                data=None,
            ).model_dump(),
        ) from exc

    response = RepoTreeResponse(
        success=True,
        message="repo tree success",
        data=build_repo_tree_payload(repo_data, tree_data),
    )
    tree_cache.set(repoUrl, response)
    return response


@router.get(
    "/repo/file",
    response_model=RepoFileResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def repo_file(repoUrl: str, path: str) -> RepoFileResponse:
    cache_key = f"{repoUrl}::{path.strip()}"
    cached = file_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        parsed = parse_repo_url(repoUrl)
    except RepoUrlParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                success=False,
                message=str(exc),
                errorCode="INVALID_GITHUB_REPO_URL",
                data=None,
            ).model_dump(),
        ) from exc

    if not path.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                success=False,
                message="file path is required",
                errorCode="FILE_PATH_REQUIRED",
                data=None,
            ).model_dump(),
        )

    try:
        async with GithubClient() as github_client:
            repo_data = await _get_repo_data(github_client, parsed.owner, parsed.repo)
            file_data = await github_client.fetch_file_content(
                parsed.owner,
                parsed.repo,
                path,
                repo_data["default_branch"],
            )
    except RepositoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                success=False,
                message="repository or file not found",
                errorCode="REPO_OR_FILE_NOT_FOUND",
                data=None,
            ).model_dump(),
        ) from exc
    except GithubClientError as exc:
        status_code = status.HTTP_429_TOO_MANY_REQUESTS if exc.error_code == "GITHUB_API_LIMITED" else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status_code,
            detail=ErrorResponse(
                success=False,
                message=exc.message,
                errorCode=exc.error_code,
                data=None,
            ).model_dump(),
        ) from exc

    response = RepoFileResponse(
        success=True,
        message="repo file success",
        data=build_repo_file_payload(repo_data, file_data),
    )
    file_cache.set(cache_key, response)
    return response


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def analyze_repo(payload: AnalyzeRequest) -> AnalyzeResponse:
    cache_key = f"{payload.repoUrl}::{payload.enableAI}"
    cached = analyze_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        parsed = parse_repo_url(payload.repoUrl)
    except RepoUrlParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                success=False,
                message=str(exc),
                errorCode="INVALID_GITHUB_REPO_URL",
                data=None,
            ).model_dump(),
        ) from exc

    try:
        async with GithubClient() as github_client:
            repo_data_task = _get_repo_data(github_client, parsed.owner, parsed.repo)
            repo_data, language_data, readme_exists, release_exists = await asyncio.gather(
                repo_data_task,
                github_client.fetch_languages(parsed.owner, parsed.repo),
                github_client.fetch_readme_exists(parsed.owner, parsed.repo),
                github_client.fetch_release_exists(parsed.owner, parsed.repo),
            )
    except RepositoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                success=False,
                message="repository not found",
                errorCode="REPO_NOT_FOUND",
                data=None,
            ).model_dump(),
        ) from exc
    except GithubClientError as exc:
        status_code = status.HTTP_429_TOO_MANY_REQUESTS if exc.error_code == "GITHUB_API_LIMITED" else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status_code,
            detail=ErrorResponse(
                success=False,
                message=exc.message,
                errorCode=exc.error_code,
                data=None,
            ).model_dump(),
        ) from exc

    result = build_analysis_payload(
        repo_data=repo_data,
        language_data=language_data,
        readme_exists=readme_exists,
        release_exists=release_exists,
    )
    result.aiReport = await build_ai_report(
        enable_ai=payload.enableAI,
        repo=result.repo,
        score=result.score,
        health=result.health,
        metrics=result.metrics,
    )

    response = AnalyzeResponse(success=True, message="analyze success", data=result)
    analyze_cache.set(cache_key, response)
    return response
