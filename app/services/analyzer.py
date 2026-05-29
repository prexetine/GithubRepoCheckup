from datetime import UTC, datetime

from app.models.schemas import (
    AIReport,
    AnalyzeResult,
    Charts,
    Health,
    HealthDimension,
    LanguageChartItem,
    Metrics,
    OverviewChartItem,
    RadarChartItem,
    RepoInfo,
    Score,
)


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _days_since(value: str) -> int:
    dt = _parse_iso_datetime(value)
    now = datetime.now(UTC)
    delta = now - dt
    return max(delta.days, 0)


def _repo_age_days(created_at: str) -> int:
    return _days_since(created_at)


def _safe_ratio(left: int, right: int) -> float:
    if right <= 0:
        return float(left) if left > 0 else 0.0
    return round(left / right, 2)


def _language_chart(language_data: dict[str, int]) -> list[LanguageChartItem]:
    total = sum(language_data.values())
    if total <= 0:
        return []

    sorted_items = sorted(language_data.items(), key=lambda item: item[1], reverse=True)
    chart_items = []
    for name, value in sorted_items[:5]:
        percent = round((value / total) * 100, 1)
        chart_items.append(LanguageChartItem(name=name, value=value, percent=percent))
    return chart_items


def _label_from_ratio(score: int, max_score: int) -> str:
    ratio = score / max_score if max_score else 0
    if ratio >= 0.85:
        return "high"
    if ratio >= 0.65:
        return "good"
    if ratio >= 0.4:
        return "medium"
    return "low"


def _level_from_total(total: int) -> str:
    if total >= 85:
        return "优秀"
    if total >= 70:
        return "良好"
    if total >= 50:
        return "一般"
    return "风险较高"


def _build_popularity(stars: int, forks: int, watchers: int) -> HealthDimension:
    score = min(30, int(stars / 5000) + int(forks / 2500) + int(watchers / 500))
    label = _label_from_ratio(score, 30)
    summary = {
        "high": "仓库社区关注度较高",
        "good": "仓库具备较好的社区关注度",
        "medium": "仓库有一定社区关注，但热度中等",
        "low": "仓库热度较低，社区关注度有限",
    }[label]
    return HealthDimension(score=score, label=label, summary=summary)


def _build_activity(days_since_update: int, days_since_push: int) -> HealthDimension:
    score = 0
    if days_since_update <= 7:
        score += 15
    elif days_since_update <= 30:
        score += 11
    elif days_since_update <= 90:
        score += 7
    else:
        score += 3

    if days_since_push <= 7:
        score += 15
    elif days_since_push <= 30:
        score += 11
    elif days_since_push <= 90:
        score += 7
    else:
        score += 3

    score = min(score, 30)
    label = _label_from_ratio(score, 30)
    summary = {
        "high": "仓库近期仍保持活跃更新",
        "good": "仓库更新较稳定，整体活跃度不错",
        "medium": "仓库有一定维护，但更新节奏一般",
        "low": "仓库近期更新较少，活跃度偏弱",
    }[label]
    return HealthDimension(score=score, label=label, summary=summary)


def _build_maintenance(
    description: str,
    license_name: str,
    homepage: str | None,
    readme_exists: bool,
    release_exists: bool,
) -> HealthDimension:
    score = 0
    if description:
        score += 4
    if license_name and license_name != "None":
        score += 6
    if homepage:
        score += 3
    if readme_exists:
        score += 4
    if release_exists:
        score += 3

    score = min(score, 20)
    label = _label_from_ratio(score, 20)
    summary = {
        "high": "仓库维护规范性很强，信息完整度较高",
        "good": "仓库具备较好的维护规范性",
        "medium": "仓库具备基础维护信息，但规范性一般",
        "low": "仓库维护信号较弱，规范性不足",
    }[label]
    return HealthDimension(score=score, label=label, summary=summary)


