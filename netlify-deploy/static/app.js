(() => {
  let sessionId = null;
  let currentQuestion = null;
  const $ = (id) => document.getElementById(id);
  const show = (id) => $(id).classList.remove('hidden');
  const hide = (id) => $(id).classList.add('hidden');
  async function api(url, options = {}) {
    const response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Something went wrong. Please try again.');
    return data;
  }
  async function loadMetadata() {
    try {
      const data = await api('/api/meta');
      const select = $('subject');
      select.replaceChildren(new Option('All subjects', 'All'));
      data.subjects.forEach(subject => select.add(new Option(subject, subject)));
    } catch (_) { /* The start action will show a useful API error if unavailable. */ }
  }
  loadMetadata();
  $('start-btn').addEventListener('click', async () => {
    $('start-btn').disabled = true; $('welcome-error').textContent = ''; $('top-status').textContent = 'Starting…';
    try {
      const data = await api('/api/sessions', {method:'POST', body:JSON.stringify({subject:$('subject').value})});
      sessionId = data.session_id; hide('welcome'); show('exam'); $('top-status').textContent = 'In progress';
      if (new URLSearchParams(location.search).get('dev') === '1') { $('trace-link').href = `/trace?session_id=${encodeURIComponent(sessionId)}`; $('trace-link').classList.remove('hidden'); }
      await loadQuestion();
    } catch (error) { $('welcome-error').textContent = error.message; $('start-btn').disabled = false; $('top-status').textContent = 'Ready'; }
  });
  function normalizeQuestionText(text) {
    return text
      .replace(/\\begin\{center\}|\\end\{center\}/g, '')
      .replace(/\\begin\{tabular\}\{[^}]*\}/g, '')
      .replace(/\\end\{tabular\}/g, '')
      .replace(/\\hline/g, '')
      .replace(/\\\\/g, '\n')
      .replace(/&/g, ' | ')
      .replace(/\\~/g, '~');
  }
  async function loadQuestion() {
    $('answer-error').textContent = ''; $('save-status').textContent = 'Select one answer'; $('next-btn').disabled = true;
    const data = await api(`/api/sessions/${sessionId}/question`);
    if (data.complete) { finish(); return; }
    currentQuestion = data.question;
    $('subject-topic').textContent = `${currentQuestion.subject} · ${currentQuestion.topic}`;
    $('question-count').textContent = `Question ${currentQuestion.number}`;
    $('progress-bar').style.width = `${Math.min(100, ((currentQuestion.number - 1) / currentQuestion.total_limit) * 100)}%`;
    $('question-text').textContent = currentQuestion.text;
    if (window.MathJax?.typesetPromise) {
      await window.MathJax.typesetPromise([$('question-text')]);
    }
    $('options').replaceChildren();
    currentQuestion.options.forEach((option, index) => {
      const label = document.createElement('label'); label.className = 'option';
      const input = document.createElement('input'); input.type = 'radio'; input.name = 'answer'; input.value = String(index);
      const letter = document.createElement('span'); letter.className = 'option-letter'; letter.textContent = String.fromCharCode(65 + index) + '.';
      const text = document.createElement('span'); text.textContent = option;
      input.addEventListener('change', () => { document.querySelectorAll('.option').forEach(el => el.classList.remove('selected')); label.classList.add('selected'); $('next-btn').disabled = false; $('save-status').textContent = 'Answer selected'; });
      label.append(input, letter, text); $('options').append(label);
    });
    if (window.MathJax?.typesetPromise) {
      await window.MathJax.typesetPromise([
        $('question-text'),
        $('options')
      ]);
    }
  }
  $('answer-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const selected = document.querySelector('input[name="answer"]:checked');
    if (!selected) { $('answer-error').textContent = 'Select an answer before continuing.'; return; }
    $('next-btn').disabled = true; $('save-status').textContent = 'Saving response…';
    try {
      await api(`/api/sessions/${sessionId}/answer`, {method:'POST', body:JSON.stringify({question_id:currentQuestion.question_id, selected_index:Number(selected.value)})});
      await loadQuestion();
    } catch (error) { $('answer-error').textContent = error.message; $('next-btn').disabled = false; $('save-status').textContent = 'Response not saved'; }
  });
  function finish() { hide('exam'); hide('welcome'); show('finished'); $('top-status').textContent = 'Submitted'; }
})();
