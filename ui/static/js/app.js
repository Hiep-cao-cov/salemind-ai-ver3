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

  const getPracticeRole = () => (root.dataset.practiceRole || 'buyer').toLowerCase();

  const setPracticeRole = (role) => {
    const r = role === 'seller' ? 'seller' : 'buyer';
    root.dataset.practiceRole = r;
    document.querySelectorAll('.practice-role-radios input[type="radio"]').forEach((radio) => {
      radio.checked = radio.value === r;
    });
    document.querySelectorAll('.practice-role-radios label.radio-row').forEach((lab) => {
      const inp = lab.querySelector('input[type="radio"]');
      lab.classList.toggle('radio-row-checked', Boolean(inp && inp.checked));
    });
  };

  const refreshAnalyzerCaption = () => {
    const el = document.getElementById('model-info-value');
    const am = document.getElementById('analyzer-mode');
    if (!el || !am) return;
    const v = am.value;
    if (v === 'local_model') {
      el.textContent = root.dataset.analyzerLineLocal || '';
    } else if (v === 'cloud_model') {
      el.textContent = root.dataset.analyzerLineCloud || '';
    } else {
      el.textContent = root.dataset.analyzerLineNoLlm || '';
    }
  };

  const persistPracticeRole = async (role) => {
    if (mode !== 'real_case' || !sessionId) return;
    try {
      await fetch('/api/session/practice-role', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, practice_role: role }),
      });
    } catch (e) {
      console.error(e);
    }
  };

  const chatPanel = document.getElementById('chat-panel');
  const input = document.getElementById('message-input');
  const sendBtn = document.getElementById('send-btn');
  const runBtn = document.getElementById('run-simulation-btn');
  const simNextBtn = document.getElementById('sim-next-btn');

  let simApiHist = [];
  let simInProgress = false;

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

  const setFinishButtonsDisabled = (disabled) => {
    document.querySelectorAll('[data-open-finish-dialog]').forEach((btn) => {
      btn.disabled = disabled;
    });
  };

  const refreshSandboxSimButtons = () => {
    if (!runBtn || mode !== 'sandbox') return;
    if (!getHasContext()) {
      runBtn.disabled = true;
      if (simNextBtn) {
        simNextBtn.disabled = true;
        simNextBtn.classList.add('hidden');
      }
      return;
    }
    runBtn.disabled = simInProgress;
    if (simNextBtn) {
      simNextBtn.classList.toggle('hidden', !simInProgress);
      simNextBtn.disabled = !simInProgress || isProcessing;
    }
  };

  const lockWorkflow = () => {
    if (runBtn) runBtn.disabled = true;
    if (simNextBtn) simNextBtn.disabled = true;
    if (sendBtn) sendBtn.disabled = true;
    if (input) input.disabled = true;
    setFinishButtonsDisabled(true);
  };

  const unlockWorkflow = () => {
    if (sendBtn) sendBtn.disabled = false;
    if (input) input.disabled = false;
    setFinishButtonsDisabled(false);
    refreshSandboxSimButtons();
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
    if (role === 'mentor') return 'Mentor';
    if (role === 'system') return 'System';
    if (role === 'assistant') {
      if (mode === 'real_case' && getPracticeRole() === 'seller') return 'AI Buyer';
      if (mode === 'real_case' && getPracticeRole() === 'buyer') return 'AI Sales';
      return 'AI Assistant';
    }
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
    } else if (role === 'mentor') {
      body.classList.add('mentor-body');
      body.textContent = String(text || '').trim();
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
    hideSummary();
    setHasContext(false);
    simApiHist = [];
    simInProgress = false;

    if (generatedScenarioWrap) generatedScenarioWrap.classList.add('hidden');
    if (generatedScenario) generatedScenario.textContent = '';

    if (summaryKeyPoints) summaryKeyPoints.innerHTML = '';
    if (summaryNegotiationPoints) summaryNegotiationPoints.innerHTML = '';
    if (summaryTitle) summaryTitle.textContent = '';
    if (summarySource) summarySource.textContent = '';
    if (summaryCopy) summaryCopy.textContent = '';

    unlockWorkflow();
  };

  const analyzeScenario = async () => {
    if (!form || isProcessing) return;

    isProcessing = true;
    lockWorkflow();
    setProgress(20, 'Analyzing...');

    const formData = new FormData(form);
    const abortCtrl = new AbortController();
    const abortTimer = window.setTimeout(() => abortCtrl.abort(), 180000);

    try {
      const res = await fetch('/api/scenario/prepare', {
        method: 'POST',
        body: formData,
        signal: abortCtrl.signal
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok || !data.ok) {
        setProgress(0, 'Error');
        return;
      }

      renderSummary(data.context);
      simApiHist = [];
      simInProgress = false;

      if (scenarioBrief) scenarioBrief.classList.add('hidden');

      setProgress(100, 'Scenario ready');
      resetProgress();
    } catch (e) {
      console.error(e);
      setProgress(0, e?.name === 'AbortError' ? 'Timed out — try No LLM or shorter text' : 'Error');
    } finally {
      window.clearTimeout(abortTimer);
      isProcessing = false;
      unlockWorkflow();
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
      if (simInProgress) {
        await nextDemoSimulationTurn();
      } else {
        await startDemoSimulation();
      }
      return;
    }

    isProcessing = true;

    if (message) appendMessage('user', message);
    if (input) input.value = '';

    const aiNode = appendMessage('assistant', '', '', true);
    setProgress(18, 'Sending to model...');

    try {
      const chatBody = {
        session_id: sessionId,
        mode,
        message,
        action
      };
      if (mode === 'real_case') {
        chatBody.practice_role = getPracticeRole();
      }

      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(chatBody)
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

    const abortCtrl = new AbortController();
    const abortTimer = window.setTimeout(() => abortCtrl.abort(), 180000);

    try {
      const res = await fetch('/api/scenario/prepare', {
        method: 'POST',
        body: formData,
        signal: abortCtrl.signal
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok || !data.ok) {
        setProgress(0, 'Error');
        return;
      }

      renderSummary(data.context);
      simApiHist = [];
      simInProgress = false;

      setProgress(100, 'Scenario ready');
      resetProgress();
    } catch (err) {
      console.error(err);
      setProgress(0, err?.name === 'AbortError' ? 'Timed out — try No LLM or shorter text' : 'Error');
    } finally {
      window.clearTimeout(abortTimer);
      isProcessing = false;
      unlockWorkflow();
    }
  };

  const DEMO_TURNS = 18;

  /** One model call = one negotiation line; must hit /simulate-step (not legacy /simulate). */
  const fetchSandboxSimulateStep = async (apiHistPayload) => {
    const res = await fetch('/api/sandbox/simulate-step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        turns: DEMO_TURNS,
        api_hist: apiHistPayload,
        mentor: true
      })
    });
    const data = await res.json().catch(() => ({}));

    if (Array.isArray(data.transcript) && !Object.prototype.hasOwnProperty.call(data, 'item')) {
      console.error(
        '[DEMO] Stale client: received full /simulate payload. Hard refresh (Ctrl+Shift+R) to load app.js with step-by-step DEMO.'
      );
      return {
        ok: false,
        staleClient: true,
        data
      };
    }

    if (!res.ok || !data.ok) {
      return { ok: false, data };
    }

    return { ok: true, data };
  };

  const startDemoSimulation = async () => {
    if (isProcessing || mode !== 'sandbox') return;
    isProcessing = true;
    refreshSandboxSimButtons();
    setProgress(28, 'Starting DEMO (turn 1)...');

    try {
      if (chatPanel) chatPanel.innerHTML = '';
      hideChatEmptyState();
      simApiHist = [];
      simInProgress = true;
      refreshSandboxSimButtons();

      const { ok, data, staleClient } = await fetchSandboxSimulateStep([]);

      if (!ok) {
        simInProgress = false;
        simApiHist = [];
        setProgress(0, staleClient ? 'Hard refresh page (Ctrl+Shift+R)' : 'Simulation failed');
        refreshSandboxSimButtons();
        return;
      }

      simApiHist = data.api_hist || [];
      if (data.item) {
        appendMessage(data.item.role, data.item.text || '');
      }
      if (data.mentor_insight && String(data.mentor_insight).trim()) {
        appendMessage('mentor', String(data.mentor_insight).trim());
      }
      if (data.done && data.audit?.summary) {
        appendMessage('system', data.audit.summary, data.audit.summary);
        simInProgress = false;
      }

      setProgress(100, data.done ? 'DEMO complete' : 'Press Next turn to continue');
      resetProgress();
    } catch (e) {
      console.error(e);
      simInProgress = false;
      simApiHist = [];
      setProgress(0, 'Error');
    } finally {
      isProcessing = false;
      refreshSandboxSimButtons();
    }
  };

  const nextDemoSimulationTurn = async () => {
    if (isProcessing || mode !== 'sandbox' || !simInProgress) return;
    isProcessing = true;
    refreshSandboxSimButtons();
    setProgress(35, 'Generating next turn...');

    try {
      const { ok, data, staleClient } = await fetchSandboxSimulateStep(simApiHist);

      if (!ok) {
        setProgress(0, staleClient ? 'Hard refresh page (Ctrl+Shift+R)' : 'Simulation failed');
        return;
      }

      simApiHist = data.api_hist || simApiHist;
      if (data.item) {
        appendMessage(data.item.role, data.item.text || '');
      }
      if (data.mentor_insight && String(data.mentor_insight).trim()) {
        appendMessage('mentor', String(data.mentor_insight).trim());
      }
      if (data.done && data.audit?.summary) {
        appendMessage('system', data.audit.summary, data.audit.summary);
        simInProgress = false;
      }

      setProgress(100, data.done ? 'DEMO complete' : 'Press Next turn to continue');
      resetProgress();
    } catch (e) {
      console.error(e);
      setProgress(0, 'Error');
    } finally {
      isProcessing = false;
      refreshSandboxSimButtons();
    }
  };

  const clearPracticeChatUi = () => {
    if (!chatPanel) return;
    chatPanel.innerHTML = `
      <div id="chat-empty-state" class="chat-empty-state">
        <div class="empty-state-icon">◈</div>
        <h4>Ready to continue</h4>
        <p>Scenario is still loaded.<br>Start a new negotiation thread below.</p>
      </div>`;
  };

  // Initial state
  refreshScenarioUI();
  refreshAnalyzerCaption();
  if (mode === 'real_case') {
    setPracticeRole(getPracticeRole());
  }

  if (mode === 'sandbox') {
    if (!getHasContext()) {
      lockWorkflow();
      hideSummary();
    } else {
      unlockWorkflow();
      showSummary();
    }
    refreshSandboxSimButtons();
  }

  document.querySelectorAll('.practice-role-radios input[type="radio"]').forEach((radio) => {
    radio.addEventListener('change', () => {
      if (!radio.checked) return;
      const value = radio.value;
      if (value !== 'buyer' && value !== 'seller') return;
      setPracticeRole(value);
      persistPracticeRole(value);
    });
  });

  const finishDialog = document.getElementById('finish-negotiation-dialog');
  const finishCancelBtn = document.getElementById('finish-dialog-cancel');

  document.querySelectorAll('[data-open-finish-dialog]').forEach((btn) => {
    btn.addEventListener('click', () => {
      finishDialog?.showModal();
    });
  });

  finishCancelBtn?.addEventListener('click', () => {
    finishDialog?.close();
  });

  document.querySelectorAll('.finish-option-btn[data-finish-resolution]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const resolution = btn.getAttribute('data-finish-resolution');
      if (!resolution || !sessionId) return;
      setProgress(30, 'Updating session...');
      try {
        const res = await fetch('/api/session/finish-negotiation', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId, resolution }),
        });
        if (!res.ok) {
          setProgress(0, 'Could not finish');
          return;
        }
        finishDialog?.close();
        if (resolution === 'full_reset') {
          window.location.reload();
          return;
        }
        clearPracticeChatUi();
        if (mode === 'sandbox') {
          simApiHist = [];
          simInProgress = false;
          refreshSandboxSimButtons();
        }
        setHasContext(true);
        unlockWorkflow();
        showSummary();
        setProgress(100, 'Chat cleared');
        resetProgress();
      } catch (e) {
        console.error(e);
        setProgress(0, 'Error');
      }
    });
  });

  // Events
  sourceType?.addEventListener('change', () => {
    resetScenarioState();
    refreshScenarioUI();
  });

  analyzerMode?.addEventListener('change', () => {
    refreshAnalyzerCaption();
    resetScenarioState();
  });

  form?.addEventListener('submit', (e) => {
    e.preventDefault();
    analyzeScenario();
  });

  sendBtn?.addEventListener('click', () => {
    streamChat('chat');
  });

  runBtn?.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    await startDemoSimulation();
  });

  simNextBtn?.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    await nextDemoSimulationTurn();
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