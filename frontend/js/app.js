import { api } from "./api.js";

const root = document.querySelector("#app");
const toast = document.querySelector("#toast");
const progressDialog = document.querySelector("#progress-dialog");
const progressForm = document.querySelector("#progress-form");
let toastTimer;
let currentToday;

const esc = (value = "") => String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
const localDate = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
};
const minutes = (value) => value >= 60 ? `${Math.floor(value / 60)}h${value % 60 ? ` ${value % 60}m` : ""}` : `${value}m`;
const weekdayNames = ["월", "화", "수", "목", "금", "토", "일"];
const frequencyNames = { daily: "매일", weekly: "매주", biweekly: "격주", monthly: "매월" };

function notify(message, error = false) {
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.style.background = error ? "#803b37" : "#293229";
  toast.classList.add("show");
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
}

function setActiveNav(view) {
  document.querySelectorAll("[data-nav]").forEach((link) => link.classList.toggle("active", link.dataset.nav === view));
}

function statusLabel(status) {
  return ({ pending: "예정", completed: "완료", partial: "일부 수행", failed: "실패", active: "진행 중", paused: "중지", planned: "예정", archived: "보관" })[status] || status;
}

async function renderToday() {
  const day = localDate();
  currentToday = await api.today(day);
  const { tasks, weekly_progress: weekly, capacity, candidates, overdue_tasks: overdue } = currentToday;
  const ratio = capacity.planning_limit_minutes ? Math.round(currentToday.planned_minutes / capacity.planning_limit_minutes * 100) : 0;
  root.innerHTML = `
    <header class="page-head">
      <div><p class="eyebrow">TODAY · ${esc(day)}</p><h1>오늘 이거 하면 된다.</h1><button class="text-button vision" id="edit-vision">${esc(currentToday.vision_text || "Vision을 입력하세요")}</button></div>
      <button class="button secondary" id="add-task">할 일 추가</button>
    </header>
    <div class="summary">
      <div class="metric"><strong>${minutes(currentToday.planned_minutes)}</strong><span>오늘 계획</span></div>
      <div class="metric"><strong>${minutes(capacity.planning_limit_minutes)}</strong><span>80% 계획 한도</span></div>
      <div class="metric"><strong>${ratio}%</strong><span><button class="text-button" id="edit-capacity">가용시간 ${minutes(capacity.available_minutes)}</button></span><div class="capacity-track ${ratio > 100 ? "over" : ""}"><i style="width:${Math.min(ratio, 100)}%"></i></div></div>
    </div>
    <section class="section"><div class="section-head"><h2>오늘 할 일</h2><p>${tasks.filter((task) => task.status === "pending").length}개 남음</p></div>${tasks.length ? `<ul class="task-list">${tasks.map(taskRow).join("")}</ul>` : `<p class="empty">오늘 생성된 Task가 없습니다.</p>`}</section>
    ${candidates.length ? `<section class="section"><div class="section-head"><h2>추가 후보</h2><p>계획 한도를 확인해 주세요</p></div><ul class="plain-list">${candidates.map(candidateRow).join("")}</ul></section>` : ""}
    ${overdue.length ? `<section class="section"><div class="section-head"><h2>지난 미완료</h2><p>자동으로 이월하지 않았습니다</p></div><ul class="plain-list">${overdue.map(overdueRow).join("")}</ul></section>` : ""}
    <section class="section"><div class="section-head"><h2>This week</h2><p>최소시간 이상 수행한 기록 기준</p></div><div class="progress-grid">${weekly.map(progressRow).join("") || `<p class="empty">활성 루틴이 없습니다.</p>`}</div></section>`;
  bindToday();
}

function taskRow(task) {
  const done = task.status !== "pending";
  const detail = [task.detail, task.target_value != null ? `목표 ${task.target_value}${task.target_unit || ""}` : "", done ? statusLabel(task.status) : ""].filter(Boolean).join(" · ");
  return `<li class="task-row ${done ? "done" : ""}"><button class="task-check" data-progress="${task.id}" ${done ? "disabled" : ""} aria-label="${esc(task.title)} 수행 기록">✓</button><div><p class="task-title">${esc(task.title)}</p>${detail ? `<p class="task-detail">${esc(detail)}</p>` : ""}<div class="entity-meta">${resourceLinks(task.resources)}</div></div><span class="task-time">${minutes(task.expected_minutes)}</span></li>`;
}

