document.addEventListener('DOMContentLoaded', () => {

  const root = document.getElementById('workspace-root');
  const progressFill = document.getElementById('progress-fill');
  const progressLabel = document.getElementById('progress-label');

  let isProcessing = false;

  const setProgress = (value, label) => {
    if (progressFill) progressFill.style.width = `${value}%`;
    if (progressLabel) progressLabel.textContent = label;
  };

  if (!root) {
    setProgress(0, 'Ready');
    return;
  }

  const mode = root.dataset.mode || 'sandbox';
  const sessionId = root.dataset.session || '';
  const hasContext = root.dataset.hasContext === 'true';

  const chatPanel = document.getElementById('chat-panel');
  const input = document.getElementById('message-input');
  const sendBtn = document.getElementById('send-btn');
  const runBtn = document.getElementById('run-simulation-btn');

  const scenarioForm = document.getElementById('scenario-form');
  const sourceType = document.getElementById('source-type');
  const scenarioBrief = document.getElementById('scenario-brief');

  const scenarioLibraryWrap = document.getElementById('scenario-library-wrap');
  const scenarioFileWrap = document.getElementById('scenario-file-wrap');

  const summaryPanel = document.getElementById('summary-panel');
  const summaryTitle = document.getElementById('summary-title');
  const summarySource = document.getElementById('summary-source');
  const summaryCopy = document.getElementById('summary-copy');
  const summaryKeyPoints = document.getElementById('summary-key-points');
  const summaryNegotiationPoints = document.getElementById('summary-negotiation-points');
  const generatedScenarioWrap = document.getElementById('generated-scenario-wrap');
  const generatedScenario = document.getElementById('generated-scenario');

  const getHasContext = () => root.dataset.hasContext === 'true';
  const setHasContext = (value) => {
    root.dataset.hasContext = value ? 'true' : 'false';
  };

  const lockWorkflow = () => {
    if (runBtn) runBtn.disabled = true;
    if (sendBtn) sendBtn.disabled = true;
    if (input) input.disabled = true;
  };

  const unlockWorkflow = () => {
    if (runBtn) runBtn.disabled = false;
    if (sendBtn) sendBtn.disabled = false;
    if (input) input.disabled = false;
  };

  // =========================
  // INITIAL STATE
  // =========================

  if (mode === 'sandbox') {
    if (!hasContext) {
      lockWorkflow();
      if (summaryPanel) summaryPanel.classList.add('hidden');
    } else {
      unlockWorkflow();
      if (summaryPanel) summaryPanel.classList.remove('hidden');
    }
  }

  // =========================
  // MESSAGE RENDER
  // =========================

  const labelForRole = (role) => {
    if (role === 'user') return 'You';
    if (role === 'buyer_ai') return 'AI Buyer';
    if (role === 'sales_ai') return 'AI Sales';
    if (role === 'system') return 'System';
    if (role === 'assistant') return 'AI Assistant';
    return 'AI Coach';
  };

  const appendMessage = (role, text) => {
    if (!chatPanel) return;
    const row = document.createElement('div');
    row.className = `message-row ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'bubble';

    const meta = document.createElement('div');
    meta.className = 'bubble-meta';
    meta.textContent = labelForRole(role);

    const body = document.createElement('div');
    body.className = 'bubble-text';
    body.textContent = text;

    bubble.appendChild(meta);
    bubble.appendChild(body);
    row.appendChild(bubble);
    chatPanel.appendChild(row);

    chatPanel.scrollTop = chatPanel.scrollHeight;
  };

  // =========================
  // SUMMARY RENDER
  // =========================

  const renderSummary = (context) => {
    if (!context || !summaryPanel) return;

    summaryPanel.classList.remove('hidden');

    summaryTitle.textContent = context.title || '';
    summarySource.textContent = context.source_name || '';
    summaryCopy.textContent = context.summary || '';

    summaryKeyPoints.innerHTML = (context.key_points || [])
      .map(item => `<li>${item}</li>`).join('');

    summaryNegotiationPoints.innerHTML = (context.negotiation_points || [])
      .map(item => `<li>${item}</li>`).join('');

    if (generatedScenarioWrap && generatedScenario) {
      if (context.generated_scenario) {
        generatedScenarioWrap.classList.remove('hidden');
        generatedScenario.textContent = context.generated_scenario;
      } else {
        generatedScenarioWrap.classList.add('hidden');
      }
    }

    setHasContext(true);
  };

  // =========================
  // SCENARIO UI CONTROL
  // =========================

  const refreshScenarioVisibility = () => {
    if (!sourceType) return;

    const value = sourceType.value;

    if (scenarioLibraryWrap) {
      scenarioLibraryWrap.classList.toggle('hidden', value !== 'library');
    }

    if (scenarioFileWrap) {
      scenarioFileWrap.classList.toggle('hidden', value !== 'upload');
    }

    if (scenarioBrief) {
      scenarioBrief.classList.toggle('hidden', value !== 'upload');
    }
    if (input) {
      input.classList.toggle('hidden', sourceType.value !== 'upload');
    }
  };

  refreshScenarioVisibility();

  sourceType?.addEventListener('change', () => {

    lockWorkflow();

    if (summaryPanel) summaryPanel.classList.add('hidden');

    refreshScenarioVisibility();
  });

  // =========================
  // ANALYZE SCENARIO
  // =========================

  const prepareScenario = async () => {

    if (!scenarioForm || isProcessing) return;
    isProcessing = true;

    const formData = new FormData(scenarioForm);

    setProgress(20, 'Analyzing scenario...');

    try {
      const response = await fetch('/api/scenario/prepare', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (!response.ok) {
        setProgress(0, 'Error');
        return;
      }

      renderSummary(data.context);

      // ❗ KHÔNG appendMessage nữa → FIX bubble

      if (scenarioBrief) scenarioBrief.classList.add('hidden');

      unlockWorkflow();

      setProgress(100, 'Ready');
      setTimeout(() => setProgress(0, 'Ready'), 800);

    } catch (err) {
      console.error(err);
      setProgress(0, 'Error');
    } finally {
      isProcessing = false;
    }
  };

  scenarioForm?.addEventListener('submit', (e) => {
    e.preventDefault(); // CRITICAL FIX
    prepareScenario();
  });

  // =========================
  // CHAT
  // =========================

  sendBtn?.addEventListener('click', () => {
    const msg = input.value.trim();
    if (!msg) return;

    appendMessage('user', msg);
    input.value = '';
  });

  // =========================
  // RUN SIMULATION
  // =========================

  runBtn?.addEventListener('click', async () => {

    if (isProcessing) return;
    isProcessing = true;

    setProgress(30, 'Running simulation...');

    try {
      const response = await fetch('/api/sandbox/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, turns: 8 })
      });

      const data = await response.json();

      (data.transcript || []).forEach(msg => {
        appendMessage(msg.role, msg.text);
      });

      setProgress(100, 'Done');
      setTimeout(() => setProgress(0, 'Ready'), 800);

    } catch (err) {
      console.error(err);
    } finally {
      isProcessing = false;
    }
  });

  setProgress(0, 'Ready');
});