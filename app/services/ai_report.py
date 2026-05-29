import json

import httpx

from app.core.config import get_settings
from app.models.schemas import AIReport, Health, Metrics, RepoInfo, Score
from app.utils.yaml_config import load_simple_yaml


class AIServiceError(Exception):
    pass


def _fallback_ai_report(
    repo: RepoInfo,
    score: Score,
    health: Health,
    metrics: Metrics,
    error: str,
) -> AIReport:
    strengths: list[str] = []
    risks: list[str] = []
    advice: list[str] = []

    if health.popularity.score >= 22:
        strengths.append("社区热度较高，说明项目具备较强的外部关注度。")
    else:
        risks.append("社区热度相对有限，参考资料和社区活跃度可能不足。")

    if health.activity.score >= 22:
        strengths.append("近期仍在持续更新，项目活跃度表现较好。")
    else:
        risks.append("近期更新节奏偏慢，接入前建议评估维护持续性。")

    if health.maintenance.score >= 14:
        strengths.append("仓库说明、许可或发布信息较完整，维护规范性较好。")
    else:
        risks.append("仓库规范化信号一般，建议进一步查看 README、License 和 Release。")

    if metrics.openIssues > 1000:
        risks.append("Open Issues 数量较高，可能意味着维护压力较大。")

    advice.append("适合作为技术调研和学习参考的第一步。")
    advice.append(f"如果计划正式采用 {repo.fullName}，建议结合文档质量和最近发布情况继续评估。")
    advice.append("可进一步查看 README、Release Notes 和 Issue 讨论来确认项目稳定性。")

    return AIReport(
        enabled=True,
        available=False,
        score=score.total,
        level=score.level,
        summary=f"{repo.fullName} 当前整体评级为{score.level}，已返回规则化兜底分析。",
        strengths=strengths,
        risks=risks,
        advice=advice,
        error=error,
    )


def _build_prompt(repo: RepoInfo, score: Score, health: Health, metrics: Metrics) -> str:
    return f"""
你是一个Github开源项目评审助手。请基于输入的结构化信息，为该仓库生成客观、简洁、可展示的中文体检报告。

请只输出JSON对象，不要输出Markdown，不要输出解释，不要使用代码块。

JSON schema:
{{
  "score": 0,
  "level": "优秀|良好|一般|风险较高",
  "summary": "一句话总结",
  "strengths": ["优点1", "优点2"],
  "risks": ["风险1", "风险2"],
  "advice": ["建议1", "建议2", "建议3"]
}}

仓库信息:
- fullName: {repo.fullName}
- description: {repo.description}
- mainLanguage: {repo.mainLanguage}
- license: {repo.license}
- updatedAt: {repo.updatedAt}
- pushedAt: {repo.pushedAt}

核心指标:
- stars: {metrics.stars}
- forks: {metrics.forks}
- watchers: {metrics.watchers}
- openIssues: {metrics.openIssues}
- starForkRatio: {metrics.starForkRatio}
- repoAgeDays: {metrics.repoAgeDays}
- daysSinceUpdate: {metrics.daysSinceUpdate}
- daysSincePush: {metrics.daysSincePush}
- topicsCount: {metrics.topicsCount}

规则评分:
- total: {score.total}
- level: {score.level}
- popularity: {score.breakdown.get("popularity", 0)}
- activity: {score.breakdown.get("activity", 0)}
- maintenance: {score.breakdown.get("maintenance", 0)}
- technicalClarity: {score.breakdown.get("technicalClarity", 0)}

维度说明:
- popularity: {health.popularity.summary}
- activity: {health.activity.summary}
- maintenance: {health.maintenance.summary}
- technicalClarity: {health.technicalClarity.summary}

要求:
- 语气专业、克制
- 不要编造不存在的信息
- 建议面向“学习参考/技术选型/生产参考”场景
- score 必须是 0 到 100 的整数
- strengths、risks、advice 各返回 2 到 4 条
""".strip()


async def build_ai_report(
    enable_ai: bool,
    repo: RepoInfo,
    score: Score,
    health: Health,
    metrics: Metrics,
) -> AIReport:
    if not enable_ai:
        return AIReport(
            enabled=False,
            available=False,
            error="AI analysis disabled",
        )

    settings = get_settings()

    try:
        llm_config = load_simple_yaml(settings.llm_config_path)
        api_key = llm_config["api_key"]
        base_url = llm_config["base_url"].rstrip("/")
        model_name = llm_config["model_name"]
    except Exception as exc:
        return _fallback_ai_report(repo, score, health, metrics, f"failed to load model config: {exc}")

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": "你是一个严谨的Github仓库评审助手，只输出合法JSON。",
            },
            {
                "role": "user",
                "content": _build_prompt(repo, score, health, metrics),
            },
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(
            timeout=settings.ai_request_timeout_seconds,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            response = await client.post(f"{base_url}/chat/completions", json=payload)
            response.raise_for_status()
            raw = response.json()
            content = raw["choices"][0]["message"]["content"]
            parsed = json.loads(content)
    except Exception as exc:
        return _fallback_ai_report(repo, score, health, metrics, f"llm request failed: {exc}")

    try:
        llm_score = int(parsed.get("score", score.total))
        llm_score = max(0, min(llm_score, 100))
        return AIReport(
            enabled=True,
            available=True,
            score=llm_score,
            level=str(parsed.get("level") or score.level),
            summary=str(parsed.get("summary") or score.summary),
            strengths=[str(item) for item in parsed.get("strengths", [])][:4],
            risks=[str(item) for item in parsed.get("risks", [])][:4],
            advice=[str(item) for item in parsed.get("advice", [])][:4],
            error=None,
        )
    except Exception as exc:
        return _fallback_ai_report(repo, score, health, metrics, f"llm response parse failed: {exc}")
