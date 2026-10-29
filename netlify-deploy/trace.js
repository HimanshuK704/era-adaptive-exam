(() => {
  const params = new URLSearchParams(location.search);
  const sessionId = params.get("session_id");
  const $ = id => document.getElementById(id);

  async function loadResearch() {
    const status = $("ednet-status");
    try {
      const response = await fetch("/api/research/ednet");
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Research summary unavailable");

      status.textContent = `${data.dataset || "EdNet-KT2"} · ${data.profiles_analyzed} profiles analyzed`;

      const selected = [
        ["event_count", "Events per profile"],
        ["answer_revisions", "Answer revisions"],
        ["session_count_30min_gap", "Inferred sessions"],
        ["total_session_seconds", "Estimated session seconds"],
        ["median_session_seconds", "Median session seconds"]
      ];

      const stats = $("ednet-stats");
      stats.replaceChildren();
      selected.forEach(([key, label]) => {
        const item = data.features?.[key];
        if (!item) return;
        const card = document.createElement("article");
        card.className = "trace-event";

        const heading = document.createElement("strong");
        heading.textContent = label;

        const detail = document.createElement("p");
        detail.textContent = `Median: ${item.median} · Mean: ${item.mean} · Range: ${item.min}–${item.max}`;

        card.append(heading, detail);
        stats.append(card);
      });

      const correlations = $("ednet-correlations");
      correlations.replaceChildren();
      Object.entries(data.correlations || {}).forEach(([pair, value]) => {
        const item = document.createElement("p");
        item.textContent = `${pair.replaceAll("__", " vs ")}: ${value ?? "not available"}`;
        correlations.append(item);
      });

      const limitations = $("ednet-limitations");
      limitations.replaceChildren();
      (data.limitations || []).forEach(limit => {
        const item = document.createElement("li");
        item.textContent = limit;
        limitations.append(item);
      });
    } catch (error) {
      status.textContent = `Research summary unavailable: ${error.message}`;
    }
  }

  async function refreshTrace() {
    if (!sessionId) {
      $("trace-error").textContent = "No session_id provided. The EdNet research panel remains available below.";
      $("trace-status").textContent = "Research view";
      return;
    }

    try {
      const response = await fetch(`/api/admin/sessions/${encodeURIComponent(sessionId)}/trace`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Trace unavailable");

      $("trace-status").textContent = "Live";
      $("trace-summary").textContent =
        `Responses: ${data.ability.responses} · Theta: ${data.ability.theta} · Posterior SD: ${data.ability.posterior_sd} · Next phase: ${data.phase}`;

      const events = $("trace-events");
      events.replaceChildren();
      data.events.slice().reverse().forEach(event => {
        const card = document.createElement("article");
        card.className = "trace-event";
        const title = document.createElement("strong");
        title.textContent = event.event_type;
        const pre = document.createElement("pre");
        pre.textContent = JSON.stringify(event, null, 2);
        card.append(title, pre);
        events.append(card);
      });
      $("trace-error").textContent = "";
    } catch (error) {
      $("trace-status").textContent = "Unavailable";
      $("trace-error").textContent = error.message;
    }
  }

  loadResearch();
  refreshTrace();
  setInterval(refreshTrace, 2500);
})();
