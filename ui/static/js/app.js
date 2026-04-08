document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('workspace-root');
  const progressFill = document.getElementById('progress-fill');
  const progressLabel = document.getElementById('progress-label');

  let isProcessing = false;

  const setProgress = (value, label) => {
    if (progressFill) progressFill.style.width = `${value}%`;
    if (progressLabel) progressLabel.textContent = label;
  };

  const resetProgress = (delay = 800) => {
    window.setTimeout(() => {
      setProgress(0, 'Ready');
    }, delay);
  };

  if (!root) {
    setProgress(0, 'Ready');
    return;
  }

  const mode = root.dataset.mode || 'sandbox';
  const sessionId = root.dataset.session || '';

  const chatPanel = document.getElementById('chat-panel');
  const input = document.getElementById('message-input');
  const sendBtn = document.getElementById('send-btn');

  const scenarioForm = document.getElementById('scenario-form');
  const sourceType = document.getElementById('source-type');
  const analyzerMode = document.getElementById('analyzer-mode');
  const scenarioBrief = document.getElementById('scenario-brief');
  const analyzeBtn = document.getElementById('analyze-btn');

  const scenarioSetupPanel = document.getElementById('scenario-setup-panel');
  const scenarioLibraryWrap = document.getElementById('scenario-library-wrap');
  const scenarioFileWrap = document.getElementById('scenario-file-wrap');

  const runSimulationBtn = document.getElementById('run-simulation-btn');

  const summaryPanel = document.getElementById('summary-panel');
  const summaryTitle = document.getElementById('summary-title');
  const summarySource = document.getElementById('summary-source');
  const summaryCopy = document.getElementById('summary-copy');
  const summaryKeyPoints = document.getElementById('summary-key-points');
  const summaryNegotiationPoints = document.getElementById('summary-negotiation-points');
  const generatedScenarioWrap = document.getElementById('generated-scenario-wrap');
  const generatedScenario = document.getElementById('generated-scenario');

  const chatEmptyState = document.getElementById('chat-empty-state');

  const getHasContext = () => root.dataset.hasContext === 'true';
  const setHasContext = (value) => {
    root.dataset.hasContext = value ? 'true' : 'false';
  };

  const escapeHtml = (value) =>
    (value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

  const labelForRole = (role) => {
    if (role === 'user') return 'You';
    if (role === 'buyer_ai') return 'AI Buyer';
    if (role === 'sales_ai') return 'AI Sales';
    if (role === 'system') return 'System';
    if (role === 'assistant') return 'AI Assistant';
    return 'AI Coach';
  };

  const hideChatEmptyState = () => {
    if (chatEmptyState) chatEmptyState.classList.add('hidden');
  };

  const appendMessage = (role, text, auditSummary = '', typing = false) => {
    if (!chatPanel) return null;

    hideChatEmptyState();

    const row = document.createElement('div');
    row.className = `message-row ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'bubble';

    const meta = document.createElement('div');
    meta.className = 'bubble-meta';
    meta.textContent = labelForRole(role);

    const body = document.createElement('div');
    body.className = 'bubble-text';

    if (typing) {
      body.innerHTML =
        '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
    } else {
      body.textContent = text;
    }

    bubble.appendChild(meta);
    bubble.appendChild(body);

    if (auditSummary) {
      const audit = document.createElement('div');
      audit.className = 'audit-chip';
      audit.textContent = auditSummary;
      bubble.appendChild(audit);
    }

    row.appendChild(bubble);
    chatPanel.appendChild(row);
    chatPanel.scrollTop = chatPanel.scrollHeight;
    return body;
  };

  const clearList = (node) => {
    if (node) node.innerHTML = '';
  };

  const fillList = (node, items) => {
    if (!node) return;
    node.innerHTML = (items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');
  };

  const ensureAuxiliarySummarySections = () => {
    if (!summaryPanel) return {};

    let aux = document.getElementById('summary-aux-sections');
    if (!aux) {
      aux = document.createElement('div');
      aux.id = 'summary-aux-sections';
      aux.className = 'summary-aux-sections';
      summaryPanel.appendChild(aux);
    }

    return { aux };
  };

  const renderAdvancedSummary = (context) => {
    if (!summaryPanel || !context) return;

    const { aux } = ensureAuxiliarySummarySections();
    if (!aux) return;

    const stakeholders = context.stakeholders || { buyer: '', seller: '' };
    const painPoints = context.pain_points || [];
    const risks = context.risks || [];
    const recommendedStrategies = context.recommended_strategies || [];
    const tacticalSuggestions = context.tactical_suggestions || [];
    const possibleObjections = context.possible_objections || [];
    const powerDynamics = context.power_dynamics || [];

    const sections = [];

    const hasStakeholders =
      (stakeholders && (stakeholders.buyer || stakeholders.seller)) ||
      painPoints.length ||
      risks.length ||
      recommendedStrategies.length ||
      tacticalSuggestions.length ||
      possibleObjections.length ||
      powerDynamics.length;

    if (!hasStakeholders) {
      aux.innerHTML = '';
      return;
    }

    sections.push(`
      <div class="summary-columns">
        <div class="summary-card">
          <h4>Stakeholders</h4>
          <ul>
            <li><strong>Buyer:</strong> ${escapeHtml(stakeholders.buyer || '')}</li>
            <li><strong>Seller:</strong> ${escapeHtml(stakeholders.seller || '')}</li>
          </ul>
        </div>
        <div class="summary-card">
          <h4>Pain Points</h4>
          <ul>${painPoints.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        </div>
      </div>
    `);

    sections.push(`
      <div class="summary-columns">
        <div class="summary-card">
          <h4>Risks</h4>
          <ul>${risks.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        </div>
        <div class="summary-card">
          <h4>Power Dynamics</h4>
          <ul>${powerDynamics.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        </div>
      </div>
    `);

    sections.push(`
      <div class="summary-columns">
        <div class="summary-card">
          <h4>Recommended Strategies</h4>
          <ul>${recommendedStrategies.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        </div>
        <div class="summary-card">
          <h4>Tactical Suggestions</h4>
          <ul>${tacticalSuggestions.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        </div>
      </div>
    `);

    sections.push(`
      <div class="summary-columns">
        <div class="summary-card">
          <h4>Possible Objections</h4>
          <ul>${possibleObjections.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        </div>
        <div class="summary-card"></div>
      </div>
    `);

    aux.innerHTML = sections.join('');
  };

  const renderSummary = (context) => {
    if (!summaryPanel || !context) return;

    summaryPanel.classList.remove('hidden');

    if (summaryTitle) summaryTitle.textContent = context.title || 'Scenario Summary';
    if (summarySource) summarySource.textContent = context.source_name || '';
    if (summaryCopy) summaryCopy.textContent = context.summary || '';

    fillList(summaryKeyPoints, context.key_points || []);
    fillList(summaryNegotiationPoints, context.negotiation_points || []);

    if (generatedScenarioWrap && generatedScenario) {
      if (context.generated_scenario) {
        generatedScenarioWrap.classList.remove('hidden');
        generatedScenario.textContent = context.generated_scenario;
      } else {
        generatedScenarioWrap.classList.add('hidden');
        generatedScenario.textContent = '';
      }
    }

    renderAdvancedSummary(context);
    setHasContext(true);
  };

  const lockWorkflow = () => {
    if (runSimulationBtn) runSimulationBtn.disabled = true;
    if (sendBtn) sendBtn.disabled = true;
    if (input) input.disabled = true;
  };

  const unlockWorkflow = () => {
    if (runSimulationBtn && mode === 'sandbox') runSimulationBtn.disabled = false;
    if (sendBtn) sendBtn.disabled = false;
    if (input) input.disabled = false;
  };

  const setAnalyzeButtonState = (busy) => {
    if (!analyzeBtn) return;
    analyzeBtn.disabled = busy;
    analyzeBtn.textContent = busy ? 'Analyzing...' : 'Analyze Scenario';
  };

  const refreshScenarioVisibility = () => {
    if (!sourceType) return;

    const value = sourceType.value;

    if (scenarioLibraryWrap) {
      if (mode === 'sandbox') {
        scenarioLibraryWrap.classList.toggle('hidden', value !== 'library');
      } else if (mode === 'reps') {
        scenarioLibraryWrap.classList.remove('hidden');
      } else {
        scenarioLibraryWrap.classList.add('hidden');
      }
    }

    if (scenarioFileWrap) {
      if (mode === 'sandbox' || mode === 'real_case') {
        scenarioFileWrap.classList.toggle('hidden', value !== 'upload');
      } else {
        scenarioFileWrap.classList.add('hidden');
      }
    }

    if (scenarioBrief) {
      if (mode === 'sandbox') {
        scenarioBrief.classList.toggle('hidden', value !== 'upload');
        if (value === 'upload') {
          scenarioBrief.placeholder = 'Optional note for uploaded scenario.';
        }
      } else {
        scenarioBrief.classList.add('hidden');
      }
    }
  };

  const resetScenarioStateForSourceChange = () => {
    lockWorkflow();

    if (summaryPanel) summaryPanel.classList.add('hidden');

    clearList(summaryKeyPoints);
    clearList(summaryNegotiationPoints);

    if (generatedScenarioWrap) generatedScenarioWrap.classList.add('hidden');
    if (generatedScenario) generatedScenario.textContent = '';

    const aux = document.getElementById('summary-aux-sections');
    if (aux) aux.innerHTML = '';

    setHasContext(false);
  };

  const prepareScenario = async (overrides = {}) => {
    if (!scenarioForm || isProcessing) return;

    isProcessing = true;
    setAnalyzeButtonState(true);
    lockWorkflow();
    setProgress(20, 'Analyzing scenario...');

    const formData = new FormData(scenarioForm);
    Object.entries(overrides).forEach(([key, value]) => formData.set(key, value));

    try {
      const response = await fetch('/api/scenario/prepare', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (!response.ok || !data.ok) {
        setProgress(0, data.detail || data.error || 'Scenario preparation failed');
        return;
      }

      renderSummary(data.context || {});

      if (scenarioBrief) {
        scenarioBrief.classList.add('hidden');
      }

      if (scenarioSetupPanel) {
        scenarioSetupPanel.classList.add('scenario-ready');
      }

      unlockWorkflow();

      if (mode === 'real_case' && input) {
        input.placeholder = 'Case summarized. Now type your negotiation message or ask for guidance.';
      }

      setProgress(100, 'Scenario ready');
      resetProgress();
    } catch (err) {
      console.error('Scenario preparation error:', err);
      setProgress(0, 'Error');
    } finally {
      setAnalyzeButtonState(false);
      isProcessing = false;
    }
  };

  const streamChat = async (action = 'chat') => {
    if (isProcessing) return;

    const message = (input?.value || '').trim();
    if (action === 'chat' && !message) return;

    if (action === 'chat' && !getHasContext()) {
      if (mode === 'real_case' || (mode === 'sandbox' && sourceType?.value === 'paste')) {
        await prepareScenario({ source_type: 'paste', content: message });
        if (input) input.value = '';
        return;
      }
      return;
    }

    if (action === 'chat' && mode === 'sandbox') {
      if (input) input.value = '';
      return;
    }

    if (action === 'auto' && mode === 'sandbox') {
      if (!getHasContext()) return;
      await runSimulation();
      return;
    }

    isProcessing = true;

    if (message) appendMessage('user', message);
    if (input) input.value = '';

    const aiNode = appendMessage('assistant', '', '', true);
    setProgress(15, 'Sending to model...');

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, mode, message, action })
      });

      if (!response.ok || !response.body) {
        const errorText = await response.text();
        if (aiNode) aiNode.textContent = errorText || 'Request failed.';
        setProgress(0, 'Request failed');
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let streamed = '';

      setProgress(30, 'Model is responding...');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split('\n');
        buffer = chunks.pop() || '';

        for (const chunk of chunks) {
          const trimmedChunk = chunk.trim();
          if (!trimmedChunk.startsWith('data: ')) continue;

          try {
            const payload = JSON.parse(trimmedChunk.slice(6));

            if (payload.token) {
              if (streamed === '' && aiNode) aiNode.textContent = '';
              streamed += payload.token;
              if (aiNode) aiNode.textContent = streamed;
              setProgress(
                Math.min(90, 30 + Math.floor(streamed.length / 8)),
                'Streaming response...'
              );
              if (chatPanel) chatPanel.scrollTop = chatPanel.scrollHeight;
            }

            if (payload.done) {
              const bubble = aiNode?.parentElement;
              if (bubble && payload.audit?.summary) {
                const audit = document.createElement('div');
                audit.className = 'audit-chip';
                audit.textContent = payload.audit.summary;
                bubble.appendChild(audit);
              }
              setProgress(100, 'Completed');
              resetProgress();
            }
          } catch (e) {
            console.error('Error parsing JSON chunk', e);
          }
        }
      }
    } catch (err) {
      console.error('Chat stream error:', err);
      if (aiNode) aiNode.textContent = 'Connection error.';
      setProgress(0, 'Error');
    } finally {
      isProcessing = false;
    }
  };

  const runSimulation = async () => {
    if (isProcessing) return;
    isProcessing = true;

    setProgress(25, 'Building AI vs AI negotiation...');

    try {
      const response = await fetch('/api/sandbox/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, turns: 8 })
      });

      const data = await response.json();

      if (!response.ok) {
        setProgress(0, data.detail || 'Simulation failed.');
        return;
      }

      const transcript = data.transcript || [];
      for (let i = 0; i < transcript.length; i += 1) {
        const item = transcript[i];
        appendMessage(item.role, item.text || item.content || '');
        if (chatPanel) chatPanel.scrollTop = chatPanel.scrollHeight;
        await new Promise((resolve) => setTimeout(resolve, 220));
        setProgress(
          Math.min(95, 25 + Math.floor(((i + 1) / Math.max(transcript.length, 1)) * 65)),
          'Animating negotiation...'
        );
      }

      if (data.audit?.summary) {
        appendMessage('system', data.audit.summary);
      }

      setProgress(100, 'Simulation complete');
      resetProgress();
    } catch (err) {
      console.error('Simulation request failed:', err);
      setProgress(0, 'Error');
    } finally {
      isProcessing = false;
    }
  };

  // Initial UI state
  refreshScenarioVisibility();

  if (mode === 'sandbox') {
    if (!getHasContext()) {
      lockWorkflow();
      if (summaryPanel) summaryPanel.classList.add('hidden');
    } else {
      unlockWorkflow();
      if (summaryPanel) summaryPanel.classList.remove('hidden');
    }
  }

  // Events
  sourceType?.addEventListener('change', () => {
    resetScenarioStateForSourceChange();
    refreshScenarioVisibility();
  });

  analyzerMode?.addEventListener('change', () => {
    resetScenarioStateForSourceChange();
  });

  scenarioForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    await prepareScenario();
  });

  sendBtn?.addEventListener('click', () => streamChat('chat'));
  runSimulationBtn?.addEventListener('click', () => runSimulation());

  document.querySelectorAll('[data-action]').forEach((button) => {
    button.addEventListener('click', () => {
      const action = button.getAttribute('data-action') || 'chat';

      if (action === 'help' || action === 'coach') {
        if (input && !input.value.trim()) {
          input.value =
            action === 'help'
              ? 'Please give me a tactical hint for this situation.'
              : 'Coach me on the next best move.';
        }
      }

      streamChat(action);
    });
  });

  input?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      streamChat('chat');
    }
  });

  setProgress(0, 'Ready');
});