function candidateRow(item) {
  return `<li class="entity-row"><div><h3>${esc(item.title)}</h3><p>${esc(item.reason)}</p></div><div class="entity-meta"><span>${minutes(item.expected_minutes)}</span></div><div class="actions"><button class="button secondary small" data-candidate="${item.kind}:${item.source_id}">오늘 추가</button></div></li>`;
}

function overdueRow(task) {
  return `<li class="entity-row"><div><h3>${esc(task.title)}</h3><p>${esc(task.scheduled_date)} 예정</p></div><div class="entity-meta"><span>${minutes(task.expected_minutes)}</span></div><div class="actions"><button class="button secondary small" data-reschedule="${task.id}">오늘로 이동</button></div></li>`;
}

function progressRow(item) {
  const ratio = item.target_count ? Math.min(item.completed_count / item.target_count * 100, 100) : 0;
  return `<div class="progress-row"><div class="progress-label"><span>${esc(item.name)}</span><strong>${item.completed_count} / ${item.target_count}</strong></div><div class="progress-track"><i style="width:${ratio}%"></i></div></div>`;
}

function bindToday() {
  root.querySelectorAll("[data-progress]").forEach((button) => button.addEventListener("click", () => {
    const task = currentToday.tasks.find((item) => item.id === Number(button.dataset.progress));
    progressForm.reset(); progressForm.elements.task_id.value = task.id; progressForm.elements.actual_minutes.value = task.expected_minutes;
    document.querySelector("#progress-title").textContent = task.title; progressDialog.showModal();
  }));
  root.querySelectorAll("[data-candidate]").forEach((button) => button.addEventListener("click", async () => {
    const [kind, id] = button.dataset.candidate.split(":");
    await action(() => api.acceptCandidate(kind, id, currentToday.date), "오늘 계획에 추가했습니다.", renderToday);
  }));
  root.querySelectorAll("[data-reschedule]").forEach((button) => button.addEventListener("click", async () => {
    if (!confirm("이 Task의 날짜를 오늘로 변경할까요?")) return;
    await action(() => api.updateTask(button.dataset.reschedule, { scheduled_date: currentToday.date, confirm_reschedule: true }), "오늘로 이동했습니다.", renderToday);
  }));
  root.querySelector("#edit-capacity").addEventListener("click", async () => {
    const value = prompt("오늘 실제로 사용할 수 있는 시간(분)", currentToday.capacity.available_minutes);
    if (value === null || !Number.isFinite(Number(value)) || Number(value) < 0) return;
    await action(() => api.setCapacity(currentToday.date, Number(value)), "가용시간을 수정했습니다.", renderToday);
  });
  root.querySelector("#edit-vision").addEventListener("click", async () => {
    const value = prompt("Vision", currentToday.vision_text); if (value === null) return;
    await action(() => api.updateSettings({ vision_text: value }), "Vision을 수정했습니다.", renderToday);
  });
  root.querySelector("#add-task").addEventListener("click", async () => {
    const title = prompt("오늘 할 일"); if (!title?.trim()) return;
    const duration = Number(prompt("예상 소요시간(분)", "30"));
    if (!Number.isFinite(duration) || duration <= 0) return notify("올바른 시간을 입력해 주세요.", true);
    await action(() => api.createTask({ title: title.trim(), scheduled_date: currentToday.date, expected_minutes: duration, priority: 50 }), "Task를 추가했습니다.", renderToday);
  });
}

