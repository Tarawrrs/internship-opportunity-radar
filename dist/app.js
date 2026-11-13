"use strict";

const $ = id => document.getElementById(id);
const repo = "https://github.com/Tarawrrs/internship-opportunity-radar";
const timeZone = "Asia/Taipei";
const winterLabels = {
  "winter-only": "寒假限定", extends: "寒假開始、延續到學期", flexible: "起聘或結束日待確認",
};
const actionLabels = { saved: "收藏", applied: "已申請", dismissed: "略過" };
const state = {
  career: null, academic: null, actions: loadActions(), route: "", paperLimit: 20, feedbackTimer: 0,
};

function loadActions() {
  try {
    return JSON.parse(localStorage.getItem("radar_actions_v1")) || {};
  } catch {
    return {};
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function link(href, label, style = "") {
  let url;
  try {
    url = new URL(href);
  } catch {
    return escapeHtml(label);
  }
  if (url.protocol !== "https:") return escapeHtml(label);
  return `<a class="${style}" href="${escapeHtml(url.href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
}

function dateInTaipei() {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" })
    .formatToParts(new Date());
  return ["year", "month", "day"].map(key => parts.find(part => part.type === key).value).join("-");
}

function taipeiTime() {
  return new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date());
}

function shortDate(value) {
  const [, month, day] = String(value ?? "").split("-");
  return month && day ? `${Number(month)}/${Number(day)}` : "";
}

function scanTime(value) {
  const time = Date.parse(value);
  if (!Number.isFinite(time)) return "尚無紀錄";
  return new Intl.DateTimeFormat("zh-TW", { timeZone, dateStyle: "short", timeStyle: "short", hour12: false }).format(time);
}

function empty(message) {
  return `<p class="empty">${escapeHtml(message)}</p>`;
}

function tag(label, tone = "") {
  return `<span class="tag ${tone}">${escapeHtml(label)}</span>`;
}

function meta(values) {
  return escapeHtml(values.filter(Boolean).join(" · "));
}

function isOpen(job, today = dateInTaipei(), now = taipeiTime()) {
  return !job.deadline || job.deadline > today ||
    (job.deadline === today && (!job.deadlineTime || job.deadlineTime > now));
}

function upcoming() {
  const today = dateInTaipei();
  const now = taipeiTime();
  return (state.academic?.events || []).filter(item =>
    (item.endDate || item.date) >= today &&
    ((item.endDate || item.date) !== today || !(item.endTime || item.time) || (item.endTime || item.time) >= now)
  );
}

function isWinter(job) {
  return job.winterYear === state.career?.meta.winter_year && Boolean(winterLabels[job.winterStatus]);
}

function runLink(run) {
  return /^\d+$/.test(run?.id ?? "") ? link(`${repo}/actions/runs/${run.id}`, "GitHub 執行紀錄 ↗") : "";
}

function eventLabel(event) {
  return { schedule: "排程觸發", workflow_dispatch: "手動觸發", local: "本機預掃描" }[event] || "觸發方式未提供";
}

function eventRow(item, compact = false) {
  const dates = item.endDate && item.endDate !== item.date ? `${shortDate(item.date)}–${shortDate(item.endDate)}` : shortDate(item.date);
  const times = [item.time, item.endTime].filter(Boolean).join("–");
  return `<article class="row">
    <div class="date-block"><time datetime="${escapeHtml(item.date)}">${escapeHtml(dates)}</time><small>${escapeHtml(compact ? item.time : times)}</small></div>
    <div class="row-main">
      <h3>${link(item.url, item.title, "row-title")}</h3>
      <p class="meta">${meta([item.sourceName, item.venue, compact ? "" : item.speaker])}</p>
      ${compact && !item.stale ? "" : `<div class="tags">${item.stale ? tag("請向主辦方確認", "warn") : ""}
        ${compact ? "" : [item.type, ...item.topics].map(label => tag(label)).join("")}</div>`}
    </div>
  </article>`;
}

function paperRow(item, compact = false) {
  const stamp = item.dateLabel === "出版月份" ? item.date.slice(0, 7) : shortDate(item.date);
  const people = (item.authors || []).join("、");
  return `<article class="row">
    <div class="date-block"><time datetime="${escapeHtml(item.date)}">${escapeHtml(stamp)}</time><small>${escapeHtml(item.dateLabel)}</small></div>
    <div class="row-main">
      <h3>${link(item.url, item.title, "row-title")}</h3>
      <p class="meta">${meta([item.type, item.sourceName, compact ? "" : people])}</p>
      ${compact ? "" : `<div class="tags">${item.topics.map(label => tag(label)).join("")}</div>`}
    </div>
  </article>`;
}

function jobRow(job, field) {
  const winter = isWinter(job) ? winterLabels[job.winterStatus] : "";
  const date = job[field];
  return `<article class="row">
    <div class="date-block ${date ? "" : "undated"}">${date ? `<time datetime="${escapeHtml(date)}">${shortDate(date)}</time>` : "隨到隨審"}
      <small>${escapeHtml(field === "firstSeen" ? "首次找到" : job.deadlineTime || "")}</small></div>
    <div class="row-main">
      <h3>${link(job.source, job.title, "row-title")}</h3>
      <p class="meta">${meta([job.company, field === "deadline" ? winter : job.location])}</p>
    </div>
  </article>`;
}

function renderOverview() {
  const today = dateInTaipei();
  $("today-label").textContent = new Intl.DateTimeFormat("zh-TW", {
    timeZone, year: "numeric", month: "long", day: "numeric", weekday: "long",
  }).format(new Date());
  $("overview-events").innerHTML = upcoming().slice(0, 4).map(item => eventRow(item, true)).join("") ||
    empty(state.academic ? "目前沒有已確認日期的近期活動。" : "讀取學術活動中。");
  $("overview-papers").innerHTML = (state.academic?.papers || []).slice(0, 3).map(item => paperRow(item, true)).join("") ||
    empty(state.academic ? "目前沒有新研究紀錄。" : "讀取研究紀錄中。");
  const jobs = (state.career?.jobs || []).filter(job => isOpen(job, today) && state.actions[job.id] !== "dismissed");
  const winter = jobs.filter(isWinter).sort(compareDeadlines);
  const firstSeen = jobs.filter(job => wasRecentlyFound(job, today)).sort(compareDiscovery);
  const year = state.career?.meta.winter_year;
  $("winter-overview").textContent = year ? `${year} 寒假 · ${winter.length} 筆目前機會` : "";
  $("overview-jobs").innerHTML = winter.slice(0, 4).map(job => jobRow(job, "deadline")).join("") ||
    empty(state.career ? "目前沒有符合地點和期間的寒假機會。" : "讀取寒假機會中。");
  $("overview-new").innerHTML = firstSeen.slice(0, 3).map(job => jobRow(job, "firstSeen")).join("") ||
    empty(state.career ? "近七天沒有首次找到且仍開放的職缺。" : "讀取職缺中。");
}

function setCurrent(selector, dataKey, selected) {
  for (const element of document.querySelectorAll(selector)) {
    if (element.dataset[dataKey] === selected) element.setAttribute("aria-current", "page");
    else element.removeAttribute("aria-current");
  }
}

function renderAcademic() {
  const papers = state.route === "papers";
  setCurrent("[data-academic]", "academic", papers ? "papers" : "events");
  $("institution-filter").hidden = papers;
  $("paper-type-filter").hidden = !papers;
  $("academic-list-heading").textContent = papers ? "近期研究" : "近期活動";
  const query = $("academic-query").value.trim().toLocaleLowerCase();
  const topic = $("academic-topic").value;
  const institution = $("academic-institution").value;
  const paperType = $("academic-paper-type").value;
  const items = (papers ? state.academic?.papers || [] : upcoming()).filter(item => {
    const text = [item.title, item.sourceName, item.venue, item.speaker, ...(item.authors || []), ...item.topics].join(" ").toLocaleLowerCase();
    return (!topic || item.topics.includes(topic)) && text.includes(query) &&
      (papers ? !paperType || item.type === paperType : !institution || item.institution === institution);
  });
  $("academic-count").textContent = state.academic ? `${items.length} 筆` : "";
  $("academic-list").innerHTML = (papers ? items.slice(0, state.paperLimit).map(item => paperRow(item)) :
    items.map(item => eventRow(item))).join("") ||
    empty(state.academic ? "沒有符合目前篩選條件的資料。" : "讀取學術資料中。");
  $("more-papers").hidden = !papers || items.length <= state.paperLimit;
}

function compareDeadlines(a, b) {
  const date = job => job.deadline ? `${job.deadline} ${job.deadlineTime || "23:59"}` : "9999";
  return date(a).localeCompare(date(b)) || (b.score || 0) - (a.score || 0);
}

function compareDiscovery(a, b) {
  return (b.firstSeen || "").localeCompare(a.firstSeen || "") || compareDeadlines(a, b);
}

function wasRecentlyFound(job, today) {
  const elapsed = Date.parse(today) - Date.parse(job.firstSeen);
  return elapsed >= 0 && elapsed < 7 * 86400000;
}

function jobCard(job, archived, showActions) {
  const status = state.actions[job.id];
  const actions = !showActions ? "" : `<div class="actions" aria-label="處理職缺">
    ${Object.entries(actionLabels).filter(([key]) => !archived || key === status).map(([key, label]) =>
      `<button type="button" class="action" data-job="${escapeHtml(job.id)}" data-action="${key}" aria-pressed="${status === key}">${label}</button>`).join("")}
  </div>`;
  const dates = [
    job.postedAt && `刊登 ${job.postedAt}`, job.firstSeen && `首次找到 ${job.firstSeen}`,
    job.sourceKey?.startsWith("manual-leads:") ? job.checked && `人工查核 ${job.checked}` : job.lastSeen && `最後查到 ${job.lastSeen}`,
    job.sourceUpdatedAt && !job.sourceKey?.startsWith("manual-leads:") && `來源更新 ${job.sourceUpdatedAt}`,
  ];
  const tags = [
    tag(job.track === "research" ? "研究型" : "商業型"),
    job.jobType && tag(job.jobType),
    isWinter(job) && tag(winterLabels[job.winterStatus], "accent"),
    job.verificationStatus === "pending" && !archived && tag("待查核", "warn"),
    archived && tag("歷史紀錄"),
  ];
  const deadline = job.deadline ? `<time datetime="${escapeHtml(job.deadline)}">截止 ${escapeHtml(job.deadline)}${job.deadlineTime ? ` ${escapeHtml(job.deadlineTime)}` : ""}</time>` :
    (archived ? "" : `<span class="meta">${job.timing?.startsWith("公告採") ? "隨到隨審" : "未列截止日"}</span>`);
  return `<article class="panel job">
    <div class="job-top">
      <div>
        <h3>${link(job.source, job.title, "row-title")}</h3>
        <p class="meta">${meta([job.company, job.location])}</p>
        <div class="tags">${tags.filter(Boolean).join("")}</div>
      </div>
      ${actions}
    </div>
    ${job.period ? `<p class="job-period"><strong>期間／工時</strong> ${escapeHtml(job.period)}</p>` : ""}
    ${job.note ? `<p class="row-detail">${escapeHtml(job.note)}</p>` : ""}
    ${job.verificationNote && !archived ? `<p class="row-detail">${escapeHtml(job.verificationNote)}</p>` : ""}
    <div class="job-footer">
      ${deadline}
      ${link(job.source, "原公告 ↗")}
      ${job.applicationUrl && !archived ? link(job.applicationUrl, "申請頁 ↗") : ""}
    </div>
    <details>
      <summary>${archived ? "封存紀錄" : "資格與搜尋紀錄"}</summary>
      ${job.eligibility ? `<p>${escapeHtml(job.eligibility)}</p>` : ""}
      ${job.skills?.length ? `<p>相關技能 ${escapeHtml(job.skills.join("、"))}</p>` : ""}
      ${job.archiveReason && archived ? `<p>${escapeHtml(job.archiveReason)} ${escapeHtml(job.archivedAt)}</p>` : ""}
      <p>${meta([job.sourceName, ...dates])}</p>
    </details>
  </article>`;
}

function renderCareer() {
  const controls = {
    query: $("job-query").value.trim().toLocaleLowerCase(), track: $("job-track").value, season: $("job-season").value,
    location: $("job-location").value, list: $("job-state").value, sort: $("job-sort").value,
  };
  const data = state.career;
  const today = dateInTaipei();
  const now = taipeiTime();
  const all = [...(data?.jobs || []), ...(data?.review || []), ...(data?.archive || [])];
  const shown = all.filter(job => {
    const status = state.actions[job.id];
    const archived = job.status === "archived" || job.archived;
    const active = !archived && isOpen(job, today, now);
    const review = job.status === "review";
    const lists = {
      archive: archived, saved: status === "saved", applied: status === "applied", dismissed: status === "dismissed",
      review: active && review && status !== "dismissed", active: active && !review && status !== "dismissed",
      new: active && !review && status !== "dismissed" && wasRecentlyFound(job, today),
    };
    const season = controls.season === "all" || (isWinter(job) && (controls.season === "winter" || job.winterStatus === controls.season));
    const track = !controls.track || controls.track === (job.track === "research" ? "research" : "business");
    const location = !controls.location || job.locationKey === controls.location;
    const text = [job.title, job.company, job.location, job.jobType, job.period, ...(job.skills || [])].join(" ").toLocaleLowerCase();
    return lists[controls.list] && season && track && location && text.includes(controls.query);
  });
  const sorting = { deadline: compareDeadlines, new: compareDiscovery, fit: (a, b) => (b.score || 0) - (a.score || 0) };
  if (controls.list !== "archive") shown.sort(sorting[controls.sort]);
  $("job-list-heading").textContent = $("job-state").selectedOptions[0].textContent;
  $("job-count").textContent = data ? `${shown.length} 筆` : "";
  const year = data?.meta.winter_year;
  let note = "收藏、已申請和略過狀態儲存在這個瀏覽器。";
  if (year && controls.season !== "all") {
    note = year === 2027 ? "2027 寒假依台大行事曆（12/28–2/19）。" : `${year} 寒假以 1–2 月估計。`;
  }
  $("career-note").textContent = note;
  $("job-list").innerHTML = shown.map(job =>
    jobCard(job, job.status === "archived" || job.archived, job.status !== "archived" || Boolean(state.actions[job.id]))
  ).join("") || `<div class="panel">${empty(data ? "沒有符合目前篩選條件的職缺。" : "讀取職缺中。")}</div>`;
}

function sourceRow(source) {
  const status = source.manual ? "人工查核" : { ok: "已讀取", partial: "部分讀取", error: "讀取失敗" }[source.status] || "無狀態";
  const found = source.group ? source.matches : (source.active || 0);
  const count = source.manual ? `待查核 ${source.review || 0} 筆` : source.status === "error" ? "" : `讀取 ${source.examined || 0} 筆 · 收錄 ${found || 0} 筆`;
  const issues = (source.issues || []).join("；");
  return `<div class="row source-row">
    <div class="row-main">${link(source.url, source.source, "row-title")}<p class="meta">${meta([count, issues])}</p></div>
    ${tag(status, source.status === "ok" ? "accent" : "warn")}
  </div>`;
}

function renderSources() {
  const career = state.career?.meta;
  const academic = state.academic;
  const careerSources = career?.sources || [];
  const academicSources = academic?.sources || [];
  const sourceIssues = [...careerSources, ...academicSources].filter(source => source.status !== "ok").length;
  const timestamp = career?.last_scan_attempt || academic?.last_scan_attempt;
  const overdue = !timestamp || Date.now() - Date.parse(timestamp) >= 40 * 3600 * 1000;
  const schedule = career?.last_schedule;
  const scheduleOverdue = schedule && Date.now() - Date.parse(schedule.finished) >= 32 * 3600 * 1000;
  const header = $("scan-link");
  const pending = !career || !academic;
  header.classList.toggle("ok", !pending && schedule && !overdue && !scheduleOverdue && sourceIssues === 0);
  header.classList.toggle("warn", !pending && (overdue || scheduleOverdue || sourceIssues > 0 || !schedule));
  const trigger = career?.run?.event === "schedule" ? "排程掃描" : "最近掃描";
  $("scan-label").textContent = !timestamp ? "掃描紀錄" :
    overdue ? "資料逾時 · 查看紀錄" : scheduleOverdue ? "排程逾時 · 查看紀錄" :
    sourceIssues ? `${sourceIssues} 個來源異常` : !schedule ? "排程待驗證" : `${trigger} ${scanTime(timestamp)}`;
  $("job-sources").innerHTML = careerSources.map(sourceRow).join("") || empty("尚無職涯來源紀錄。");
  $("academic-sources").innerHTML = academicSources.map(sourceRow).join("") || empty("尚無學術來源紀錄。");
  const history = (career?.history || []).map(run => `<tr>
    <td>${escapeHtml(scanTime(run.finished))}</td><td>${eventLabel(run.event)}</td>
    <td>${Number(run.examined).toLocaleString("zh-TW")}</td><td>${Number(run.new)}</td><td>${runLink(run)}</td></tr>`).join("");
  $("source-scan-summary").innerHTML = `
    <p><strong>最近職涯掃描</strong> ${escapeHtml(scanTime(career?.last_scan_attempt))} · ${eventLabel(career?.run?.event)}
      ${career ? ` · 讀取 ${Number(career.records_examined).toLocaleString("zh-TW")} 筆 · 首次找到 ${Number(career.new_count)} 筆` : ""}
      ${runLink(career?.run)}</p>
    <p><strong>最近排程觸發</strong> ${schedule ? `${escapeHtml(scanTime(schedule.finished))} ${runLink(schedule)}` : "等待此版本的第一次排程掃描"}</p>
    <p><strong>最近學術掃描</strong> ${escapeHtml(scanTime(academic?.last_scan_attempt))}
      ${academic ? ` · ${upcoming().length} 場活動 · ${academic.papers.length} 筆研究` : ""}</p>
    ${history ? `<details><summary>最近掃描明細</summary><table><thead><tr>
      <th>完成時間</th><th>觸發</th><th>讀取</th><th>首次找到</th><th>紀錄</th></tr></thead><tbody>${history}</tbody></table></details>` : ""}
  `;
}

function route() {
  const fragment = location.hash.slice(1);
  if (fragment === "main") return;
  const valid = ["overview", "events", "papers", "career", "career-new", "archive", "sources"];
  const next = valid.includes(fragment) ? fragment : "overview";
  if (next === state.route) {
    if (fragment === "career" && $("job-state").value !== "active") {
      $("job-state").value = "active";
      $("job-season").value = "winter";
      renderCareer();
    }
    return;
  }
  const old = state.route;
  state.route = next;
  const page = ["events", "papers"].includes(next) ? "academic" :
    ["career", "career-new", "archive"].includes(next) ? "career" : next;
  for (const view of document.querySelectorAll("[data-view]")) view.hidden = view.dataset.view !== page;
  setCurrent("[data-nav]", "nav", page);
  if (page === "career") {
    $("job-state").value = { career: "active", "career-new": "new", archive: "archive" }[next];
    $("job-season").value = next === "career" ? "winter" : "all";
  }
  render();
  if (old) {
    $(`${page}-heading`).focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }
}

function render() {
  renderSources();
  if (state.route === "overview") renderOverview();
  else if (["events", "papers"].includes(state.route)) renderAcademic();
  else if (["career", "career-new", "archive"].includes(state.route)) renderCareer();
}

async function readData(file) {
  const response = await fetch(`./data/${file}.json`, { cache: "no-store" });
  if (!response.ok) throw new Error(file);
  return response.json();
}

async function load() {
  $("reload").disabled = true;
  const [career, academic] = await Promise.allSettled([
    Promise.all(["jobs", "review", "archive", "scan-meta"].map(readData)),
    readData("academic"),
  ]);
  const failed = [];
  if (career.status === "fulfilled") {
    const [jobs, review, archive, meta] = career.value;
    state.career = { jobs, review, archive, meta };
  } else failed.push("職涯");
  if (academic.status === "fulfilled") {
    state.academic = academic.value;
    const menu = $("academic-topic");
    const current = menu.value;
    for (const option of Array.from(menu.options).slice(1)) option.remove();
    for (const topic of state.academic.topics) {
      const option = document.createElement("option");
      option.textContent = topic;
      option.value = topic;
      menu.append(option);
    }
    menu.value = [...menu.options].some(option => option.value === current) ? current : "";
  } else failed.push("學術");
  $("load-error").hidden = !failed.length;
  $("load-error").textContent = failed.length ? `${failed.join("、")}資料讀取失敗。請到「來源與掃描紀錄」重新讀取。` : "";
  $("reload").disabled = false;
  render();
}

document.querySelectorAll("#view-academic .filters input, #view-academic .filters select").forEach(control => {
  control.addEventListener("input", () => {
    state.paperLimit = 20;
    renderAcademic();
  });
});
document.querySelectorAll("#view-career .filters input, #view-career .filters select").forEach(control => {
  control.addEventListener("input", () => {
    if (control.id === "job-state") {
      if (["archive", "new", "review", "saved", "applied", "dismissed"].includes(control.value)) $("job-season").value = "all";
      const hash = { archive: "archive", new: "career-new" }[control.value] || "career";
      history.replaceState(null, "", `#${hash}`);
      state.route = hash;
    }
    renderCareer();
  });
});
$("more-papers").addEventListener("click", () => {
  state.paperLimit += 20;
  renderAcademic();
});
$("reload").addEventListener("click", load);
$("job-list").addEventListener("click", event => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = button.dataset.job;
  const action = button.dataset.action;
  const pressed = state.actions[id] !== action;
  if (pressed) state.actions[id] = action;
  else delete state.actions[id];
  let saved = true;
  try {
    localStorage.setItem("radar_actions_v1", JSON.stringify(state.actions));
  } catch {
    saved = false;
  }
  const feedback = $("feedback");
  feedback.textContent = saved ? (pressed ? `已更新為「${actionLabels[action]}」` : `已取消「${actionLabels[action]}」`) :
    "目前瀏覽器無法保存，下次開啟時需重新設定。";
  feedback.hidden = false;
  clearTimeout(state.feedbackTimer);
  state.feedbackTimer = setTimeout(() => { feedback.hidden = true; }, 2500);
  renderCareer();
  const replacement = Array.from($("job-list").querySelectorAll("button[data-action]")).find(
    element => element.dataset.job === id && element.dataset.action === action
  );
  (replacement || $("job-state")).focus({ preventScroll: true });
});
window.addEventListener("hashchange", route);
document.addEventListener("click", event => {
  const navigation = event.target.closest('a[href^="#"]');
  if (!navigation || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const target = navigation.getAttribute("href");
  if (target === "#main") return;
  event.preventDefault();
  if (location.hash !== target) history.pushState(null, "", target);
  route();
});
route();
load();
