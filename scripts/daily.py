"""Public-source collector and lossless publication staging; Python 3.10+, no packages.

Collection produces leads, never automatically authored news. The scheduled editor
verifies original sources and supplies a reviewed edition to `prepare`.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import email.utils
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
TZ = dt.timezone(dt.timedelta(hours=8))
CATEGORIES = {"模型与产品 · 前沿进展", "开源项目", "研究", "行业动态"}
VERIFICATIONS = {"官方发布", "独立评测", "媒体报道", "研究预印本", "待核实"}
FORMATS = {"rss", "atom", "github_releases", "github_trending", "hf_papers", "hf_models", "hf_spaces", "html"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now():
    return dt.datetime.now(TZ).replace(microsecond=0)


def parse_time(value):
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = email.utils.parsedate_to_datetime(str(value))
        except (ValueError, TypeError):
            return None
    # Never infer a source timezone for naive timestamps.
    return parsed if parsed.tzinfo else None


def canonical(url):
    p = urllib.parse.urlsplit(str(url))
    if p.scheme not in ("https", "http") or not p.netloc or p.username or p.password:
        raise ValueError("Expected a public http(s) URL")
    query = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"ref", "source", "fbclid", "gclid"}]
    host = p.netloc.lower()
    path = p.path.rstrip("/") or "/"
    if host in {"www.arxiv.org", "export.arxiv.org"}:
        host = "arxiv.org"
    if host == "arxiv.org":
        path = re.sub(r"^/pdf/", "/abs/", path).removesuffix(".pdf")
        path = re.sub(r"v\d+$", "", path)
    return urllib.parse.urlunsplit((p.scheme, host, path, urllib.parse.urlencode(sorted(query)), ""))


def plain(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", str(value or "")))).strip()


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.href, self.parts = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.parts = []

    def handle_data(self, data):
        if self.href:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            self.links.append((self.href, plain(" ".join(self.parts))))
            self.href = None


def xml_value(node, names):
    for child in node:
        if child.tag.split("}")[-1] in names:
            return "".join(child.itertext()).strip()
    return ""


def parse_source(source, body):
    fmt = source["format"]
    rows = []
    if fmt in {"rss", "atom"}:
        root = ET.fromstring(body)
        for node in root.iter():
            if node.tag.split("}")[-1] not in {"item", "entry"}:
                continue
            url = xml_value(node, {"link"})
            for child in node:
                if child.tag.split("}")[-1] == "link" and child.get("href") and child.get("rel", "alternate") == "alternate":
                    url = child.get("href")
                    break
            rows.append({"title": xml_value(node, {"title"}), "source_url": url,
                         "published_at": xml_value(node, {"pubDate", "published", "date"}) or None,
                         "updated_at": xml_value(node, {"updated"}) or None,
                         "excerpt": xml_value(node, {"description", "summary", "content"})})
    elif fmt == "github_releases":
        payload = json.loads(body)
        if not isinstance(payload, list):
            raise ValueError("GitHub releases response is not a list")
        for release in payload:
            if release.get("draft"):
                continue
            repo = source["repo"]
            rows.append({"title": f"{repo}: {release.get('name') or release['tag_name']}",
                         "source_url": release["html_url"], "published_at": release.get("published_at"),
                         "excerpt": release.get("body", ""), "repository_url": f"https://github.com/{repo}",
                         "event_key": f"release:{repo.lower()}:{release['tag_name']}",
                         "prerelease": bool(release.get("prerelease"))})
    elif fmt in {"hf_papers", "hf_models", "hf_spaces"}:
        payload = json.loads(body)
        if not isinstance(payload, list):
            raise ValueError("Hugging Face response is not a list")
        for entry in payload:
            if fmt == "hf_papers":
                paper = entry.get("paper", entry)
                rows.append({"title": paper.get("title", paper["id"]),
                             "source_url": f"https://arxiv.org/abs/{paper['id']}",
                             "published_at": paper.get("publishedAt"), "excerpt": paper.get("summary", ""),
                             "discovery_url": f"https://huggingface.co/papers/{paper['id']}"})
            else:
                kind = "spaces/" if fmt == "hf_spaces" else ""
                rows.append({"title": entry["id"], "source_url": f"https://huggingface.co/{kind}{entry['id']}",
                             "published_at": None, "updated_at": entry.get("lastModified"),
                             "excerpt": "模型卡或 Space 发现线索；修改时间不等于发布日。"})
    elif fmt in {"html", "github_trending"}:
        parser = Links()
        parser.feed(body.decode("utf-8", errors="replace"))
        for href, title in parser.links:
            url = urllib.parse.urljoin(source["url"], href)
            if fmt == "github_trending":
                if not re.match(r"^https://github\.com/[^/?#]+/[^/?#]+$", url) or " / " not in title:
                    continue
            elif not source.get("link_pattern") or not re.search(source["link_pattern"], url):
                continue
            if len(title) < 4:
                continue
            row = {"title": title, "source_url": url, "published_at": None, "excerpt": "列表发现线索，待读取原文核对日期与内容。"}
            if fmt == "github_trending":
                row["repository_url"] = url
            rows.append(row)
    else:
        raise ValueError(f"Unsupported format: {fmt}")
    return rows


def fetch_source(source, output, fetched_at, timeout=18, max_bytes=4000000):
    status = {"id": source["id"], "name": source["name"], "url": source["url"],
              "checked_at": fetched_at.isoformat(), "latest_date": None, "status": "failed"}
    attempts = [{"url": source["fetch_url"], "format": source["format"]}] + source.get("fallback_urls", [])
    errors = []
    for endpoint in attempts:
        for attempt in range(2):
            try:
                request = urllib.request.Request(endpoint["url"], headers={"User-Agent": "AI-Daily/2.0 (+https://lies-gifts.github.io/)", "Accept": "application/json, application/rss+xml, application/atom+xml, text/html;q=0.8, */*;q=0.1"})
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    body = response.read(max_bytes + 1)
                    if len(body) > max_bytes:
                        raise ValueError("Response exceeded configured size limit")
                    status.update({"http_status": response.status, "resolved_url": response.url,
                                   "content_type": response.headers.get("Content-Type", "")})
                parse_config = {**source, "format": endpoint["format"]}
                rows = parse_source(parse_config, body)
                raw = Path(output) / "raw" / (source["id"] + ".body")
                raw.parent.mkdir(parents=True, exist_ok=True)
                raw.write_bytes(body)
                dates = [parse_time(x.get("published_at")) for x in rows]
                dates = [x for x in dates if x]
                discovery = endpoint["format"] in {"html", "github_trending", "hf_models", "hf_spaces"}
                status.update({"status": "partial" if discovery or not rows else "ok", "parsed_count": len(rows),
                               "latest_date": max(dates).date().isoformat() if dates else None,
                               "sha256": hashlib.sha256(body).hexdigest(), "fetch_url": endpoint["url"],
                               "note": ("已读取发现列表；原文日期与结论需逐项核查。" if discovery else "已解析条目；不代表每条已核验或适合刊发。") if rows else "HTTP 可达，但本次解析为0条；不能据此认定没有新闻。"})
                if errors:
                    status["attempt_errors"] = errors
                return rows, status
            except (OSError, ValueError, ET.ParseError, KeyError) as error:
                errors.append(f"{endpoint['url']}: {type(error).__name__}: {error}")
                if isinstance(error, urllib.error.HTTPError) and error.code not in {429, 500, 502, 503, 504}:
                    break
                if attempt == 0:
                    time.sleep(0.6)
    status["note"] = "抓取或解析失败；不能判定该源是否有新增。"
    status["errors"] = errors
    return [], status


def known_items(root):
    manifest = read(root / "data/index.json")
    result = []
    for edition in manifest["editions"]:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", edition["date"]):
            result.extend(read(root / "data" / (edition["date"] + ".json"))["items"])
    return result


def deduplicate(candidates, history):
    seen, result = {}, []
    old_keys = {x.get("event_key") for x in history if x.get("event_key")}
    old_urls = {canonical(x["source_url"]) for x in history if x.get("source_url")}
    for item in candidates:
        url = canonical(item["source_url"])
        title = re.sub(r"[\W_]", "", item["title"].casefold())
        keys = ["url:" + url, "event:" + item["event_key"]]
        if len(title) > 24:
            keys.append("title:" + title)
        match = next((seen[k] for k in keys if k in seen), None)
        if match is not None:
            existing = result[match]
            for provenance in item["provenance"]:
                if provenance not in existing["provenance"]:
                    existing["provenance"].append(provenance)
            continue
        item["already_published"] = item["event_key"] in old_keys or url in old_urls
        for key in keys:
            seen[key] = len(result)
        result.append(item)
    return result


def collect(args):
    config = read(args.root / "config/sources.json")
    at = parse_time(args.at) if args.at else now()
    if at is None:
        raise ValueError("--at must include a timezone")
    sources = [s for s in config["sources"] if s.get("enabled", True) and (not args.sources or s["id"] in args.sources.split(","))]
    if not sources:
        raise ValueError("No matching enabled sources")
    candidates, statuses = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        tasks = {pool.submit(fetch_source, s, args.out, at, args.timeout): s for s in sources}
        for future in concurrent.futures.as_completed(tasks):
            source = tasks[future]
            rows, status = future.result()
            statuses.append(status)
            print(f"{source['id']}: {status['status']} ({len(rows)} entries)", flush=True)
            for row in rows[:60]:
                try:
                    url = canonical(row["source_url"])
                except (ValueError, KeyError):
                    continue
                published = parse_time(row.get("published_at"))
                age = (at - published).total_seconds() / 3600 if published else None
                # Keep undated discovery separately. Do not republish older or future records.
                if age is not None and (age < 0 or age > 7 * 24):
                    continue
                eligibility = "needs_date_check" if age is None else "news_window" if age <= 24 else "discovery_window"
                if eligibility == "discovery_window" and source["category"] not in {"开源项目", "研究"}:
                    continue
                key = row.get("event_key") or url
                score = round(source.get("priority", 70) / 5 + (20 if age is not None and age <= 24 else 8 if age is not None else 0) + {"official": 18, "independent": 18, "preprint": 12, "media": 8, "discovery": 0}.get(source["evidence_type"], 0))
                candidates.append({**row, "source_url": url, "title": plain(row["title"]), "excerpt": plain(row.get("excerpt"))[:2400],
                                   "candidate_id": hashlib.sha256(key.encode()).hexdigest()[:16], "event_key": key,
                                   "source_id": source["id"], "source_name": source["name"], "group": source["group"],
                                   "category": source["category"], "tags": source["tags"], "evidence_type": source["evidence_type"],
                                   "published_at": published.isoformat() if published else None,
                                   "discovered_at": at.isoformat(), "eligibility": eligibility, "heuristic_score": score,
                                   "provenance": [{"name": source["name"], "url": row.get("discovery_url", url), "source_id": source["id"]}],
                                   "requires_editorial_review": True})
    candidates.sort(key=lambda x: (-x["heuristic_score"], x["source_url"]))
    candidates = deduplicate(candidates, known_items(args.root))
    # Round-robin shortlists prevent prolific release feeds from hiding other families.
    groups = {}
    for item in candidates:
        if not item["already_published"]:
            groups.setdefault(item["group"], []).append(item)
    shortlist = []
    for i in range(5):
        for group in groups.values():
            if i < len(group):
                shortlist.append(group[i]["candidate_id"])
    report = {"schema_version": 2, "run_at": at.isoformat(), "window_start": (at - dt.timedelta(hours=24)).isoformat(),
              "window_end": at.isoformat(), "source_status": sorted(statuses, key=lambda s: s["id"]),
              "candidate_count": len(candidates), "shortlist": shortlist,
              "notes": ["自动排序只用于编辑初筛；影响与用途须阅读原文后判断。", "未注明日期的发现不能直接作为今日新闻；热度不是能力或质量证据。"]}
    write(args.out / "collection.json", report)
    write(args.out / "candidates.json", candidates)
    print(json.dumps({"sources": len(statuses), "failed": sum(s["status"] == "failed" for s in statuses), "candidates": len(candidates), "output": str(args.out)}, ensure_ascii=False))


def validate_edition(edition, strict=True):
    dt.date.fromisoformat(edition["date"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", edition["date"]), "Bad edition date"
    assert parse_time(edition["generated_at"]), "generated_at requires timezone"
    assert isinstance(edition["items"], list), "items must be a list"
    keys, urls, ids = set(), set(), set()
    for item in edition["items"]:
        for field in ["id", "event_key", "title", "summary", "impact", "source_name", "source_url"]:
            assert isinstance(item.get(field), str) and item[field].strip(), f"Missing {field}"
        assert item["event_key"] not in keys, "Duplicate event_key"
        keys.add(item["event_key"])
        assert item["id"] not in ids, "Duplicate item ID"
        ids.add(item["id"])
        url = canonical(item["source_url"])
        assert url not in urls, "Duplicate original URL"
        urls.add(url)
        for source in item.get("related_sources", []):
            canonical(source["url"])
        if strict:
            assert item["category"] in CATEGORIES, "Unknown category"
            assert item["verification"] in VERIFICATIONS, "Unknown verification"
            assert item.get("evidence_note"), "Evidence note required"
            assert item.get("editorial_reviewed") is True, "Unreviewed item"
            assert isinstance(item.get("tags"), list), "Tags required"
            assert parse_time(item.get("published_at")) or item.get("date_note"), "Unknown date needs explicit explanation"
            assert item.get("selection_reason"), "Editorial significance reason required"
            if item["category"] == "开源项目":
                canonical(item["repository_url"])
                for field in ["purpose", "audience", "license", "limitations"]:
                    assert item.get("project", {}).get(field), f"Missing project.{field}"
    return True


def prepare(args):
    incoming = read(args.edition)
    validate_edition(incoming)
    assert incoming.get("editorial_reviewed") is True, "Edition must be editorially reviewed"
    start, end = parse_time(incoming["window_start"]), parse_time(incoming["window_end"])
    assert start and end and start <= end, "Invalid reporting window"
    assert end.astimezone(TZ).date().isoformat() == incoming["date"], "Window must end on edition date in Beijing"
    for item in incoming["items"]:
        published = parse_time(item.get("published_at"))
        if published:
            assert published <= end, "Future publication date"
            if published < start:
                assert item.get("date_note"), "Older material must be explicitly dated as a lookback"
    source_config = read(args.root / "config/sources.json")
    manifest = read(args.root / "data/index.json")
    existing_path = args.root / "data" / (incoming["date"] + ".json")
    if existing_path.exists():
        existing = read(existing_path)
        old_items = {x["event_key"]: x for x in existing["items"]}
        for item in incoming["items"]:
            old = old_items.get(item["event_key"])
            if old and old != item:
                assert item.get("is_update") and item.get("change_note"), "Existing item change requires an explicit revision note"
            old_items[item["event_key"]] = item
        incoming["items"] = list(old_items.values())
        if existing.get("previous_revisions"):
            incoming["previous_revisions"] = existing["previous_revisions"]
        if incoming != existing:
            # A content hash is stable and collision-resistant, including multiple runs a day.
            digest = hashlib.sha256(existing_path.read_bytes()).hexdigest()[:16]
            revision = f"data/revisions/{incoming['date']}/{digest}.json"
            (args.out / revision).parent.mkdir(parents=True, exist_ok=True)
            (args.out / revision).write_bytes(existing_path.read_bytes())
            incoming["previous_revisions"] = list(dict.fromkeys(existing.get("previous_revisions", []) + [revision]))
    validate_edition(incoming, strict=False)
    manifest["schema_version"] = 2
    manifest["taxonomy_url"] = "./config/taxonomy.json"
    manifest["sources_url"] = "./config/sources.json"
    manifest["sources"] = [{k: s[k] for k in ["id", "name", "url", "role", "group", "format"]} for s in source_config["sources"] if s.get("enabled", True)]
    entry = {"date": incoming["date"], "title": incoming["title"], "count": len(incoming["items"])}
    manifest["editions"] = sorted([x for x in manifest["editions"] if x["date"] != incoming["date"]] + [entry], key=lambda x: x["date"], reverse=True)
    write(args.out / "data" / (incoming["date"] + ".json"), incoming)
    write(args.out / "data/index.json", manifest)
    print(f"Prepared {len(incoming['items'])} items in {args.out}; remote repository unchanged.")


def validate_site(root):
    manifest = read(root / "data/index.json")
    dates = set()
    for entry in manifest["editions"]:
        assert entry["date"] not in dates, "Duplicate archive date"
        dates.add(entry["date"])
        edition = read(root / "data" / (entry["date"] + ".json"))
        assert edition["date"] == entry["date"], "Archive date mismatch"
        validate_edition(edition, strict=False)
        assert entry["count"] == len(edition["items"]), "Manifest count mismatch"
    sources = read(root / "config/sources.json")["sources"]
    assert len({s["id"] for s in sources}) == len(sources), "Duplicate source IDs"
    for source in sources:
        canonical(source["url"])
        canonical(source["fetch_url"])
        assert source["format"] in FORMATS, "Unsupported source format"
    print(f"Validated {len(dates)} archive dates and {len(sources)} sources.")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    c = commands.add_parser("collect")
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--at")
    c.add_argument("--sources", help="Optional comma-separated source IDs for diagnostics")
    c.add_argument("--workers", type=int, default=6)
    c.add_argument("--timeout", type=int, default=18)
    p = commands.add_parser("prepare")
    p.add_argument("--edition", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    commands.add_parser("validate")
    args = parser.parse_args()
    try:
        if args.command == "collect":
            collect(args)
        elif args.command == "prepare":
            prepare(args)
        else:
            validate_site(args.root)
    except (ValueError, AssertionError, KeyError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
