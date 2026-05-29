# Github Repo Checkup

一个基于 `FastAPI` 的 Github 仓库“体检”工具。

用户输入公开 Github 仓库 URL 后，系统会：

- 拉取仓库基础信息
- 计算规则化健康度评分
- 展示语言分布与核心指标
- 调用大模型生成 AI 体检报告
- 在线浏览仓库文件树和文件内容

整个文件浏览能力**不是通过 `git clone` 到本地实现**，而是直接通过 Github API 获取目录树和文件内容。

## 当前功能

- Web 页面输入公开 Github 仓库 URL
- 基础分析先返回，AI 报告后加载
- Github 仓库基础信息展示
- Stars / Forks / Watchers / Open Issues 展示
- 规则化健康度评分
- AI 项目总结、风险和建议
- 仓库文件树浏览
- 点击文件在线查看内容
- 文件树支持折叠/展开
- 大文件在固定高度面板中滚动查看，不会无限撑高页面
- 前后端都做了缓存，减少重复请求和 Github API 限流概率

## 技术栈

- Backend: `FastAPI`
- HTTP Client: `httpx`
- Frontend: 原生 `HTML + CSS + JavaScript`
- AI: 兼容 OpenAI Chat Completions 风格接口

## 目录结构

```text
github_repo_checkup/
  app/
    api/         # 路由
    core/        # 配置
    models/      # 数据模型与 config.yaml
    services/    # Github 分析、AI、文件浏览服务
    static/      # 前端页面
    utils/       # URL 解析、缓存、yaml 读取
    main.py
  requirements.txt
  README.md
```

## 运行方式

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 配置模型与可选 Github Token

编辑 [app/models/config.yaml](app/models/config.yaml)：

```yaml
api_key: "你的模型 key"
base_url: "你的模型 base_url"
model_name: "你的模型名"
github_token: "可选，你的 Github token"
```

说明：

- `api_key` / `base_url` / `model_name` 用于 AI 分析
- `github_token` 可选，但**强烈建议配置**
- 如果不配置 `github_token`，频繁分析公开仓库时更容易触发 Github API `429`

3. 启动服务

```bash
uvicorn app.main:app --reload
```

4. 打开页面

```text
http://127.0.0.1:8000
```

## 两阶段分析流程

当前分析流程不是一次性等所有内容都完成才展示，而是分两段：

### 第一段：基础分析

后端直接从 Github 获取并计算：

- 仓库基础信息
- 核心指标
- 语言分布
- 健康度维度
- 规则评分

这些结果会优先返回并立即展示。

### 第二段：AI 报告

前端拿到基础结构化数据后，再单独请求 AI 分析接口。

模型输入的不是整个仓库源码，而是后端整理好的结构化信息，例如：

- repo
- metrics
- health
- score

这样做的好处：

- 首屏更快
- 基础结果不依赖 AI
- 模型职责更聚焦在总结、风险提示、建议生成

## 文件树浏览说明

文件树和文件内容通过 Github API 实现：

- 文件树：Github Branch / Tree API
- 文件内容：Github Contents API

特点：

- 不 clone 仓库到本地
- 可直接浏览公开仓库目录
- 支持折叠目录
- 支持在线查看文本文件内容

## 缓存与限流

为减少重复请求，当前版本做了几层缓存：

- 仓库基础信息缓存
- 仓库文件树缓存
- 分析结果缓存
- 文件内容缓存
- 前端内存缓存同仓库文件树

默认缓存有效期为 `300` 秒。

如果仍然遇到 Github API 限流：

1. 优先检查是否配置了 `github_token`
2. 避免短时间内频繁切换大量仓库
3. 等待一段时间后重试

## 环境变量

支持以下可选环境变量：

- `APP_NAME`
- `GITHUB_API_BASE`
- `GITHUB_TOKEN`
- `REQUEST_TIMEOUT_SECONDS`
- `AI_REQUEST_TIMEOUT_SECONDS`
- `LLM_CONFIG_PATH`
- `CACHE_TTL_SECONDS`

通常只配 `config.yaml` 就够用了。

## 当前接口

- `GET /`
- `GET /api/health`
- `GET /api/examples`
- `POST /api/analyze`
- `POST /api/analyze/ai`
- `GET /api/repo/tree`
- `GET /api/repo/file`

## 接口说明

### `POST /api/analyze`

返回基础分析结果，不依赖 AI。

请求示例：

```json
{
  "repoUrl": "https://github.com/vercel/next.js",
  "enableAI": false
}
```

### `POST /api/analyze/ai`

接收基础结构化数据，返回 AI 报告。

### `GET /api/repo/tree`

根据 `repoUrl` 返回仓库文件树。

### `GET /api/repo/file`

根据 `repoUrl + path` 返回指定文件内容。

## 当前限制

- 仅支持公开 Github 仓库
- 主要适合文本文件在线预览
- 二进制文件暂未做专门预览处理
- AI 报告依赖外部模型服务可用性

## 后续可继续优化

- 代码高亮
- 行号显示
- 二进制文件“不可预览”提示
- 文件树展开状态持久化
- 请求取消与输入防抖
- 导出分析报告