async function renderRoutines() {
  const [routines, reviews] = await Promise.all([api.routines(), api.reviewItems()]);
  root.innerHTML = `<header class="page-head"><div><p class="eyebrow">ROUTINES</p><h1>반복 활동</h1><p class="muted">반복되는 행동의 빈도와 기본 시간을 관리합니다.</p></div><button class="button primary" id="new-routine">루틴 추가</button></header><form class="editor" id="routine-form" hidden>${routineForm()}</form><section><ul class="plain-list">${routines.map(routineRow).join("") || `<p class="empty">등록된 Routine이 없습니다.</p>`}</ul></section><section class="section"><div class="section-head"><h2>Review</h2><p>예정일에 Today Task 후보가 됩니다</p></div><form class="quick-form" id="review-form"><input name="title" placeholder="복습 주제" required><input name="next_review_on" type="date" value="${localDate()}" required><input name="review_interval_days" type="number" min="1" value="7" aria-label="복습 주기(일)" required><button class="button secondary">복습 추가</button></form><ul class="plain-list">${reviews.map(reviewRow).join("") || `<p class="empty">복습 항목이 없습니다.</p>`}</ul></section>`;
  const editor = root.querySelector("#routine-form");
  root.querySelector("#new-routine").addEventListener("click", () => { editor.reset(); editor.elements.id.value = ""; editor.hidden = false; editor.elements.name.focus(); });
  root.querySelector("[data-cancel-editor]").addEventListener("click", () => { editor.hidden = true; });
  root.querySelectorAll("[data-edit-routine]").forEach((button) => button.addEventListener("click", () => {
    const item = routines.find((routine) => routine.id === Number(button.dataset.editRoutine));
    Object.entries(item).forEach(([key, value]) => { if (editor.elements[key]) editor.elements[key].value = key === "preferred_weekdays" ? value.join(",") : value; });
    editor.hidden = false; editor.scrollIntoView({ behavior: "smooth", block: "start" });
  }));
  root.querySelectorAll("[data-toggle-routine]").forEach((button) => button.addEventListener("click", async () => {
    const item = routines.find((routine) => routine.id === Number(button.dataset.toggleRoutine));
    const payload = routinePayload(item); payload.active = !item.active;
    await action(() => api.updateRoutine(item.id, payload), payload.active ? "루틴을 활성화했습니다." : "루틴을 비활성화했습니다.", renderRoutines);
  }));
  root.querySelectorAll("[data-resource-routine]").forEach((button) => button.addEventListener("click", () => addResource("routine_id", Number(button.dataset.resourceRoutine), renderRoutines)));
  editor.addEventListener("submit", async (event) => {
    event.preventDefault(); const values = Object.fromEntries(new FormData(editor)); const id = values.id; const payload = routinePayload(values);
    await action(() => id ? api.updateRoutine(id, payload) : api.createRoutine(payload), id ? "루틴을 수정했습니다." : "루틴을 추가했습니다.", renderRoutines);
  });
  root.querySelector("#review-form").addEventListener("submit", async (event) => {
    event.preventDefault(); const form = event.currentTarget; const values = Object.fromEntries(new FormData(form));
    const payload = { title: values.title, first_learned_on: localDate(), last_reviewed_on: null, review_interval_days: Number(values.review_interval_days), next_review_on: values.next_review_on, expected_minutes: 30, active: true };
    await action(() => api.createReviewItem(payload), "복습 항목을 추가했습니다.", renderRoutines);
  });
}

function routineForm() {
  return `<input type="hidden" name="id"><input type="hidden" name="active" value="1"><input type="hidden" name="frequency_interval" value="1"><input type="hidden" name="active_from"><input type="hidden" name="active_until"><div class="form-grid"><label>이름<input name="name" required></label><label>분류<input name="category" value="general"></label><label>주기<select name="frequency_type"><option value="daily">매일</option><option value="weekly" selected>매주</option><option value="biweekly">격주</option><option value="monthly">매월</option></select></label><label>목표 횟수<input name="target_count" type="number" min="0" value="1" required></label><label>선호 요일<input name="preferred_weekdays" placeholder="월=0, 수=2처럼 입력"></label><label>기본 시간(분)<input name="default_duration_minutes" type="number" min="1" value="30" required></label><label>최소 시간(분)<input name="min_duration_minutes" type="number" min="1" value="10" required></label><label>최대 시간(분)<input name="max_duration_minutes" type="number" min="1" value="60" required></label><label>기본 목표량<input name="default_target_value" type="number" min="0" step="0.1"></label><label>목표 단위<input name="default_target_unit" placeholder="세트, 문제, 챕터"></label><label>우선순위 (0~100)<input name="priority" type="number" min="0" max="100" value="50" required></label><label class="wide">설명<textarea name="description" rows="2"></textarea></label></div><div class="form-actions"><button type="button" class="button secondary" data-cancel-editor>취소</button><button class="button primary">저장</button></div>`;
}

