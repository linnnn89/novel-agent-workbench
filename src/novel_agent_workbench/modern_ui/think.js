const ThinkTrace = (() => {
  const WAITING = "请求已发出，正在等待模型返回内容。接口返回的思考文本会显示在这里；部分模型不提供思考文本。无需重复发送，可点击「停止任务」结束等待。";
  let jobId = 0;
  let activeJob = 0;
  let phase = "idle";
  let text = "";
  let dismissed = false;
  let bound = false;
  let startedAt = 0;
  let elapsed = 0;
  let expanded = false;
  let timer = null;
  let home = null;
  let homeNext = null;
  let follow = true;
  let scrollPosition = 0;

  function mount(host) {
    const bar = el("thinkBar");
    if (!bar) return;
    if (!home) { home = bar.parentNode; homeNext = bar.nextSibling; }
    if (host) host.appendChild(bar);
    else home.insertBefore(bar, homeNext);
  }

  function stopTimer() {
    if (timer !== null) clearInterval(timer);
    timer = null;
  }

  function el(id) {
    return document.getElementById(id);
  }

  function isActive(id) {
    return id == null || id === activeJob;
  }

  function seconds() {
    if (phase === "done" || phase === "failed") return elapsed;
    if (!startedAt) return 0;
    return Math.max(1, Math.round((Date.now() - startedAt) / 1000));
  }

  function titleForPhase() {
    if (phase === "thinking") return "正在思考";
    if (phase === "writing") return text ? "正在输出正文" : "模型已接入";
    if (phase === "done") return text ? "思考完成" : "没有思考链";
    if (phase === "failed") return "生成失败";
    return "等待模型接入";
  }

  function setExpanded(open) {
    expanded = Boolean(open);
    const body = el("thinkBarBody");
    const toggle = el("thinkBarToggle");
    if (body) {
      if (!body.hidden) scrollPosition = body.scrollTop;
      body.hidden = !expanded;
      if (expanded) body.scrollTop = follow ? body.scrollHeight : scrollPosition;
    }
    if (toggle) toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
  }

  function renderTime() {
    const meta = el("thinkBarMeta");
    if (!meta) return;
    const secs = seconds();
    meta.textContent = secs ? `${phase === "sent" ? "已等待 " : ""}${secs}s` : "";
  }

  function render() {
    const bar = el("thinkBar");
    const title = el("thinkBarTitle");
    const body = el("thinkBarBody");
    if (!bar || !title || !body) return;
    bar.classList.toggle("active", phase === "sent" || phase === "thinking" || phase === "writing");
    bar.classList.toggle("done", phase === "done");
    bar.classList.toggle("failed", phase === "failed");
    title.textContent = titleForPhase();
    renderTime();
    const content = text || ({
      thinking: "模型已接入，正在思考…",
      writing: "模型已接入，正在输出正文。这次没有单独的思考链。",
      done: "这次没有单独的思考链。",
      failed: "请求已结束。",
    }[phase] || WAITING);
    if (body.textContent !== content) {
      body.textContent = content;
      if (!body.hidden) body.scrollTop = follow ? body.scrollHeight : scrollPosition;
    }
  }

  function show() {
    const bar = el("thinkBar");
    if (bar) bar.hidden = false;
  }

  function hide() {
    const bar = el("thinkBar");
    if (bar) bar.hidden = true;
    setExpanded(false);
  }

  function start() {
    stopTimer();
    jobId += 1;
    activeJob = jobId;
    phase = "sent";
    text = "";
    dismissed = false;
    follow = true;
    scrollPosition = 0;
    startedAt = Date.now();
    elapsed = 0;
    render();
    setExpanded(true);
    show();
    timer = setInterval(renderTime, 1000);
    return activeJob;
  }

  function applyStatus(nextPhase) {
    if (!nextPhase || phase === "done" || phase === "failed") return;
    if (nextPhase === "sent" && (phase === "thinking" || phase === "writing")) return;
    if (nextPhase === "thinking" && phase === "writing") return;
    phase = nextPhase;
    render();
    if (!dismissed) show();
  }

  function append(chunk) {
    const piece = String(chunk || "");
    if (!piece || phase === "idle") return;
    if (phase !== "writing") phase = "thinking";
    text += piece;
    render();
    if (!dismissed) show();
  }

  function finish(ok) {
    if (phase === "idle") return;
    stopTimer();
    elapsed = startedAt ? Math.max(1, Math.round((Date.now() - startedAt) / 1000)) : 0;
    phase = ok === false ? "failed" : "done";
    render();
    if (!text || dismissed) {
      hide();
      return;
    }
    setExpanded(false);
    show();
  }

  function close() {
    dismissed = true;
    hide();
  }

  function dispose() {
    stopTimer();
    jobId += 1;
    activeJob = 0;
    phase = "idle";
    text = "";
    dismissed = false;
    startedAt = 0;
    elapsed = 0;
    hide();
    const body = el("thinkBarBody");
    if (body) body.textContent = "";
  }

  function handle(event, payload) {
    if (event !== "think_status" && event !== "think_chunk" && event !== "job_status" && event !== "reason_chunk") {
      return false;
    }
    if (phase === "idle") return true;
    const incomingJob = payload && payload.job_id != null ? payload.job_id : activeJob;
    if (!isActive(incomingJob)) return true;
    if (event === "think_chunk" || event === "reason_chunk") {
      append(payload && payload.text);
      return true;
    }
    applyStatus(payload && payload.phase);
    return true;
  }

  function bind() {
    if (bound) return;
    const toggle = el("thinkBarToggle");
    if (toggle) {
      toggle.addEventListener("click", () => {
        if (el("thinkBar")?.hidden) return;
        setExpanded(!expanded);
      });
    }
    const body = el("thinkBarBody");
    body?.addEventListener("scroll", () => {
      if (body.hidden || el("thinkBar")?.hidden) return;
      scrollPosition = body.scrollTop;
      follow = body.scrollHeight - body.clientHeight - body.scrollTop < 48;
    });
    bound = true;
  }

  return {
    mount,
    acceptJob(id) {
      activeJob = id;
    },
    start,
    finish,
    close,
    dispose,
    handle,
    bind,
    isOpen() {
      const bar = el("thinkBar");
      return Boolean(bar && !bar.hidden);
    },
    isIdle() {
      return phase === "idle" || phase === "done" || phase === "failed";
    },
  };
})();
window.ThinkTrace = ThinkTrace;
