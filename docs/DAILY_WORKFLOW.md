# AI 日报日常采集与发布协议 v2

目标是发现整个 AI 生态的重要变化和可实际使用的项目。每次运行都重新读取本文件，避免任务指令与来源配置漂移。

## 输入和时段

1. 确认仓库 `lies-gifts/lies-gifts.github.io`、`main` 当前 head、目录及最近 7 日正文；归档较少时读取现有全部正文。使用 Asia/Shanghai，沿用每天 08:00 的现有任务。
2. 读取 `config/sources.json` 与 `config/taxonomy.json`。新闻优先 24 小时，项目与研究发现可回看 7 天并明确标注；重大新证据可以作为旧事件的补充，但说明新增证据与日期。
3. 采集主干同时覆盖官方发布、开源项目、研究/社区、新闻和独立评测。没有满足标准的内容时允许该类为空，不把均衡覆盖变成栏目配额。

## 抓取和来源发现

- 优先 `fetch_url` 指定的 RSS、Atom、GitHub Releases API、HF API 和网页。独立来源可有限并发；每源超时、大小和有限重试受配置约束。
- HTML/Trending/HF Models/Spaces 是发现入口。继续阅读候选的官方发布、README、release、许可证、模型卡或论文。可定向补充新发现项目的 releases，不受固定仓库列表限制。
- 官方站点提供厂商信息；AIBase、Latent Space、MIT Technology Review、VentureBeat 和开发者博客提供线索和报道；Artificial Analysis、Arena、Vals 用于独立评测，不主导整份日报。
- 如 HTML 无法解析，可直接读取页面并抽取已见链接；网页工具读取成功时注明实际工具、时间和范围。仅知道 URL 或收到 HTTP 200 不构成正文核实。
- 记录每源 `id/name/url/status/checked_at/latest_date/note`。`ok` 为已读取结构化条目，`partial` 为只读到列表/空列表/部分内容，`failed` 为失败；只有实际比较过新旧内容才写 `unchanged`。

## 去重、证据、排序

1. 去除 URL 跟踪参数；按同一原文、repo+版本、论文 ID、产品+发布事件建立稳定 `event_key`。同一事件多家报道合为一条，原始出处为主，其他放 `related_sources`。相同项目不同版本不要仅按 repo 名误合并。
2. 与最近归档比较；重复报道不重发。新实质信息须 `is_update=true` 与 `change_note`，保留此前版本。同一天多次运行合并旧条目，不整期覆盖删除。
3. 编辑逐项判断影响（0–4）、具体用途（0–3）、新鲜度（0–2）、证据充分度（0–3）；总分用于编辑排序，同时在 `selection_reason` 写选择理由。候选的 `heuristic_score` 仅是自动初筛，不能代替这一判断。最终按编辑排序排列。
4. 通常精选 3–10 条；允许更少或 0 条。不把小补丁、预发布版本号变化或重复榜单分数本身当成重大突破。避免连续刊发同一项目多个构建。
5. 明确区分官方发布/官方自述、独立评测、媒体报道、研究预印本、待核实。每条 `evidence_note` 说清楚读到了什么、没有验证什么。重大传言和无依据指控不写成事实。性能数字注明基准版本、硬件、任务和推理条件；不跨条件拼成排行榜。

## 条目结构

沿用旧版 `id/event_key/category/title/summary/impact/published_at/source_name/source_url/verification/is_update/related_sources/models`。新增：

- `tags`：具体技术或产品标签；顶层分类只有四个。
- `editorial_reviewed: true`：编辑已核对原始证据；不是采集成功标记，不要求额外用户审批。
- `evidence_note`：证据边界；`selection_reason`：入选理由；可加 `editorial_score`。
- `date_note`：不在 24 小时窗口内、日期只精确到天或具体发布时间未知时必须说明。未知时间用 null，不填当天零点冒充精确值。
- `repository_url`：开源项目原仓库；`project` 含 `purpose/audience/license/limitations/quick_start_url`。未经核验许可证时写明未知，不断言可商用。公开 issue tracker、开放权重、开源代码和商业许可分别判断。
- `published_at` 是原始发布时间；`event_at` 是确有证据的事件时间；发现或抓取时间不能替代前两者。

每期保留 `date/generated_at/window_start/window_end/title/summary/items/source_status/notes`，加 `schema_version:2`、`editorial_reviewed:true`。无新增可 `items:[]`，说明实际覆盖和失败项。不要用“所有来源均无新增”概括部分抓取。

## 无损提交与部署核验

1. 有 Python 时先 `prepare`，再将暂存结果合入工作副本并 `validate`。无执行环境时，用连接器按同样规则构造文件，校验日期、唯一 ID/事件/URL、条目数和目录一致性。
2. 改写同日正文前，将原始文件完整保存在 `data/revisions/YYYY-MM-DD/<内容哈希>.json`，新正文 `previous_revisions` 记录相对路径。保留全部原条目及历史目录，其他日期不变。
3. 重新读取 main head。以当前 tree 为 base，一次 create_tree（仅本次明确变更文件）→ create_commit（当前 head 为 parent）→ update_ref（expected_sha=当前 head，force=false）。不要提交候选全文、原始快照或凭据。
4. 若比较失败，读取新 head 和当天正文，合并后重试一次；冲突不能可靠解决时保留待发布稿并报告，不强推。
5. 回读正文和目录，核对条目数与日期。检查同一 commit 的 Pages workflow 成功状态，再读取线上 HTML、JS、目录及正文。浏览器可用时验证日期切换、分类、标签、关键词、原文链接和移动布局。
6. 通知沿用原偏好：有实质新增最多三条要点和网站入口；无实质新增不打扰，但仍可留当天归档。失败或需要用户处理时明确说明。不另建重复定时器。
