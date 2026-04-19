document.addEventListener('DOMContentLoaded', () => {
  const workspaceLayout = document.getElementById('workspace-layout');
  const workspaceSidebar = document.getElementById('workspace-session-sidebar');
  const workspaceSidebarToggle = document.getElementById('workspace-sidebar-toggle');
  const SIDEBAR_LS_KEY = 'workspaceHistorySidebarExpanded';

  if (workspaceLayout && workspaceSidebar && workspaceSidebarToggle) {
    const applySidebarCollapsed = (collapsed) => {
      workspaceLayout.classList.toggle('sidebar-collapsed', collapsed);
      workspaceSidebar.classList.toggle('is-collapsed', collapsed);
      workspaceSidebarToggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      workspaceSidebarToggle.setAttribute('title', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
      try {
        localStorage.setItem(SIDEBAR_LS_KEY, collapsed ? 'false' : 'true');
      } catch (_) {
        /* ignore */
      }
    };

    try {
      if (localStorage.getItem(SIDEBAR_LS_KEY) === 'false') {
        applySidebarCollapsed(true);
      }
    } catch (_) {
      /* ignore */
    }

    workspaceSidebarToggle.addEventListener('click', () => {
      applySidebarCollapsed(!workspaceSidebar.classList.contains('is-collapsed'));
    });
  }

  workspaceLayout?.addEventListener('click', async (e) => {
    const delBtn = e.target.closest('[data-delete-session]');
    if (!delBtn) return;
    e.preventDefault();
    e.stopPropagation();
    const sid = delBtn.getAttribute('data-delete-session');
    if (!sid) return;
    if (!window.confirm('Delete this session and all saved messages? This cannot be undone.')) return;
    try {
      const res = await fetch('/api/session/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sid }),
      });
      if (!res.ok) {
        window.alert('Could not delete session.');
        return;
      }
      const rootEl = document.getElementById('workspace-root');
      const currentSid = rootEl?.dataset.session || '';
      const mode = rootEl?.dataset.mode || 'sandbox';
      if (sid === currentSid) {
        window.location.assign(`/workspace/${encodeURIComponent(mode)}`);
      } else {
        delBtn.closest('.workspace-sidebar-row')?.remove();
      }
    } catch (err) {
      console.error(err);
      window.alert('Could not delete session.');
    }
  });

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
  let sessionId = String(root.dataset.session || '').trim();

  const getPracticeRole = () => (root.dataset.practiceRole || 'seller').toLowerCase();

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
  const startPracticeBtn = document.getElementById('start-practice-btn');
  const analyzeBtn = document.getElementById('analyze-btn');
  const mentorToggle = document.getElementById('mentor-toggle');
  const difficultySelect = document.getElementById('difficulty-select');
  const chipDifficulty = document.getElementById('chip-difficulty');
  const chipMentor = document.getElementById('chip-mentor');
  const negotiationWorkspaceBadge = document.getElementById('negotiation-workspace-badge');

  const isMentorEnabled = () => (mentorToggle ? Boolean(mentorToggle.checked) : true);
  const getDifficulty = () => {
    const value = String(difficultySelect?.value || 'medium').toLowerCase();
    return ['simple', 'medium', 'hard'].includes(value) ? value : 'medium';
  };

  let simApiHist = [];
  const newSimState = () => ({
    public_transcript: [],
    next_speaker: 'buyer',
    buyer_private_context: {},
    seller_private_context: {},
    demo_script: [],
    demo_script_cursor: 0
  });
  let simState = newSimState();
  let simInProgress = false;

  const form = document.getElementById('scenario-form');
  const sourceType = document.getElementById('source-type');
  const analyzerMode = document.getElementById('analyzer-mode');
  const scenarioBrief = document.getElementById('scenario-brief');

  const applyReturnedSessionId = (newId) => {
    const id = String(newId || '').trim();
    if (!id) return;
    if (id === sessionId) return;
    sessionId = id;
    root.dataset.session = id;
    const hid = form?.querySelector('input[name="session_id"]');
    if (hid) hid.value = id;
    const url = new URL(window.location.href);
    url.pathname = `/workspace/${encodeURIComponent(mode)}`;
    url.searchParams.set('session_id', id);
    window.history.replaceState(null, '', `${url.pathname}?${url.searchParams.toString()}`);
  };

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

  const syncWorkspaceStepper = () => {
    const has = getHasContext();
    document.querySelectorAll('.workspace-stepper [data-ws-step]').forEach((el) => {
      const step = el.getAttribute('data-ws-step');
      el.classList.remove('is-active', 'is-complete', 'is-upcoming');
      if (!has) {
        if (step === '1') el.classList.add('is-active');
        else el.classList.add('is-upcoming');
      } else if (step === '3') {
        el.classList.add('is-active');
      } else {
        el.classList.add('is-complete');
      }
    });
  };

  const updateRunContextChips = () => {
    if (chipDifficulty) {
      const d = getDifficulty();
      const label = d.charAt(0).toUpperCase() + d.slice(1);
      chipDifficulty.textContent = `Difficulty: ${label}`;
    }
    if (chipMentor) {
      const on = isMentorEnabled();
      chipMentor.textContent = on ? 'Mentor: on' : 'Mentor: off';
      chipMentor.classList.toggle('run-chip--off', !on);
    }
  };

  const syncNegotiationWorkspaceBadge = () => {
    if (!negotiationWorkspaceBadge) return;
    const has = getHasContext();
    negotiationWorkspaceBadge.textContent = has ? 'Enabled' : 'Locked';
    negotiationWorkspaceBadge.classList.toggle('ready', has);
    negotiationWorkspaceBadge.classList.toggle('locked', !has);
  };

  const syncWorkspaceChrome = () => {
    syncWorkspaceStepper();
    updateRunContextChips();
    syncNegotiationWorkspaceBadge();
  };

  const setHasContext = (value) => {
    root.dataset.hasContext = value ? 'true' : 'false';
    syncWorkspaceChrome();
  };

  const setAnalyzeBusy = (busy) => {
    if (form) {
      form.classList.toggle('is-analyzing', busy);
      form.setAttribute('aria-busy', busy ? 'true' : 'false');
    }
    if (analyzeBtn) {
      analyzeBtn.classList.toggle('is-loading', busy);
      analyzeBtn.setAttribute('aria-busy', busy ? 'true' : 'false');
      analyzeBtn.disabled = busy;
    }
    [sourceType, analyzerMode, difficultySelect].forEach((el) => {
      if (el) el.disabled = busy;
    });
    if (mentorToggle) mentorToggle.disabled = busy;
    if (scenarioBrief) scenarioBrief.disabled = busy;
    const fileInput = form?.querySelector('input[type="file"]');
    if (fileInput) fileInput.disabled = busy;
    const libSelect = form?.querySelector('select[name="scenario_key"]');
    if (libSelect) libSelect.disabled = busy;
  };

  const clearStreamActionLoading = () => {
    sendBtn?.classList.remove('is-loading');
    sendBtn?.removeAttribute('aria-busy');
    startPracticeBtn?.classList.remove('is-loading');
    startPracticeBtn?.removeAttribute('aria-busy');
    document.querySelectorAll('[data-action="help"], [data-action="coach"]').forEach((btn) => {
      btn.classList.remove('is-loading');
      btn.removeAttribute('aria-busy');
    });
  };

  const setStreamActionLoading = (action) => {
    clearStreamActionLoading();
    if (action === 'chat' && sendBtn) {
      sendBtn.classList.add('is-loading');
      sendBtn.setAttribute('aria-busy', 'true');
    } else if (action === 'start' && startPracticeBtn) {
      startPracticeBtn.classList.add('is-loading');
      startPracticeBtn.setAttribute('aria-busy', 'true');
    } else if (action === 'help' || action === 'coach') {
      document.querySelectorAll(`[data-action="${action}"]`).forEach((btn) => {
        btn.classList.add('is-loading');
        btn.setAttribute('aria-busy', 'true');
      });
    }
  };

  const setFinishButtonsDisabled = (disabled) => {
    document.querySelectorAll('[data-open-finish-dialog]').forEach((btn) => {
      btn.disabled = disabled;
    });
  };

  const hasPracticeChatRows = () => Boolean(chatPanel?.querySelector('.message-row'));

  const refreshPracticeStartButton = () => {
    if (!startPracticeBtn || mode !== 'real_case') return;
    const analyzed = getHasContext();
    const canStart = analyzed && !hasPracticeChatRows();
    startPracticeBtn.disabled = !canStart;
    if (!analyzed) {
      startPracticeBtn.title =
        'Choose a scenario source, then click Analyze Scenario. Start is available only after analysis completes.';
    } else if (hasPracticeChatRows()) {
      startPracticeBtn.title = 'Negotiation already begun. Use the composer to continue, or Finish to clear chat.';
    } else if (getPracticeRole() === 'seller') {
      startPracticeBtn.title = 'Begin practice: the AI buyer opens the conversation first.';
    } else {
      startPracticeBtn.title = 'Begin practice: the AI seller opens the conversation first.';
    }
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
    if (startPracticeBtn) startPracticeBtn.disabled = true;
    if (sendBtn) sendBtn.disabled = true;
    if (input) input.disabled = true;
    setFinishButtonsDisabled(true);
  };

  const unlockWorkflow = () => {
    if (sendBtn) sendBtn.disabled = false;
    if (input) input.disabled = false;
    setFinishButtonsDisabled(false);
    refreshSandboxSimButtons();
    refreshPracticeStartButton();
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
      if (mode === 'sandbox') return 'AI Seller';
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
      const details = document.createElement('details');
      details.className = 'mentor-bubble-details';
      details.open = true;
      const sum = document.createElement('summary');
      sum.className = 'mentor-bubble-summary';
      sum.textContent = 'Full coaching text';
      const region = document.createElement('div');
      region.className = 'bubble-text mentor-body mentor-scroll-region';
      region.textContent = String(text || '').trim();
      details.appendChild(sum);
      details.appendChild(region);
      bubble.appendChild(meta);
      bubble.appendChild(details);
      row.appendChild(bubble);
      if (auditSummary) {
        const audit = document.createElement('div');
        audit.className = 'audit-chip';
        audit.textContent = auditSummary;
        bubble.appendChild(audit);
      }
      chatPanel.appendChild(row);
      chatPanel.scrollTop = chatPanel.scrollHeight;
      return { row, bubble, body: region };
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
    summaryPanel?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
    simState = newSimState();
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

    // Snapshot before setAnalyzeBusy: disabled fields are omitted from FormData (422 if source_type / analyzer_mode missing).
    const formData = new FormData(form);

    isProcessing = true;
    lockWorkflow();
    setAnalyzeBusy(true);
    setProgress(20, 'Analyzing...');
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
      applyReturnedSessionId(data.session_id);
      simApiHist = [];
      simState = newSimState();
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
      setAnalyzeBusy(false);
      unlockWorkflow();
    }
  };

  const streamChat = async (action = 'chat') => {
    if (isProcessing) return;

    const message = (input?.value || '').trim();
    if (action === 'chat' && !message) return;

    if (action === 'start') {
      if (mode !== 'real_case' || !getHasContext() || hasPracticeChatRows()) return;
    }

    if (action === 'chat' && !getHasContext()) {
      if (mode === 'real_case' || (mode === 'sandbox' && sourceType?.value === 'paste')) {
        await analyzeScenarioFromComposer(message);
        if (input) input.value = '';
        return;
      }
      return;
    }

    isProcessing = true;
    setStreamActionLoading(action);

    let lastUserBubble = null;
    if (message) {
      const userEl = appendMessage('user', message);
      lastUserBubble = userEl?.bubble || null;
    }
    if (input) input.value = '';

    const aiNode = appendMessage('assistant', '', '', true);
    if (action === 'start' && mode === 'real_case') {
      setProgress(
        18,
        getPracticeRole() === 'seller' ? 'AI Buyer is opening...' : 'AI Seller is opening...'
      );
    } else {
      setProgress(18, 'Sending to model...');
    }

    try {
      const chatBody = {
        session_id: sessionId,
        mode,
        message,
        action
      };
      if (mode === 'real_case') {
        chatBody.practice_role = getPracticeRole();
        chatBody.difficulty = getDifficulty();
        chatBody.mentor = isMentorEnabled();
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
              if (mode === 'real_case' && payload.user_audit?.summary && lastUserBubble) {
                const aud = document.createElement('div');
                aud.className = 'audit-chip';
                aud.textContent = payload.user_audit.summary;
                lastUserBubble.appendChild(aud);
              } else if (mode !== 'real_case' && payload.audit?.summary && aiNode?.bubble) {
                const audit = document.createElement('div');
                audit.className = 'audit-chip';
                audit.textContent = payload.audit.summary;
                aiNode.bubble.appendChild(audit);
              }
              if (isMentorEnabled() && payload.mentor_insight && String(payload.mentor_insight).trim()) {
                appendMessage('mentor', String(payload.mentor_insight).trim());
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
      clearStreamActionLoading();
      if (mode === 'real_case') refreshPracticeStartButton();
    }
  };

  const analyzeScenarioFromComposer = async (message) => {
    if (!form || isProcessing) return;

    const formData = new FormData(form);
    formData.set('source_type', 'paste');
    formData.set('content', message);

    isProcessing = true;
    lockWorkflow();
    setAnalyzeBusy(true);
    setProgress(20, 'Analyzing pasted case...');

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
      applyReturnedSessionId(data.session_id);
      simApiHist = [];
      simState = newSimState();
      simInProgress = false;

      setProgress(100, 'Scenario ready');
      resetProgress();
    } catch (err) {
      console.error(err);
      setProgress(0, err?.name === 'AbortError' ? 'Timed out — try No LLM or shorter text' : 'Error');
    } finally {
      window.clearTimeout(abortTimer);
      isProcessing = false;
      setAnalyzeBusy(false);
      unlockWorkflow();
    }
  };

  // Keep in sync with data/config.txt [demo_simulate] turns_default (server default for /simulate-step).
  const DEMO_TURNS = 18;
  const clearMentorMessagesInChat = () => {
    if (!chatPanel) return;
    chatPanel.querySelectorAll('.message-row.mentor').forEach((node) => node.remove());
  };

  /** One model call = one negotiation line; must hit /simulate-step (not legacy /simulate). */
  const fetchSandboxSimulateStep = async (apiHistPayload, simulationStatePayload) => {
    const res = await fetch('/api/sandbox/simulate-step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        turns: DEMO_TURNS,
        api_hist: apiHistPayload,
        simulation_state: simulationStatePayload,
        mentor: isMentorEnabled(),
        difficulty: getDifficulty()
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
    if (runBtn) {
      runBtn.classList.add('is-loading');
      runBtn.setAttribute('aria-busy', 'true');
    }
    refreshSandboxSimButtons();
    setProgress(22, 'Generating DEMO conversation (Demo_AI_negotiation, turn 1/16–20)...');

    try {
      if (chatPanel) chatPanel.innerHTML = '';
      hideChatEmptyState();
      simApiHist = [];
      simState = newSimState();
      simInProgress = true;
      refreshSandboxSimButtons();

      const { ok, data, staleClient } = await fetchSandboxSimulateStep([], simState);

      if (!ok) {
        simInProgress = false;
        simApiHist = [];
        simState = newSimState();
        setProgress(0, staleClient ? 'Hard refresh page (Ctrl+Shift+R)' : 'Simulation failed');
        refreshSandboxSimButtons();
        return;
      }

      simApiHist = data.api_hist || [];
      simState = data.simulation_state || simState;
      if (data.item) {
        appendMessage(data.item.role, data.item.text || '');
      }
      if (isMentorEnabled() && data.mentor_insight && String(data.mentor_insight).trim()) {
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
      simState = newSimState();
      setProgress(0, 'Error');
    } finally {
      isProcessing = false;
      if (runBtn) {
        runBtn.classList.remove('is-loading');
        runBtn.removeAttribute('aria-busy');
      }
      refreshSandboxSimButtons();
    }
  };

  const nextDemoSimulationTurn = async () => {
    if (isProcessing || mode !== 'sandbox' || !simInProgress) return;
    isProcessing = true;
    if (simNextBtn) {
      simNextBtn.classList.add('is-loading');
      simNextBtn.setAttribute('aria-busy', 'true');
    }
    refreshSandboxSimButtons();
    setProgress(35, 'Generating next turn...');

    try {
      const { ok, data, staleClient } = await fetchSandboxSimulateStep(simApiHist, simState);

      if (!ok) {
        setProgress(0, staleClient ? 'Hard refresh page (Ctrl+Shift+R)' : 'Simulation failed');
        return;
      }

      simApiHist = data.api_hist || simApiHist;
      simState = data.simulation_state || simState;
      if (data.item) {
        appendMessage(data.item.role, data.item.text || '');
      }
      if (isMentorEnabled() && data.mentor_insight && String(data.mentor_insight).trim()) {
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
      if (simNextBtn) {
        simNextBtn.classList.remove('is-loading');
        simNextBtn.removeAttribute('aria-busy');
      }
      refreshSandboxSimButtons();
    }
  };

  const clearPracticeChatUi = () => {
    if (!chatPanel) return;
    const demoHint =
      mode === 'sandbox'
        ? 'Scenario is still loaded.<br>Use <strong>Start DEMO (step-by-step)</strong> to run again.'
        : 'Scenario is still loaded.<br>Start a new negotiation thread below.';
    chatPanel.innerHTML = `
      <div id="chat-empty-state" class="chat-empty-state">
        <div class="empty-state-icon">◈</div>
        <h4>Ready to continue</h4>
        <p>${demoHint}</p>
      </div>`;
  };

  // Initial state
  refreshScenarioUI();
  refreshAnalyzerCaption();
  if (mode === 'real_case') {
    setPracticeRole(getPracticeRole());
    refreshPracticeStartButton();
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
      refreshPracticeStartButton();
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
          simState = newSimState();
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

  startPracticeBtn?.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    await streamChat('start');
  });

  simNextBtn?.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    await nextDemoSimulationTurn();
  });

  difficultySelect?.addEventListener('change', () => {
    updateRunContextChips();
  });

  mentorToggle?.addEventListener('change', () => {
    updateRunContextChips();
    if (!isMentorEnabled()) {
      // Keep conversation turns intact; only hide mentor commentary when disabled.
      clearMentorMessagesInChat();
    }
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

  syncWorkspaceChrome();

  setProgress(0, 'Ready');
});