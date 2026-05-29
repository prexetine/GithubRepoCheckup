from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, HttpUrl


T = TypeVar("T")


class SuccessEnvelope(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T


class ErrorResponse(BaseModel):
    success: bool
    message: str
    errorCode: str
    data: None = None


class AnalyzeRequest(BaseModel):
    repoUrl: HttpUrl
    enableAI: bool = True


class AIAnalyzeRequest(BaseModel):
    repo: "RepoInfo"
    metrics: "Metrics"
    health: "Health"
    score: "Score"


class RepoQuery(BaseModel):
    repoUrl: HttpUrl


class ParsedRepo(BaseModel):
    owner: str
    repo: str


class RepoInfo(BaseModel):
    owner: str
    name: str
    fullName: str
    description: str
    repoUrl: str
    homepage: str | None = None
    defaultBranch: str
    mainLanguage: str
    license: str
    topics: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str
    pushedAt: str
    avatarUrl: str


class Metrics(BaseModel):
    stars: int
    forks: int
    watchers: int
    openIssues: int
    subscribers: int | None = None
    sizeKb: int
    starForkRatio: float
    repoAgeDays: int
    daysSinceUpdate: int
    daysSincePush: int
    topicsCount: int


class HealthDimension(BaseModel):
    score: int
    label: str
    summary: str


class Health(BaseModel):
    popularity: HealthDimension
    activity: HealthDimension
    maintenance: HealthDimension
    technicalClarity: HealthDimension


class Score(BaseModel):
    total: int
    level: str
    maxScore: int = 100
    breakdown: dict[str, int]
    summary: str


class AIReport(BaseModel):
    enabled: bool
    available: bool
    score: int | None = None
    level: str | None = None
    summary: str | None = None
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    advice: list[str] = Field(default_factory=list)
    error: str | None = None


class LanguageChartItem(BaseModel):
    name: str
    value: int
    percent: float


class RadarChartItem(BaseModel):
    name: str
    value: int
    fullMark: int


class OverviewChartItem(BaseModel):
    name: str
    value: int


class Charts(BaseModel):
    languages: list[LanguageChartItem]
    healthRadar: list[RadarChartItem]
    overviewBars: list[OverviewChartItem]


class AnalyzeResult(BaseModel):
    repo: RepoInfo
    metrics: Metrics
    health: Health
    score: Score
    aiReport: AIReport
    charts: Charts


class AnalyzeResponse(SuccessEnvelope[AnalyzeResult]):
    pass


class HealthResponse(SuccessEnvelope[dict[str, str]]):
    pass


class ExamplesResponse(SuccessEnvelope[list[str]]):
    pass


class RepoTreeNode(BaseModel):
    name: str
    path: str
    type: str
    children: list["RepoTreeNode"] = Field(default_factory=list)


class RepoTreePayload(BaseModel):
    repoFullName: str
    defaultBranch: str
    nodes: list[RepoTreeNode]


class RepoTreeResponse(SuccessEnvelope[RepoTreePayload]):
    pass


class RepoFilePayload(BaseModel):
    repoFullName: str
    path: str
    name: str
    size: int
    encoding: str
    content: str
    truncated: bool = False
    htmlUrl: str | None = None


class RepoFileResponse(SuccessEnvelope[RepoFilePayload]):
    pass


class AIReportResponse(SuccessEnvelope[AIReport]):
    pass
