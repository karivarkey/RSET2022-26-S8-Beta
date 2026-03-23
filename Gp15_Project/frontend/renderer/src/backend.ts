const BASE_URL = "http://127.0.0.1:8000"; // or 8000 if you used that

export async function fetchSummaries() {
  const res = await fetch(`${BASE_URL}/summaries`);
  if (!res.ok) throw new Error("Failed to fetch summaries");
  return res.json();
}

export async function fetchTasks(completed = false) {
  const res = await fetch(`${BASE_URL}/tasks?completed=${completed}`);
  if (!res.ok) throw new Error("Failed to fetch tasks");
  return res.json();
}
