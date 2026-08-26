const ThinkTrace = (() => {
  const WAITING = "请求已发出。模型接入后，思考链会显示在这里。在此之前请不要重复发送。";
  let jobId = 0;
  let activeJob = 0;
  let phase = "idle";
  let text = "";
  let dismissed = false;
  let bound = false;

  function el(id) {
    return document.getElementById(id);
  }

  function isActive(id) {
    return id == null || id === activeJob;
  }

  function renderHeader() {
    const kicker = el("thinkFloatKicker");
    const title = el("thinkFloatTitle");
    if (!kicker || !title) return;
    if (phase === "thinking") {
      kicker.textContent = "模型已接入";
      title.textContent = "正在思考";
      return;
    }
    if (phase === "writing") {
      kicker.textContent = text ? "思考结束" : "模型已接入";
      title.textContent = "正在输出正文";
      return;
    }
    if (phase === "done") {
      kicker.textContent = "本次生成";
      title.textContent = text ? "思考记录" : "没有思考链";
      return;
    }
    if (phase === "failed") {
      kicker.textContent = "本次生成";
      title.textContent = "生成失败";
      return;
    }
    kicker.textContent = "请求已发出";
    title.textContent = "等待模型接入";
  }

  function renderBody() {
    const body = el("thinkFloatBody");
    if (!body) return;
    if (text) {
      body.textContent = text;
      body.scrollTop = body.scrollHeight;
      return;
    }
    if (phase === "thinking") body.textContent = "模型已接入，正在思考…";
    else if (phase === "writing") body.textContent = "模型已接入，正在输出正文。这次没有单独的思考链。";
    else if (phase === "done") body.textContent = "这次没有单独的思考链。";
    else if (phase === "failed") body.textContent = "请求已结束。";
    else body.textContent = WAITING;
  }

  function show() {
    const box = el("thinkFloat");
    if (box) box.hidden = false;
  }

  function hide() {
    const box = el("thinkFloat");
    if (box) box.hidden = true;
  }

  function start() {
    jobId += 1;
    activeJob = jobId;
    phase = "sent";
    text = "";
    dismissed = false;
    renderHeader();
    renderBody();
    show();
    return activeJob;
  }

  function applyStatus(nextPhase) {
    if (!nextPhase || phase === "done" || phase === "failed") return;
    if (nextPhase === "sent" && (phase === "thinking" || phase === "writing")) return;
    if (nextPhase === "thinking" && phase === "writing") return;
    phase = nextPhase;
    renderHeader();
    renderBody();
    if (!dismissed && (phase === "sent" || phase === "thinking" || (phase === "writing" && !text))) show();
  }

  function append(chunk) {
    const piece = String(chunk || "");
    if (!piece || phase === "idle") return;
    phase = "thinking";
    dismissed = false;
    text += piece;
    renderHeader();
    renderBody();
    show();
  }

  function finish(ok) {
    if (phase === "idle") return;
    phase = ok === false ? "failed" : "done";
    renderHeader();
    renderBody();
    if (!text) hide();
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
    hide();
    const body = el("thinkFloatBody");
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
    const button = el("thinkFloatClose");
    if (button) button.addEventListener("click", close);
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
      const box = el("thinkFloat");
      return Boolean(box && !box.hidden);
    },
    isIdle() {
      return phase === "idle" || phase === "done" || phase === "failed";
    },
  };
})();
window.ThinkTrace = ThinkTrace;