function routinePayload(values) {
  return { name: values.name, category: values.category || "general", description: values.description || "", frequency_type: values.frequency_type, frequency_interval: Number(values.frequency_interval || 1), target_count: Number(values.target_count), preferred_weekdays: Array.isArray(values.preferred_weekdays) ? values.preferred_weekdays : String(values.preferred_weekdays || "").split(",").filter((v) => v.trim() !== "").map(Number), default_duration_minutes: Number(values.default_duration_minutes), min_duration_minutes: Number(values.min_duration_minutes), max_duration_minutes: Number(values.max_duration_minutes), default_target_value: values.default_target_value === "" || values.default_target_value == null ? null : Number(values.default_target_value), default_target_unit: values.default_target_unit || null, priority: Number(values.priority), active: values.active === undefined ? true : Boolean(Number(values.active) || values.active === true), active_from: values.active_from || null, active_until: values.active_until || null };
}

function routineRow(item) {
  const days = item.preferred_weekdays.length ? item.preferred_weekdays.map((day) => weekdayNames[day]).join("·") : "유동 배치";
  const recommendation = item.recommendation ? ` · 추천 ${item.recommendation.recommended_target_value}${item.recommendation.unit || ""}` : "";
  return `<li class="entity-row"><div><h3>${esc(item.name)} <span class="badge ${item.active ? "" : "inactive"}">${item.active ? "활성" : "비활성"}</span></h3><p>${esc(item.description)}</p></div><div class="entity-meta"><span>이번 주 ${item.completed_count} / ${item.target_count}</span><span>${frequencyNames[item.frequency_type]} · ${days}</span><span>${minutes(item.default_duration_minutes)}</span><span>최근 ${item.last_performed_on || "기록 없음"}${esc(recommendation)}</span>${resourceLinks(item.resources)}</div><div class="actions"><button class="text-button" data-resource-routine="${item.id}">자료</button><button class="text-button" data-edit-routine="${item.id}">수정</button><button class="text-button" data-toggle-routine="${item.id}">${item.active ? "비활성화" : "활성화"}</button></div></li>`;
}

function reviewRow(item) {
  return `<li class="entity-row"><div><h3>${esc(item.title)}</h3><p>다음 복습 ${esc(item.next_review_on)}</p></div><div class="entity-meta"><span>${item.review_interval_days}일 주기</span><span>${minutes(item.expected_minutes)}</span></div><div><span class="badge ${item.active ? "" : "inactive"}">${item.active ? "활성" : "비활성"}</span></div></li>`;
}

