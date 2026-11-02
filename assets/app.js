'use strict';
const $ = id => document.getElementById(id);
const DEFAULT_CATEGORIES = ['模型与产品 · 前沿进展', '开源项目', '研究', '行业动态'];
const LEGACY_FRONTIER = ['模型与产品', '编程与Agent', '多模态', '榜单与评测'];
let categories = [...DEFAULT_CATEGORIES];
let manifest = null, current = null, category = '全部', loadId = 0, loading = true, loadError = false;

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = String(text);
  return node;
}
function values(value) { return Array.isArray(value) ? value.filter(x => typeof x === 'string') : typeof value === 'string' && value ? [value] : []; }
function text(value) { return values(value).join('、'); }
function link(label, url) {
  try {
    const u = new URL(url);
    if (!['https:', 'http:'].includes(u.protocol) || u.username || u.password) return el('span', '', label);
    const a = el('a', '', label);
    a.href = u.href; a.target = '_blank'; a.rel = 'noopener noreferrer';
    return a;
  } catch { return el('span', '', label); }
}
function dateText(value) {
  if (!value) return '时间未标注';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '时间未确认';
  return new Intl.DateTimeFormat('zh-CN', {timeZone:'Asia/Shanghai', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false}).format(d);
}
function itemCategory(item) {
  if (LEGACY_FRONTIER.includes(item.category)) return DEFAULT_CATEGORIES[0];
  if (item.category === '开源与研究') return item.repository_url ? '开源项目' : '研究';
  if (item.category === '行业') return '行业动态';
  return categories.includes(item.category) ? item.category : '行业动态';
}
function itemTags(item) {
  const tags = [...values(item.tags), ...values(item.models)];
  if (item.category && item.category !== itemCategory(item)) tags.unshift(item.category);
  return [...new Set(tags)];
}
function searchable(item) {
  const project = item.project && typeof item.project === 'object' ? item.project : {};
  return [item.title, item.summary, item.impact, item.category, itemCategory(item), item.verification,
    item.evidence_note, item.source_name, item.repository_url, ...itemTags(item),
    ...['purpose','audience','license','limitations'].map(k => text(project[k]))].filter(Boolean).join(' ').toLowerCase();
}
async function json(path) {
  const response = await fetch(path, {cache:'no-store'});
  if (!response.ok) throw new Error('HTTP ' + response.status);
  return response.json();
}
function notice(message) { $('notice').textContent = message; $('notice').style.display = message ? 'block' : 'none'; }
function empty(title, message, reset = false) {
  const n = el('div', 'empty'); n.append(el('h2', '', title), el('p', '', message));
  if (reset) {
    const button = el('button', 'reset', '清除筛选'); button.type = 'button';
    button.onclick = () => {category = '全部'; $('search').value = ''; $('tag-filter').value = ''; render();};
    n.append(button);
  }
  $('stories').replaceChildren(n);
}
function sourceState(source) {
  const states = Array.isArray(current?.source_status) ? current.source_status : [];
  return (source.id && states.find(x => (x.id || x.source_id) === source.id)) || states.find(x => x.name === source.name);
}
function renderSources() {
  const sources = Array.isArray(manifest?.sources) ? manifest.sources : [];
  const groups = new Map();
  for (const source of sources) {
    const group = source.group || '综合信息源';
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(source);
  }
  $('sources').replaceChildren();
  for (const [name, entries] of groups) {
    const group = el('details', 'source-group');
    group.open = sources.length <= 8;
    const groupLabels = {official:'官方发布', projects:'开源项目', research:'论文与研究', news:'新闻与开发者', evaluation:'独立评测', discovery:'社区发现'};
    const summary = el('summary', '', groupLabels[name] || name); summary.append(el('span', '', entries.length + ' 个'));
    group.append(summary);
    for (const source of entries) {
      const row = el('div', 'source'), left = el('div');
      left.append(link(source.name || source.id || '信息源', source.url), el('small', '', source.role || ''));
      const state = sourceState(source);
      const labels = {ok:'已抓取', unchanged:'未发现更新', failed:'抓取失败', partial:'部分抓取'};
      const status = state?.status;
      const label = state ? labels[status] || '状态未确认' : current ? '本期未记录' : loading ? '等待读取' : '未检查';
      const right = el('span', 'source-state' + (status === 'failed' ? ' bad' : status === 'partial' ? ' partial' : ''), label);
      if (state?.note) {right.title = state.note; left.append(el('p', 'source-note', state.note));}
      if (state?.checked_at) left.append(el('small', '', '检查 ' + dateText(state.checked_at)));
      row.append(left, right); group.append(row);
    }
    $('sources').append(group);
  }
  if (!sources.length) $('sources').append(el('p', 'source-note', '目录尚未提供来源配置。'));
  if (!current) {$('source-coverage').textContent = loading ? '正在读取本期来源记录…' : '没有本期来源记录。'; return;}
  const counts = {ok:0, unchanged:0, failed:0, partial:0, missing:0};
  for (const source of sources) {const status = sourceState(source)?.status; counts[Object.hasOwn(counts, status) ? status : 'missing']++;}
  const parts = ['来源 ' + sources.length + ' 个'];
  if (counts.ok) parts.push('已抓取 ' + counts.ok);
  if (counts.unchanged) parts.push('未发现更新 ' + counts.unchanged);
  if (counts.partial) parts.push('部分抓取 ' + counts.partial);
  if (counts.failed) parts.push('失败 ' + counts.failed);
  if (counts.missing) parts.push('未记录 ' + counts.missing);
  $('source-coverage').textContent = parts.join(' · ') + '。抓取状态不代表逐条核实。';
}
function renderFilters() {
  $('filters').replaceChildren();
  for (const name of ['全部', ...categories]) {
    const b = el('button', '', name); b.type = 'button'; b.setAttribute('aria-pressed', String(name === category));
    b.onclick = () => {category = name; render();}; $('filters').append(b);
  }
}
function renderTags() {
  const tags = [...new Set((current?.items || []).flatMap(itemTags))].sort((a,b) => a.localeCompare(b, 'zh-CN'));
  const all = el('option', '', '全部标签'); all.value = '';
  $('tag-filter').replaceChildren(all);
  for (const tag of tags) {const option = el('option', '', tag); option.value = tag; $('tag-filter').append(option);}
  $('tag-filter').value = ''; $('tag-filter').disabled = !tags.length;
}
function renderProject(item, card) {
  const project = item.project && typeof item.project === 'object' ? item.project : {};
  const fields = [['purpose','用途'],['audience','适合谁'],['license','许可证'],['limitations','局限']];
  const available = fields.filter(([key]) => text(project[key]));
  if (!available.length && !project.quick_start_url && itemCategory(item) !== '开源项目') return;
  const details = el('details', 'project'); details.open = itemCategory(item) === '开源项目';
  details.append(el('summary', '', '项目介绍与使用条件'));
  if (available.length) {
    const list = el('dl');
    for (const [key, label] of available) list.append(el('dt', '', label), el('dd', '', text(project[key])));
    details.append(list);
  } else details.append(el('p', 'source-note', '项目介绍尚未补充，请先查看原始仓库说明。'));
  if (project.quick_start_url) {const links = el('div', 'links'); links.append(link('快速开始 ↗', project.quick_start_url)); details.append(links);}
  card.append(details);
}
function render() {
  document.querySelectorAll('#filters button').forEach(b => b.setAttribute('aria-pressed', String(b.textContent === category)));
  $('stories').setAttribute('aria-busy', String(loading));
  if (loading || loadError) return;
  if (!current) {$('count').textContent = ''; empty('首篇日报尚未发布', '目录中还没有日报。发布后可在这里按日期回看，并打开原始来源。'); return;}
  const query = $('search').value.trim().toLowerCase(), tag = $('tag-filter').value;
  const items = current.items.filter(item => (category === '全部' || itemCategory(item) === category) &&
    (!tag || itemTags(item).includes(tag)) && (!query || searchable(item).includes(query)));
  $('count').textContent = '本期 ' + current.items.length + ' 条 · 当前显示 ' + items.length + ' 条';
  $('stories').replaceChildren();
  if (!items.length) {
    empty(current.items.length ? '没有匹配的内容' : '本期暂无收录条目', current.items.length ?
      '可清除筛选，或换一个关键词继续查看。' : '暂无条目不表示所有来源都没有新消息。来源覆盖、抓取限制与本期说明见右侧。', Boolean(current.items.length));
    return;
  }
  for (const item of items) {
    const card = el('article', 'card'), meta = el('div', 'meta');
    meta.append(el('span', 'tag', itemCategory(item)), el('span', 'verify', item.verification || '待核实'));
    const published = item.published_at || item.published_date;
    if (published) meta.append(el('span', '', '发布 ' + String(published).slice(0,10)));
    const event = item.event_date || item.event_at;
    if (event && String(event).slice(0,10) !== String(published || '').slice(0,10)) meta.append(el('span', '', '事件 ' + String(event).slice(0,10)));
    if (item.is_update) meta.append(el('span', '', '补充更新'));
    card.append(meta, el('h2', '', item.title || '未命名条目'), el('p', 'summary', item.summary || '摘要尚未提供，请查看原始来源。'));
    const tags = itemTags(item);
    if (tags.length) {const row = el('div', 'subtags'); for (const tag of tags) row.append(el('span', 'subtag', tag)); card.append(row);}
    if (item.impact) {const p = el('p', 'impact'); p.append(el('strong', '', '为什么重要 · '), document.createTextNode(item.impact)); card.append(p);}
    if (item.evidence_note) card.append(el('p', 'evidence', '证据说明 · ' + item.evidence_note));
    if (item.date_note) card.append(el('p', 'evidence', '时间说明 · ' + item.date_note));
    renderProject(item, card);
    const links = el('div', 'links');
    if (item.repository_url) links.append(link('原始仓库 ↗', item.repository_url));
    if (item.source_url) links.append(link((item.source_name || '原始来源') + ' ↗', item.source_url));
    for (const source of Array.isArray(item.related_sources) ? item.related_sources : []) links.append(link((source.name || '补充来源') + ' ↗', source.url));
    if (links.childNodes.length) card.append(links);
    $('stories').append(card);
  }
}
async function loadEdition(date, initialNotice = '') {
  const id = ++loadId;
  notice(initialNotice); current = null; category = '全部'; loading = true; loadError = false;
  $('search').value = ''; renderTags(); renderFilters();
  $('updated').textContent = '正在读取 ' + date; $('coverage').textContent = '';
  $('brief').textContent = '正在读取本期速览…'; $('notes').replaceChildren(); $('count').textContent = '';
  $('headline').textContent = date + ' · AI 日报'; $('intro').textContent = '正在读取所选日期的归档。';
  $('stories').setAttribute('aria-busy', 'true'); empty('正在读取日报', '正在加载 ' + date + ' 的归档。'); renderSources();
  try {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error('日期格式无效');
    const data = await json('./data/' + date + '.json');
    if (id !== loadId) return;
    if (data.date !== date || !Array.isArray(data.items) || data.items.some(x => !x || typeof x !== 'object')) throw new Error('日报数据格式无效');
    current = data; loading = false;
    $('headline').textContent = data.title || date + ' · AI 日报';
    $('intro').textContent = data.summary || '固定来源汇总，保留原文链接。'; $('brief').textContent = data.summary || '本期内容见左侧。';
    $('updated').textContent = '生成于 ' + dateText(data.generated_at);
    $('coverage').textContent = '本期 ' + data.date + ' · ' + data.items.length + ' 条';
    for (const note of values(data.notes)) $('notes').append(el('li', '', note));
    for (const revision of values(data.previous_revisions)) {
      if (/^data\/revisions\/\d{4}-\d{2}-\d{2}\/[a-f0-9]+\.json$/.test(revision)) {
        const li = el('li'); li.append(link('查看本期先前版本（原始记录）', new URL('./' + revision, location.href).href)); $('notes').append(li);
      }
    }
    const sources = manifest.sources || [];
    const incomplete = sources.filter(source => !['ok','unchanged'].includes(sourceState(source)?.status));
    if (incomplete.length) {
      const message = '本期有 ' + incomplete.length + ' 个来源抓取不完整、失败或未记录，覆盖可能不全。列表读取成功也不代表逐条新闻已核实。';
      notice([initialNotice, message].filter(Boolean).join(' '));
    }
    document.title = data.date + ' · AI 日报';
    const u = new URL(location.href); u.searchParams.set('date', date); history.replaceState(null, '', u);
    renderTags(); renderSources(); render();
  } catch (error) {
    if (id !== loadId) return;
    current = null; loading = false; loadError = true;
    $('stories').setAttribute('aria-busy', 'false');
    empty('本期日报暂时无法读取', '请稍后刷新，或选择其他归档日期。当前不能判断本期是否有更新。');
    $('updated').textContent = '本期读取失败'; $('coverage').textContent = ''; $('count').textContent = '';
    $('intro').textContent = '所选日期暂时不可用。'; $('brief').textContent = '读取失败，不能判断本期是否有更新。';
    renderSources(); notice('归档读取失败：' + error.message);
  }
}
async function init() {
  renderFilters(); renderTags();
  $('search').addEventListener('input', render);
  $('tag-filter').addEventListener('change', render);
  $('edition').addEventListener('change', () => loadEdition($('edition').value));
  try {
    // A missing optional taxonomy must never prevent existing archives from loading.
    const [index, taxonomy] = await Promise.all([json('./data/index.json'), json('./config/taxonomy.json').catch(() => null)]);
    manifest = index;
    if (!Array.isArray(manifest.editions) || !Array.isArray(manifest.sources)) throw new Error('日报目录格式无效');
    const configured = Array.isArray(taxonomy?.categories) ? taxonomy.categories.map(x => typeof x === 'string' ? x : x?.name || x?.label).filter(Boolean) : [];
    if (DEFAULT_CATEGORIES.every(name => configured.includes(name))) categories = [...new Set(configured)].filter(name => DEFAULT_CATEGORIES.includes(name));
    renderFilters();
    const editions = manifest.editions.filter(x => x && /^\d{4}-\d{2}-\d{2}$/.test(x.date)).sort((a,b) => b.date.localeCompare(a.date));
    $('edition').replaceChildren(); renderSources();
    if (!editions.length) {
      loading = false; $('edition').append(el('option', '', '尚无已发布日报')); $('updated').textContent = '尚无已发布日报';
      renderSources(); render(); return;
    }
    for (const edition of editions) {
      const option = el('option', '', edition.date + (Number.isFinite(edition.count) ? ' · ' + edition.count + ' 条' : ''));
      option.value = edition.date; $('edition').append(option);
    }
    $('edition').disabled = false;
    const requested = new URLSearchParams(location.search).get('date');
    const selected = editions.some(x => x.date === requested) ? requested : editions[0].date;
    $('edition').value = selected;
    await loadEdition(selected, requested && requested !== selected ? '未找到所选日期的归档，已显示最新一期。' : '');
  } catch (error) {
    loading = false; loadError = true; $('stories').setAttribute('aria-busy', 'false');
    $('edition').replaceChildren(el('option', '', '归档暂时不可用')); $('updated').textContent = '归档读取失败';
    $('brief').textContent = '目录读取失败，无法判断已发布内容。';
    empty('暂时无法读取日报目录', '请刷新重试。当前没有可验证的目录数据，不能据此判断是否存在日报。');
    notice('目录读取失败：' + error.message);
  }
}
init();
