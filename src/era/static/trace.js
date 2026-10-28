(() => {
  const params = new URLSearchParams(location.search);
  const sessionId = params.get('session_id');
  const $ = id => document.getElementById(id);
  async function refresh() {
    if (!sessionId) { $('trace-error').textContent = 'Missing session_id in the URL.'; $('trace-status').textContent = 'Not connected'; return; }
    try {
      const response = await fetch(`/api/admin/sessions/${encodeURIComponent(sessionId)}/trace`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Trace unavailable');
      $('trace-status').textContent = 'Live';
      $('trace-summary').textContent = `Responses: ${data.ability.responses} · θ: ${data.ability.theta} · Posterior SD: ${data.ability.posterior_sd} · Next phase: ${data.phase}`;
      $('trace-events').replaceChildren();
      data.events.slice().reverse().forEach(event => {
        const card = document.createElement('article'); card.className = 'trace-event';
        const title = document.createElement('strong'); title.textContent = event.event_type;
        const pre = document.createElement('pre'); pre.textContent = JSON.stringify(event, null, 2);
        card.append(title, pre); $('trace-events').append(card);
      });
      $('trace-error').textContent = '';
    } catch (error) { $('trace-status').textContent = 'Unavailable'; $('trace-error').textContent = error.message; }
  }
  refresh(); setInterval(refresh, 2500);
})();