async function renderProjects() {
  const projects = await api.projects();
  root.innerHTML = `<header class="page-head"><div><p class="eyebrow">PROJECTS</p><h1>끝이 있는 활동</h1><p class="muted">설명보다 다음 행동을 먼저 봅니다.</p></div><button class="button primary" id="new-project">프로젝트 추가</button></header><form class="editor" id="project-form" hidden>${projectForm()}</form><section><ul class="plain-list">${projects.map(projectRow).join("") || `<p class="empty">등록된 Project가 없습니다.</p>`}</ul></section>`;
  const editor = root.querySelector("#project-form");
  root.querySelector("#new-project").addEventListener("click", () => { editor.reset(); editor.elements.id.value = ""; editor.hidden = false; editor.elements.name.focus(); });
  root.querySelector("[data-cancel-editor]").addEventListener("click", () => editor.hidden = true);
  root.querySelectorAll("[data-edit-project]").forEach((button) => button.addEventListener("click", () => {
    const item = projects.find((project) => project.id === Number(button.dataset.editProject));
    Object.entries(item).forEach(([key, value]) => { if (editor.elements[key]) editor.elements[key].value = value ?? ""; });
    editor.hidden = false; editor.scrollIntoView({ behavior: "smooth", block: "start" });
  }));
  root.querySelectorAll("[data-resource-project]").forEach((button) => button.addEventListener("click", () => addResource("project_id", Number(button.dataset.resourceProject), renderProjects)));
  root.querySelectorAll("[data-project-today]").forEach((button) => button.addEventListener("click", async () => {
    const item = projects.find((project) => project.id === Number(button.dataset.projectToday));
    if (!item.next_action) return notify("먼저 Next action을 입력해 주세요.", true);
    const duration = Number(prompt("예상 소요시간(분)", "30"));
    if (!Number.isFinite(duration) || duration <= 0) return;
    await action(() => api.createTask({ title: item.next_action, scheduled_date: localDate(), expected_minutes: duration, priority: item.priority, project_id: item.id }), "오늘 계획에 추가했습니다.", renderProjects);
  }));
  editor.addEventListener("submit", async (event) => {
    event.preventDefault(); const values = Object.fromEntries(new FormData(editor)); const id = values.id;
    const payload = { name: values.name, description: values.description, deadline: values.deadline || null, status: values.status, priority: Number(values.priority), next_action: values.next_action, estimated_remaining_minutes: values.estimated_remaining_minutes ? Number(values.estimated_remaining_minutes) : null, weekly_target_minutes: values.weekly_target_minutes ? Number(values.weekly_target_minutes) : null };
    await action(() => id ? api.updateProject(id, payload) : api.createProject(payload), id ? "프로젝트를 수정했습니다." : "프로젝트를 추가했습니다.", renderProjects);
  });
}

function projectForm() {
  return `<input type="hidden" name="id"><div class="form-grid"><label>이름<input name="name" required></label><label>상태<select name="status"><option value="active">진행 중</option><option value="planned">예정</option><option value="paused">중지</option><option value="completed">완료</option><option value="archived">보관</option></select></label><label>마감일<input name="deadline" type="date"></label><label>우선순위<input name="priority" type="number" min="0" max="100" value="50"></label><label class="wide">Next action<input name="next_action" placeholder="다음에 할 구체적인 행동"></label><label>예상 잔여시간(분)<input name="estimated_remaining_minutes" type="number" min="0"></label><label>주간 목표시간(분)<input name="weekly_target_minutes" type="number" min="0"></label><label class="wide">설명<textarea name="description" rows="2"></textarea></label></div><div class="form-actions"><button type="button" class="button secondary" data-cancel-editor>취소</button><button class="button primary">저장</button></div>`;
}

function projectRow(item) {
  return `<li class="entity-row"><div><h3>${esc(item.name)} <span class="badge ${item.status === "active" ? "" : "inactive"}">${statusLabel(item.status)}</span></h3><p>${item.deadline ? `마감 ${esc(item.deadline)}` : "마감일 없음"}</p>${resourceLinks(item.resources)}</div><div><p class="eyebrow">NEXT ACTION</p><p class="next-action">${esc(item.next_action || "다음 행동을 입력하세요")}</p></div><div class="actions"><button class="text-button" data-project-today="${item.id}">오늘 추가</button><button class="text-button" data-resource-project="${item.id}">자료</button><button class="text-button" data-edit-project="${item.id}">수정</button></div></li>`;
}

