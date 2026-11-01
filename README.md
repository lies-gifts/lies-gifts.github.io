# AI 日报

中文 AI 日报静态站点。以固定来源直接抓取、摘要和去重为主；关键结论再核验原始来源。

## 页面与更新

- 页面：`index.html`（无构建依赖，无第三方脚本）。
- 目录：`data/index.json`，保留历史日期和固定信息源。
- 每期：`data/YYYY-MM-DD.json`，按北京时间归档。
- 由原“LLM 能力榜跟踪”任务更新为“AI 日报”，沿用北京时间每天 08:00。
- 定时任务负责抓取、汇总并通过已连接的 GitHub 写入数据；本仓库不另设重复抓取定时器，也不要求模型 API Key。
- 页面不会自行爬取新闻。若任务未成功写入，页面不会假装已经更新。

## 启用 GitHub Pages

仓库 Settings → Pages → Source 选择 **Deploy from a branch**，Branch 选择 **main**，Folder 选择 **/(root)**，保存。

目标入口：`https://lies-gifts.github.io/`。只有站点实际部署并能打开后才算上线。

## 发布协议

1. 读取 `data/index.json`，按需读取最近几期以去重。
2. 直接访问固定来源，区分源站发布时间、事件日期与抓取时间。
3. 先写入当天 JSON，再更新目录；同一天重复运行应合并、去重，不覆盖丢失已发布条目。
4. 新文件用 GitHub `create_file`；更新文件先读最新 SHA，再用 `update_file`。禁止强制覆盖分支。
5. 目录条目格式：`{"date":"YYYY-MM-DD","title":"本期标题","count":0}`，按日期倒序。
6. 写入后回读核验。提交成功与网页部署成功分开报告。

每期 JSON 格式（字段示意，不是新闻）：

```json
{
  "schema_version": 1,
  "date": "YYYY-MM-DD",
  "generated_at": "ISO-8601，含 +08:00 时区",
  "window_start": "ISO-8601",
  "window_end": "ISO-8601",
  "title": "简短日报标题",
  "summary": "本期速览",
  "items": [],
  "source_status": [],
  "notes": []
}
```

`items` 每条字段：`id`、`event_key`、`category`、`title`、`summary`、`impact`、`published_at`（不确定填 null）、`source_name`、`source_url`、`verification`、`is_update`、`related_sources`（name/url 对象数组）、`models`（字符串数组）。

分类：模型与产品、编程与Agent、多模态、榜单与评测、开源与研究、行业。

验证标记：官方发布、独立评测、媒体报道、待核实。未核实的重大传言不得写成事实。

`source_status` 每条字段：`name`、`url`、`status`（ok / unchanged / failed）、`checked_at`、`latest_date`（未知填 null）、`note`。

没有重要新增时仍写入空 items 的当日归档，并说明覆盖范围和抓取失败项；不以旧闻填充。网站与仓库均为公开内容，不得加入私人聊天、凭据或非公开资料。只发布独立撰写的简短摘要与原文链接，不转载全文。
