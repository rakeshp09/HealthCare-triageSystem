// Centralized Asynchronous REST API Client for Healthcare Triage
const ApiClient = {
  async get(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    return await res.json();
  },
  async post(url, data) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    return await res.json();
  }
};
