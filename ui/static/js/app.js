document.addEventListener('DOMContentLoaded', () => {

  const root = document.getElementById('workspace-root');
  const progressFill = document.getElementById('progress-fill');
  const progressLabel = document.getElementById('progress-label');

  let isProcessing = false;

  const setProgress = (value, label) => {
    if (progressFill) progressFill.style.width = `${value}%`;
    if (progressLabel) progressLabel.textContent = label;
  };

  const resetProgress = () => {
    setTimeout(() => setProgress(0, 'Ready'), 800);
  };

  if (!root) return;

  const mode = root.dataset.mode;
  const sessionId = root.dataset.session;

  const chatPanel = document.getElementById('chat-panel');
  const input = document.getElementById('message-input');
  const sendBtn = document.getElementById('send-btn');
  const runBtn = document.getElementById('run-simulation-btn');

  const form = document.getElementById('scenario-form');
  const sourceType = document.getElementById('source-type');
  const analyzerMode = document.getElementById('analyzer-mode');
  const scenarioBrief = document.getElementById('scenario-brief');

  const scenarioLibraryWrap = document.getElementById('scenario-library-wrap');
  const scenarioFileWrap = document.getElementById('scenario-file-wrap');

  const summaryPanel = document.getElementById('summary-panel');
  const summaryTitle = document.getElementById('summary-title');
  const summarySource = document.getElementById('summary-source');
  const summaryCopy = document.getElementById('summary-copy');
  const summaryKeyPoints = document.getElementById('summary-key-points');
  const summaryNegotiationPoints = document.getElementById('summary-negotiation-points');

  const lock = () => {
    if (runBtn) runBtn.disabled = true;
    if (sendBtn) sendBtn.disabled = true;
    if (input) input.disabled = true;
  };

  const unlock = () => {
    if (runBtn && mode === 'sandbox') runBtn.disabled = false;
    if (sendBtn) sendBtn.disabled = false;
    if (input) input.disabled = false;
  };

  const hideSummary = () => {
    if (summaryPanel) summaryPanel.classList.add('hidden');
  };

  const showSummary = () => {
    if (summaryPanel) summaryPanel.classList.remove('hidden');
  };

  // =========================
  // SCENARIO VISIBILITY
  // =========================

  const refreshScenarioUI = () => {
    if (!sourceType) return;

    const value = sourceType.value;

    // LIBRARY
    if (scenarioLibraryWrap) {
      scenarioLibraryWrap.classList.toggle('hidden', value !== 'library');
    }

    // FILE
    if (scenarioFileWrap) {
      scenarioFileWrap.classList.toggle('hidden', value !== 'upload');
    }

    // TEXTAREA LOGIC (🔥 FIX)
    if (scenarioBrief) {

      // Mode 1: sandbox
      if (mode === 'sandbox') {
        scenarioBrief.classList.toggle('hidden', !(value === 'upload' || value === 'paste'));

        if (value === 'paste') {
          scenarioBrief.placeholder = 'Paste your scenario here...';
        }

        if (value === 'upload') {
          scenarioBrief.placeholder = 'Optional note for uploaded scenario...';
        }
      }

      // Mode 2: real_case
      if (mode === 'real_case') {
        scenarioBrief.classList.toggle('hidden', value !== 'paste');

        if (value === 'paste') {
          scenarioBrief.placeholder = 'Paste your real case here...';
        }
      }
    }
  };

  refreshScenarioUI();

  sourceType?.addEventListener('change', () => {
    lock();
    hideSummary();
    refreshScenarioUI();
  });

  analyzerMode?.addEventListener('change', () => {
    lock();
    hideSummary();
  });

  // =========================
  // RENDER SUMMARY
  // =========================

  const renderSummary = (ctx) => {
    showSummary();

    summaryTitle.textContent = ctx.title || '';
    summarySource.textContent = ctx.source_name || '';
    summaryCopy.textContent = ctx.summary || '';

    summaryKeyPoints.innerHTML = (ctx.key_points || []).map(x => `<li>${x}</li>`).join('');
    summaryNegotiationPoints.innerHTML = (ctx.negotiation_points || []).map(x => `<li>${x}</li>`).join('');
  };

  // =========================
  // ANALYZE
  // =========================

  const analyzeScenario = async () => {

    if (!form || isProcessing) return;

    isProcessing = true;
    lock();
    setProgress(20, 'Analyzing...');

    const formData = new FormData(form);

    try {
      const res = await fetch('/api/scenario/prepare', {
        method: 'POST',
        body: formData
      });

      const data = await res.json();

      if (!data.ok) {
        setProgress(0, 'Error');
        return;
      }

      renderSummary(data.context);

      // hide textarea after analyze
      if (scenarioBrief) scenarioBrief.classList.add('hidden');

      unlock();

      setProgress(100, 'Ready');
      resetProgress();

    } catch (e) {
      console.error(e);
      setProgress(0, 'Error');
    }

    isProcessing = false;
  };

  form?.addEventListener('submit', (e) => {
    e.preventDefault(); // 🔥 IMPORTANT FIX
    analyzeScenario();
  });

  // =========================
  // CHAT (simple)
  // =========================

  sendBtn?.addEventListener('click', () => {
    const msg = input.value.trim();
    if (!msg) return;

    const row = document.createElement('div');
    row.className = 'message-row user';
    row.innerHTML = `<div class="bubble"><div class="bubble-meta">You</div><div class="bubble-text">${msg}</div></div>`;
    chatPanel.appendChild(row);

    input.value = '';
    chatPanel.scrollTop = chatPanel.scrollHeight;
  });

  // =========================
  // RUN SIMULATION
  // =========================

  runBtn?.addEventListener('click', async () => {

    if (isProcessing) return;

    isProcessing = true;

    setProgress(30, 'Running simulation...');

    try {
      const res = await fetch('/api/sandbox/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, turns: 8 })
      });

      const data = await res.json();

      // 🔥 CLEAR CHAT BEFORE RUN
      if (chatPanel) chatPanel.innerHTML = '';

      (data.transcript || []).forEach(msg => {
        const row = document.createElement('div');
        row.className = `message-row ${msg.role}`;
        row.innerHTML = `
          <div class="bubble">
            <div class="bubble-meta">${msg.role}</div>
            <div class="bubble-text">${msg.text}</div>
          </div>`;
        chatPanel.appendChild(row);
      });

      chatPanel.scrollTop = chatPanel.scrollHeight;

      setProgress(100, 'Done');
      resetProgress();

    } catch (e) {
      console.error(e);
      setProgress(0, 'Error');
    }

    isProcessing = false;
  });

  setProgress(0, 'Ready');
});