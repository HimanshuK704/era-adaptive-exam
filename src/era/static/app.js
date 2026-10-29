(() => {
  let authToken = null;
  let studentId = null;
  let sessionId = null;
  let currentQuestion = null;
  let currentStage = 'diagnostic';
  let diagnosticLimit = 15;
  let totalLimit = 45;
  let mainStarted = false;
  const $ = (id) => document.getElementById(id);
  const show = (id) => $(id).classList.remove('hidden');
  const hide = (id) => $(id).classList.add('hidden');
  async function api(url, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...(authToken ? {'Authorization': `Bearer ${authToken}`} : {}),
      ...(options.headers || {})
    };
    const response = await fetch(url, {...options, headers});
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
  $('login-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    $('login-btn').disabled = true;
    $('login-error').textContent = '';
    $('top-status').textContent = 'Signing in…';
    try {
      const result = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          student_id: $('student-id').value.trim(),
          password: $('student-password').value
        })
      });
      authToken = result.access_token;
      studentId = result.student_id;
      $('student-password').value = '';
      $('student-greeting').textContent = `Signed in as ${studentId}`;
      hide('login-panel');
      show('welcome');
      $('top-status').textContent = 'Authenticated';
    } catch (error) {
      $('login-error').textContent = error.message;
      $('top-status').textContent = 'Sign-in failed';
    } finally {
      $('login-btn').disabled = false;
    }
  });

  loadMetadata();
  $('start-btn').addEventListener('click', async () => {
    $('start-btn').disabled = true; $('welcome-error').textContent = ''; $('top-status').textContent = 'Starting…';
    try {
      const data = await api('/api/sessions', {method:'POST', body:JSON.stringify({subject:$('subject').value})});
      sessionId = data.session_id; diagnosticLimit = data.diagnostic_items || 15; totalLimit = data.total_limit || 45; currentStage = 'diagnostic'; mainStarted = false; hide('welcome'); show('exam'); $('top-status').textContent = 'In progress';
      if (new URLSearchParams(location.search).get('dev') === '1') { $('trace-link').href = `/trace?session_id=${encodeURIComponent(sessionId)}`; $('trace-link').classList.remove('hidden'); }
      await loadQuestion();
    } catch (error) { $('welcome-error').textContent = error.message; $('start-btn').disabled = false; $('top-status').textContent = 'Ready'; }
  });
  function normalizeQuestionText(raw) {
    let text = String(raw ?? '');

    // Replace LaTeX tabular blocks with readable rows.
    text = text.replace(
      /\\begin\{tabular\}\{[^}]*\}([\s\S]*?)\\end\{tabular\}/g,
      (_, body) => {
        const rows = body
          .replace(/\\hline/g, '')
          .split(/\\\\/)
          .map(row => row.trim())
          .filter(Boolean)
          .map(row => row.split('&').map(cell => cell.trim()).join('    |    '));
        return '\n\n' + rows.join('\n') + '\n\n';
      }
    );

    return text
      .replace(/\\begin\{center\}|\\end\{center\}/g, '')
      .replace(/\\~/g, '~')
      .replace(/\r\n/g, '\n')
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }

  function renderQuestion(raw) {
    const container = $('question-text');
    container.replaceChildren();

    let text = String(raw ?? '');
    const tablePattern = /\\begin\{center\}\s*\\begin\{tabular\}\{[^}]*\}([\s\S]*?)\\end\{tabular\}\s*\\end\{center\}/;

    const match = text.match(tablePattern);
    if (match) {
      const before = text.slice(0, match.index);
      const after = text.slice(match.index + match[0].length);

      container.append(document.createTextNode(before));

      const table = document.createElement('table');
      table.className = 'question-data-table';

      const rows = match[1]
        .replace(/\\hline/g, '')
        .split(/\\\\/)
        .map(row => row.trim())
        .filter(Boolean);

      rows.forEach((row, rowIndex) => {
        const tr = document.createElement('tr');
        row.split('&').forEach(cell => {
          const td = document.createElement(rowIndex === 0 ? 'th' : 'td');
          td.textContent = cell.trim();
          tr.appendChild(td);
        });
        table.appendChild(tr);
      });

      container.appendChild(table);
      container.append(document.createTextNode(after));
    } else {
      container.textContent = text;
    }

    if (window.MathJax?.typesetPromise) {
      window.MathJax.typesetClear?.([container]);
      window.MathJax.typesetPromise([container]).catch(console.error);
    }
  }

  async function loadQuestion() {
    $('answer-error').textContent = '';
    $('save-status').textContent = 'Select one answer';
    $('next-btn').disabled = true;

    const data = await api(`/api/sessions/${sessionId}/question`);
    if (data.complete) { finish(); return; }

    const stage = data.stage || (data.question.number <= diagnosticLimit ? 'diagnostic' : 'main');

    if (stage === 'main' && !mainStarted) {
      currentStage = 'main';
      hide('exam');
      show('stage-transition');
      $('transition-title').textContent = 'Diagnostic assessment complete';
      $('transition-message').textContent =
        `You have completed ${diagnosticLimit} diagnostic questions. Your responses have informed the adaptive assessment. The main exam contains ${totalLimit - diagnosticLimit} questions.`;
      $('begin-main-btn').onclick = async () => {
        mainStarted = true;
        hide('stage-transition');
        show('exam');
        await renderQuestion(data);
      };
      return;
    }

    currentStage = stage;
    await renderQuestion(data);
  }

  async function renderQuestion(data) {
    currentQuestion = data.question;

    const stageNumber = currentStage === 'diagnostic'
      ? currentQuestion.number
      : currentQuestion.number - diagnosticLimit;
    const stageLimit = currentStage === 'diagnostic'
      ? diagnosticLimit
      : totalLimit - diagnosticLimit;

    $('stage-label').textContent = currentStage === 'diagnostic'
      ? 'Diagnostic Assessment'
      : 'Main Adaptive Exam';
    $('question-count').textContent =
      `Question ${stageNumber} of ${stageLimit}`;
    $('progress-bar').style.width =
      `${Math.min(100, ((stageNumber - 1) / stageLimit) * 100)}%`;
    $('subject-topic').textContent =
      `${currentQuestion.subject} ? ${currentQuestion.topic}`;

    renderQuestionText(currentQuestion.text);

    $('options').replaceChildren();
    currentQuestion.options.forEach((option, index) => {
      const label = document.createElement('label');
      label.className = 'option';

      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'answer';
      input.value = String(index);

      const letter = document.createElement('span');
      letter.className = 'option-letter';
      letter.textContent = String.fromCharCode(65 + index) + '.';

      const optionText = document.createElement('span');
      optionText.textContent = option;

      input.addEventListener('change', () => {
        document.querySelectorAll('.option')
          .forEach(el => el.classList.remove('selected'));
        label.classList.add('selected');
        $('next-btn').disabled = false;
        $('save-status').textContent = 'Answer selected';
      });

      label.append(input, letter, optionText);
      $('options').append(label);
    });

    if (window.MathJax?.typesetPromise) {
      window.MathJax.typesetClear?.([$('question-text'), $('options')]);
      await window.MathJax.typesetPromise([$('question-text'), $('options')]);
    }
  }

  function renderQuestionText(raw) {
    const container = $('question-text');
    if (typeof renderQuestion === 'function' && false) return;
    container.textContent = normalizeQuestionText(raw);
    if (window.MathJax?.typesetPromise) {
      window.MathJax.typesetClear?.([container]);
      window.MathJax.typesetPromise([container]).catch(console.error);
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
