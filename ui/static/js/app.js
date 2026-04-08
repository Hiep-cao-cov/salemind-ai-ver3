document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('workspace-root');
  const progressFill = document.getElementById('progress-fill');
  const progressLabel = document.getElementById('progress-label');

  let isProcessing = false;

  const setProgress = (value, label) => {
    if (progressFill) progressFill.style.width = `${value}%`;
    if (progressLabel) progressLabel.textContent = label;
  };

  const resetProgress = (delay = 900) => {
    window.setTimeout(() => setProgress(0, 'Ready'), delay);
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
  const generatedScenarioWrap = document.getElementById('generated-scenario-wrap');
  const generatedScenario = document.getElementById('generated-scenario');

  const chatEmptyState = document.getElementById('chat-empty-state');

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

  const hideChatEmptyState = () => {
    if (chatEmptyState) chatEmptyState.classList.add('hidden');
  };

  const labelForRole = (role) => {
    if (role === 'user') return 'You';
    if (role === 'buyer_ai') return 'AI Buyer';
    if (role === 'sales_ai') return 'AI Sales';
    if (role === 'system') return 'System';
    if (role === 'assistant') return 'AI Assistant';
    return 'AI Coach';
  };

  const appendMessage = (role, text = '', auditSummary = '', typing = false) => {
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

    return { row, bubble, body };
  };

  const renderSummary = (ctx) => {
    if (!ctx) return;

    showSummary();

    if (summaryTitle) summaryTitle.textContent = ctx.title || '';
    if (summarySource) summarySource.textContent = ctx.source_name || '';
    if (summaryCopy) summaryCopy.textContent = ctx.summary || '';

    if (summaryKeyPoints) {
      summaryKeyPoints.innerHTML = (ctx.key_points || []).map((x) => `<li>${x}</li>`).join('');
    }

    if (summaryNegotiationPoints) {
      summaryNegotiationPoints.innerHTML = (ctx.negotiation_points || []).map((x) => `<li>${x}</li>`).join('');
    }

    if (generatedScenarioWrap && generatedScenario) {
      if (ctx.generated_scenario) {
        generatedScenarioWrap.classList.remove('hidden');
        generatedScenario.textContent = ctx.generated_scenario;
      } else {
        generatedScenarioWrap.classList.add('hidden');
        generatedScenario.textContent = '';
      }
    }

    setHasContext(true);
  };

  const refreshScenarioUI = () => {
    if (!sourceType) return;

    const value = sourceType.value;

    if (scenarioLibraryWrap) {
      scenarioLibraryWrap.classList.toggle('hidden', value !== 'library');
    }

    if (scenarioFileWrap) {
      scenarioFileWrap.classList.toggle('hidden', value !== 'upload');
    }

    if (scenarioBrief) {
      if (mode === 'sandbox') {
        scenarioBrief.classList.toggle('hidden', !(value === 'upload' || value === 'paste'));

        if (value === 'paste') {
          scenarioBrief.placeholder = 'Paste your scenario here...';
        } else if (value === 'upload') {
          scenarioBrief.placeholder = 'Optional note for uploaded scenario...';
        }
      } else if (mode === 'real_case') {
        scenarioBrief.classList.toggle('hidden', value !== 'paste');

        if (value === 'paste') {
          scenarioBrief.placeholder = 'Paste your real case here...';
        }
      } else {
        scenarioBrief.classList.add('hidden');
      }
    }
  };

  const resetScenarioState = () => {
    lockWorkflow();
    hideSummary();
    setHasContext(false);

    if (generatedScenarioWrap) generatedScenarioWrap.classList.add('hidden');
    if (generatedScenario) generatedScenario.textContent = '';

    if (summaryKeyPoints) summaryKeyPoints.innerHTML = '';
    if (summaryNegotiationPoints) summaryNegotiationPoints.innerHTML = '';
    if (summaryTitle) summaryTitle.textContent = '';
    if (summarySource) summarySource.textContent = '';
    if (summaryCopy) summaryCopy.textContent = '';
  };

  const analyzeScenario = async () => {
    if (!form || isProcessing) return;

    isProcessing = true;
    lockWorkflow();
    setProgress(20, 'Analyzing...');

    const formData = new FormData(form);

    try {
      const res = await fetch('/api/scenario/prepare', {
        method: 'POST',
        body: formData
      });

      const data = await res.json();

      if (!res.ok || !data.ok) {
        setProgress(0, 'Error');
        return;
      }

      renderSummary(data.context);

      if (scenarioBrief) scenarioBrief.classList.add('hidden');

      unlockWorkflow();
      setProgress(100, 'Scenario ready');
      resetProgress();
    } catch (e) {
      console.error(e);
      setProgress(0, 'Error');
    } finally {
      isProcessing = false;
    }
  };

  const streamChat = async (action = 'chat') => {
    if (isProcessing) return;

    const message = (input?.value || '').trim();
    if (action === 'chat' && !message) return;

    if (action === 'chat' && !getHasContext()) {
      if (mode === 'real_case' || (mode === 'sandbox' && sourceType?.value === 'paste')) {
        await analyzeScenarioFromComposer(message);
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
    setProgress(18, 'Sending to model...');

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          mode,
          message,
          action
        })
      });

      if (!response.ok || !response.body) {
        const errorText = await response.text();
        if (aiNode?.body) aiNode.body.textContent = errorText || 'Request failed.';
        setProgress(0, 'Request failed');
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let streamed = '';

      setProgress(35, 'AI is responding...');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split('\n');
        buffer = chunks.pop() || '';

        for (const chunk of chunks) {
          const trimmed = chunk.trim();
          if (!trimmed.startsWith('data: ')) continue;

          try {
            const payload = JSON.parse(trimmed.slice(6));

            if (payload.token) {
              if (streamed === '' && aiNode?.body) {
                aiNode.body.textContent = '';
              }
              streamed += payload.token;
              if (aiNode?.body) aiNode.body.textContent = streamed;

              setProgress(
                Math.min(92, 35 + Math.floor(streamed.length / 8)),
                'Streaming response...'
              );

              if (chatPanel) chatPanel.scrollTop = chatPanel.scrollHeight;
            }

            if (payload.done) {
              if (payload.audit?.summary && aiNode?.bubble) {
                const audit = document.createElement('div');
                audit.className = 'audit-chip';
                audit.textContent = payload.audit.summary;
                aiNode.bubble.appendChild(audit);
              }
              setProgress(100, 'Completed');
              resetProgress();
            }
          } catch (err) {
            console.error('Error parsing SSE payload:', err);
          }
        }
      }
    } catch (err) {
      console.error('Chat streaming error:', err);
      if (aiNode?.body) aiNode.body.textContent = 'Connection error.';
      setProgress(0, 'Error');
    } finally {
      isProcessing = false;
    }
  };

  const analyzeScenarioFromComposer = async (message) => {
    if (!form || isProcessing) return;

    isProcessing = true;
    lockWorkflow();
    setProgress(20, 'Analyzing pasted case...');

    const formData = new FormData(form);
    formData.set('source_type', 'paste');
    formData.set('content', message);

    try {
      const res = await fetch('/api/scenario/prepare', {
        method: 'POST',
        body: formData
      });

      const data = await res.json();

      if (!res.ok || !data.ok) {
        setProgress(0, 'Error');
        return;
      }

      renderSummary(data.context);
      unlockWorkflow();

      setProgress(100, 'Scenario ready');
      resetProgress();
    } catch (err) {
      console.error(err);
      setProgress(0, 'Error');
    } finally {
      isProcessing = false;
    }
  };

  const runSimulation = async () => {
    if (isProcessing) return;
    isProcessing = true;

    setProgress(25, 'Running simulation...');

    try {
      const res = await fetch('/api/sandbox/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, turns: 8 })
      });

      const data = await res.json();

      if (!res.ok) {
        setProgress(0, 'Simulation failed');
        return;
      }

      if (chatPanel) {
        chatPanel.innerHTML = '';
      }
      hideChatEmptyState();

      const transcript = data.transcript || [];
      for (let i = 0; i < transcript.length; i += 1) {
        const msg = transcript[i];
        const text = msg.text || msg.content || '';
        appendMessage(msg.role, text);

        if (chatPanel) chatPanel.scrollTop = chatPanel.scrollHeight;

        await new Promise((resolve) => setTimeout(resolve, 220));

        setProgress(
          Math.min(95, 25 + Math.floor(((i + 1) / Math.max(transcript.length, 1)) * 65)),
          'Animating negotiation...'
        );
      }

      if (data.audit?.summary) {
        appendMessage('system', data.audit.summary, data.audit.summary);
      }

      setProgress(100, 'Simulation complete');
      resetProgress();
    } catch (e) {
      console.error(e);
      setProgress(0, 'Error');
    } finally {
      isProcessing = false;
    }
  };

  // Initial state
  refreshScenarioUI();

  if (mode === 'sandbox') {
    if (!getHasContext()) {
      lockWorkflow();
      hideSummary();
    } else {
      unlockWorkflow();
      showSummary();
    }
  }

  // Events
  sourceType?.addEventListener('change', () => {
    resetScenarioState();
    refreshScenarioUI();
  });

  analyzerMode?.addEventListener('change', () => {
    resetScenarioState();
  });

  form?.addEventListener('submit', (e) => {
    e.preventDefault();
    analyzeScenario();
  });

  sendBtn?.addEventListener('click', () => {
    streamChat('chat');
  });

  runBtn?.addEventListener('click', async () => {
    await runSimulation();
  });

  document.querySelectorAll('[data-action]').forEach((button) => {
    button.addEventListener('click', () => {
      const action = button.getAttribute('data-action') || 'chat';

      if ((action === 'help' || action === 'coach') && input && !input.value.trim()) {
        input.value =
          action === 'help'
            ? 'Please give me a tactical hint for this situation.'
            : 'Coach me on the next best move.';
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