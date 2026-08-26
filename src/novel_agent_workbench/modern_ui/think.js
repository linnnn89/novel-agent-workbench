const ThinkTrace = (() => {
  const WAITING = "请求已发出。模型接入后，思考链会显示在这里。在此之前请不要重复发送。";
  let jobId = 0;
  let activeJob = 0;
  let phase = "idle";
  let text = "";
  let dismissed = false;
  let bound = false;
  let startedAt = 0;
  let elapsed = 0;
  let expanded = false;

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
    if (body) body.hidden = !expanded;
    if (toggle) toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
  }

  function render() {
    const bar = el("thinkBar");
    const title = el("thinkBarTitle");
    const meta = el("thinkBarMeta");
    const body = el("thinkBarBody");
    if (!bar || !title || !body) return;
    bar.classList.toggle("active", phase === "sent" || phase === "thinking" || phase === "writing");
    bar.classList.toggle("done", phase === "done");
    bar.classList.toggle("failed", phase === "failed");
    title.textContent = titleForPhase();
    const secs = seconds();
    if (meta) {
      if (phase === "done" || phase === "failed") meta.textContent = secs ? `${secs}s` : "";
      else if (phase === "thinking" || phase === "writing") meta.textContent = secs ? `${secs}s` : "";
      else meta.textContent = "";
    }
    if (text) body.textContent = text;
    else if (phase === "thinking") body.textContent = "模型已接入，正在思考…";
    else if (phase === "writing") body.textContent = "模型已接入，正在输出正文。这次没有单独的思考链。";
    else if (phase === "done") body.textContent = "这次没有单独的思考链。";
    else if (phase === "failed") body.textContent = "请求已结束。";
    else body.textContent = WAITING;
    if (text) body.scrollTop = body.scrollHeight;
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
    jobId += 1;
    activeJob = jobId;
    phase = "sent";
    text = "";
    dismissed = false;
    startedAt = Date.now();
    elapsed = 0;
    render();
    setExpanded(true);
    show();
    return activeJob;
  }

  function applyStatus(nextPhase) {
    if (!nextPhase || phase === "done" || phase === "failed") return;
    if (nextPhase === "sent" && (phase === "thinking" || phase === "writing")) return;
    if (nextPhase === "thinking" && phase === "writing") return;
    phase = nextPhase;
    render();
    if (!dismissed && (phase === "sent" || phase === "thinking" || (phase === "writing" && !text))) {
      setExpanded(true);
      show();
    }
  }

  function append(chunk) {
    const piece = String(chunk || "");
    if (!piece || phase === "idle") return;
    phase = "thinking";
    dismissed = false;
    text += piece;
    render();
    setExpanded(true);
    show();
  }

  function finish(ok) {
    if (phase === "idle") return;
    elapsed = startedAt ? Math.max(1, Math.round((Date.now() - startedAt) / 1000)) : 0;
    phase = ok === false ? "failed" : "done";
    render();
    if (!text) {
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
    bound = true;
  }

  return {
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