function resourceLinks(resources = []) {
  return resources.map((resource) => {
    if (resource.url && /^https?:\/\//i.test(resource.url)) return `<a class="text-button" href="${esc(resource.url)}" target="_blank" rel="noopener">${esc(resource.label)} ↗</a>`;
    return `<span>${esc(resource.label)}${resource.location_note ? ` · ${esc(resource.location_note)}` : ""}</span>`;
  }).join("");
}

async function addResource(ownerKey, ownerId, refresh) {
  const label = prompt("자료 이름", "원본 자료"); if (!label?.trim()) return;
  const resource_type = prompt("자료 종류 (예: Paper, GitHub, Notion)", "Local PC"); if (!resource_type?.trim()) return;
  const location = prompt("URL 또는 위치 설명", ""); if (location === null) return;
  const isUrl = /^https?:\/\//i.test(location);
  await action(() => api.createResource({ label: label.trim(), resource_type: resource_type.trim(), url: isUrl ? location : null, location_note: isUrl ? null : location || null, [ownerKey]: ownerId }), "자료 위치를 연결했습니다.", refresh);
}

async function renderInbox() {
  const items = await api.inbox();
  root.innerHTML = `<header class="page-head"><div><p class="eyebrow">INBOX</p><h1>일단 적어두기</h1><p class="muted">제목만 입력하고 나중에 정리합니다.</p></div></header><form class="quick-form" id="inbox-form"><input name="title" autocomplete="off" maxlength="160" placeholder="떠오른 일을 입력하세요" aria-label="인박스 제목" required><button class="button primary">저장</button></form><section><ul class="plain-list">${items.filter((item) => !item.processed).map(inboxRow).join("") || `<p class="empty">정리할 항목이 없습니다.</p>`}</ul></section>${items.some((item) => item.processed) ? `<section class="section"><div class="section-head"><h2>처리됨</h2></div><ul class="plain-list">${items.filter((item) => item.processed).map(inboxRow).join("")}</ul></section>` : ""}`;
  root.querySelector("#inbox-form").addEventListener("submit", async (event) => { event.preventDefault(); const form = event.currentTarget; await action(() => api.createInbox(form.elements.title.value.trim()), "Inbox에 저장했습니다.", renderInbox); });
  root.querySelectorAll("[data-process-inbox]").forEach((button) => button.addEventListener("click", () => action(() => api.processInbox(button.dataset.processInbox), "처리 완료로 표시했습니다.", renderInbox)));
  root.querySelectorAll("[data-inbox-today]").forEach((button) => button.addEventListener("click", async () => {
    const item = items.find((entry) => entry.id === Number(button.dataset.inboxToday));
    const duration = Number(prompt("예상 소요시간(분)", "30")); if (!Number.isFinite(duration) || duration <= 0) return;
    try {
      const task = await api.createTask({ title: item.title, scheduled_date: localDate(), expected_minutes: duration, priority: 50 });
      await api.processInbox(item.id, { linked_task_id: task.id }); notify("오늘 Task로 옮겼습니다."); await renderInbox();
    } catch (error) { notify(error.message, true); }
  }));
}

function inboxRow(item) {
  return `<li class="entity-row ${item.processed ? "muted" : ""}"><div><h3>${esc(item.title)}</h3><p>${esc(item.created_at.slice(0, 10))}</p></div><div></div><div class="actions">${item.processed ? `<span class="badge inactive">처리됨</span>` : `<button class="text-button" data-inbox-today="${item.id}">오늘 Task</button><button class="button secondary small" data-process-inbox="${item.id}">처리 완료</button>`}</div></li>`;
}

progressForm.addEventListener("submit", async (event) => {
  event.preventDefault(); if (event.submitter?.value === "cancel") return progressDialog.close();
  const values = Object.fromEntries(new FormData(progressForm));
  const payload = { task_id: Number(values.task_id), actual_minutes: Number(values.actual_minutes), actual_value: values.actual_value ? Number(values.actual_value) : null, result: values.result, memo: values.memo || null };
  await action(() => api.recordProgress(payload), "수행 기록을 저장했습니다.", async () => { progressDialog.close(); await renderToday(); });
});

async function action(operation, message, refresh) {
  try { await operation(); notify(message); if (refresh) await refresh(); }
  catch (error) { notify(error.message, true); }
}

async function route() {
  const view = location.hash.slice(1) || "today";
  const routes = { today: renderToday, routines: renderRoutines, projects: renderProjects, inbox: renderInbox };
  const selected = routes[view] ? view : "today";
  setActiveNav(selected); root.innerHTML = `<p class="muted">불러오는 중…</p>`;
  try { await routes[selected](); root.focus(); } catch (error) { root.innerHTML = `<p class="danger">${esc(error.message)}</p>`; }
}

window.addEventListener("hashchange", route);
route();
