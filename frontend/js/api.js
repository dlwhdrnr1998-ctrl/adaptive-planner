async function request(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `요청에 실패했습니다. (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

export const api = {
  today: (day) => request(`/today?day=${day}`),
  acceptCandidate: (kind, id, day) => request(`/today/candidates/${kind}/${id}?day=${day}`, { method: "POST" }),
  setCapacity: (day, available_minutes) => request(`/capacity/${day}`, { method: "PUT", body: JSON.stringify({ available_minutes }) }),
  updateSettings: (data) => request("/settings", { method: "PATCH", body: JSON.stringify(data) }),
  routines: () => request("/routines"),
  createRoutine: (data) => request("/routines", { method: "POST", body: JSON.stringify(data) }),
  updateRoutine: (id, data) => request(`/routines/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  projects: () => request("/projects"),
  createProject: (data) => request("/projects", { method: "POST", body: JSON.stringify(data) }),
  updateProject: (id, data) => request(`/projects/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  createTask: (data) => request("/tasks", { method: "POST", body: JSON.stringify(data) }),
  updateTask: (id, data) => request(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  recordProgress: (data) => request("/progress", { method: "POST", body: JSON.stringify(data) }),
  inbox: () => request("/inbox"),
  createInbox: (title) => request("/inbox", { method: "POST", body: JSON.stringify({ title }) }),
  processInbox: (id, data = {}) => request(`/inbox/${id}/process`, { method: "POST", body: JSON.stringify(data) }),
  createResource: (data) => request("/resources", { method: "POST", body: JSON.stringify(data) }),
  reviewItems: () => request("/review-items"),
  createReviewItem: (data) => request("/review-items", { method: "POST", body: JSON.stringify(data) }),
};