def _build_technical_clarity(language_data: dict[str, int], topics_count: int) -> HealthDimension:
    if not language_data:
        return HealthDimension(score=4, label="low", summary="缺少语言分布信息，技术结构不够清晰")

    total = sum(language_data.values())
    top_language = max(language_data.values())
    concentration = top_language / total if total else 0

    score = 0
    if concentration >= 0.7:
        score += 12
    elif concentration >= 0.5:
        score += 9
    elif concentration >= 0.3:
        score += 6
    else:
        score += 4

    if topics_count >= 5:
        score += 6
    elif topics_count >= 2:
        score += 4
    else:
        score += 2

    unique_languages = len(language_data)
    if unique_languages <= 3:
        score += 2
    elif unique_languages <= 6:
        score += 1

    score = min(score, 20)
    label = _label_from_ratio(score, 20)
    summary = {
        "high": "技术栈清晰，项目结构集中明确",
        "good": "技术栈较清晰，语言分布集中",
        "medium": "技术栈可识别，但结构集中度一般",
        "low": "技术栈分散或信息不足，结构清晰度偏弱",
    }[label]
    return HealthDimension(score=score, label=label, summary=summary)


def build_analysis_payload(
    repo_data: dict,
    language_data: dict[str, int],
    readme_exists: bool,
    release_exists: bool,
) -> AnalyzeResult:
    repo = RepoInfo(
        owner=repo_data["owner"]["login"],
        name=repo_data["name"],
        fullName=repo_data["full_name"],
        description=repo_data.get("description") or "",
        repoUrl=repo_data["html_url"],
        homepage=repo_data.get("homepage") or None,
        defaultBranch=repo_data["default_branch"],
        mainLanguage=repo_data.get("language") or "Unknown",
        license=(repo_data.get("license") or {}).get("spdx_id")
        or (repo_data.get("license") or {}).get("name")
        or "None",
        topics=repo_data.get("topics") or [],
        createdAt=repo_data["created_at"],
        updatedAt=repo_data["updated_at"],
        pushedAt=repo_data["pushed_at"],
        avatarUrl=repo_data["owner"]["avatar_url"],
    )

    metrics = Metrics(
        stars=repo_data["stargazers_count"],
        forks=repo_data["forks_count"],
        watchers=repo_data["watchers_count"],
        openIssues=repo_data["open_issues_count"],
        subscribers=repo_data.get("subscribers_count"),
        sizeKb=repo_data["size"],
        starForkRatio=_safe_ratio(repo_data["stargazers_count"], repo_data["forks_count"]),
        repoAgeDays=_repo_age_days(repo_data["created_at"]),
        daysSinceUpdate=_days_since(repo_data["updated_at"]),
        daysSincePush=_days_since(repo_data["pushed_at"]),
        topicsCount=len(repo_data.get("topics") or []),
    )

    popularity = _build_popularity(metrics.stars, metrics.forks, metrics.watchers)
    activity = _build_activity(metrics.daysSinceUpdate, metrics.daysSincePush)
    maintenance = _build_maintenance(
        repo.description,
        repo.license,
        repo.homepage,
        readme_exists,
        release_exists,
    )
    technical_clarity = _build_technical_clarity(language_data, metrics.topicsCount)

    health = Health(
        popularity=popularity,
        activity=activity,
        maintenance=maintenance,
        technicalClarity=technical_clarity,
    )

    total = (
        popularity.score
        + activity.score
        + maintenance.score
        + technical_clarity.score
    )
    score = Score(
        total=total,
        level=_level_from_total(total),
        breakdown={
            "popularity": popularity.score,
            "activity": activity.score,
            "maintenance": maintenance.score,
            "technicalClarity": technical_clarity.score,
        },
        summary=f"项目整体评分为 {total}/100，当前评级为{_level_from_total(total)}。",
    )

    charts = Charts(
        languages=_language_chart(language_data),
        healthRadar=[
            RadarChartItem(name="社区热度", value=popularity.score, fullMark=30),
            RadarChartItem(name="项目活跃度", value=activity.score, fullMark=30),
            RadarChartItem(name="维护规范度", value=maintenance.score, fullMark=20),
            RadarChartItem(name="技术清晰度", value=technical_clarity.score, fullMark=20),
        ],
        overviewBars=[
            OverviewChartItem(name="Stars", value=metrics.stars),
            OverviewChartItem(name="Forks", value=metrics.forks),
            OverviewChartItem(name="Watchers", value=metrics.watchers),
            OverviewChartItem(name="Open Issues", value=metrics.openIssues),
        ],
    )

    return AnalyzeResult(
        repo=repo,
        metrics=metrics,
        health=health,
        score=score,
        aiReport=AIReport(enabled=False, available=False, error="AI not requested"),
        charts=charts,
    )

