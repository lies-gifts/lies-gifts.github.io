# AI 日报

中文 AI 生态情报站：[阅读日报](https://lies-gifts.github.io/)。保留日期归档、搜索、分类和标签筛选；每条摘要链接原文，并区分官方发布、独立评测、媒体报道与研究预印本。

## 内容与分类

顶层分类为 **模型与产品 · 前沿进展、开源项目、研究、行业动态**。旧版前四类在页面显示时合并，原分类保留为副标签，不重写历史条目。

覆盖 Agent、编程工具、推理服务、RAG/检索、多模态、本地部署、开发基础设施，以及重要模型、产品、公司和研究进展。开源项目介绍具体用途、适用人群、许可证、限制和原仓库；有公开仓库或开放权重不自动等于开源。

## 文件

| 文件 | 用途 |
| --- | --- |
| `index.html`、`assets/app.js` | 无框架静态页面，无第三方运行时脚本 |
| `data/index.json` | 历史日期与来源目录，兼容旧结构 |
| `data/YYYY-MM-DD.json` | 每期正文与抓取状态，按北京时间归档 |
| `data/revisions/` | 同一天增补前的原始版本，完整保留 |
| `config/taxonomy.json` | 分类、旧分类映射、推荐标签 |
| `config/sources.json` | 43 个来源及抓取端点、方式、分组、证据类型、选择规则 |
| `docs/DAILY_WORKFLOW.md` | 日常采集、核实、排序和发布协议 |
| `docs/SCHEDULED_TASK_PROMPT.txt` | 供现有每日任务使用的完整指令 |
| `scripts/daily.py` | 无依赖采集器、归档校验、无损发布暂存 |

## 日常执行

现有任务约定北京时间每天 08:00，目标仓库始终为 `lies-gifts/lies-gifts.github.io` 的 `main`，页面从分支根目录发布。**本次没有新增第二个定时器。仓库工作流更新不等于 ChatGPT 托管任务的保存指令已经修改；后台配置须另外确认。**

每次先读取本仓库当前 `docs/DAILY_WORKFLOW.md`、`config/sources.json`、`config/taxonomy.json`、`data/index.json` 和最近归档。不要继续使用旧版五个来源的硬编码列表。

有 Python 的环境可运行：

```sh
python scripts/daily.py collect --out .work/run
```

产生 `collection.json`、`candidates.json` 和原始响应快照。候选只供编辑筛选，不会自动冒充成已核实新闻。直接 RSS/API/页面抓取失败时，可使用已有网页或 GitHub 连接器补读，并保留失败记录。ChatGPT 托管环境也可直接用连接器执行同一协议，不要求本机在线或新增模型 API Key。

编辑核对原文后，写成符合第 2 版结构的 `edition.json`，再执行：

```sh
python scripts/daily.py prepare --edition .work/edition.json --out .work/staged
```

`prepare` 只生成待发布文件，不联网写仓库。它保留旧条目、保存同日原版、拒绝未核实条目与无说明的覆盖。将暂存的 `data/` 合入工作副本后运行：

```sh
python scripts/daily.py validate
python -m unittest discover -s scripts -p "test_*.py"
```

最终通过已授权 GitHub 连接器一次提交正文、目录和修订存档。更新 ref 使用最新分支 SHA 比较、`force=false`；竞争更新时重新合并，不强推。

## 发布与证据边界

对新闻优先检查过去 24 小时；项目与研究可回看 7 天，并在条目中明确原始日期。来源发布时间、事件日期、发现时间、抓取时间分别记录。热榜、stars、下载数和点赞用于发现，不作为质量或能力排名。论文摘要里的作者成绩不等于独立复现；未全文阅读时不能声称已精读。

通常选 3–10 条有用内容，允许更少或为空；按影响、用途、新鲜度和证据排序，避免一个高频 release 项目挤占版面。页面抓取成功不等于逐条核实，解析为空不等于无新闻。每期展示失败、部分抓取和缺失记录。

发布后回读仓库文件、核对 Pages 构建提交，并实际访问页面与数据。分别记录“本地验证通过”“提交已写入”“Pages 部署成功”“线上页面已核验”；不把任一前一步当作后一步已完成。

只发布自行撰写的短摘要与原文链接。原始网页快照和候选队列保留在被忽略的 `.work/`，不公开全文、凭据或私人资料。
