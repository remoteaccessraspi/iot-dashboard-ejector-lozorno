(function () {

  const log = document.getElementById("setupLog");
  const form = document.getElementById("setupForm");
  const input = document.getElementById("setupText");
  const send = document.getElementById("setupSend");
  const agentNote = document.getElementById("setupAgentNote");
  const historyTable = document.getElementById("setupHistory");
  const restartBox = document.getElementById("setupRestart");
  const restartBtn = document.getElementById("setupRestartBtn");
  const restartNote = document.getElementById("setupRestartNote");
  const usageLine = document.getElementById("setupUsage");
  const costsBox = document.getElementById("setupCosts");

  const history = [];

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function show(value) {
    if (Array.isArray(value)) return value.join(", ");
    if (value === true) return "yes";
    if (value === false) return "no";
    return String(value);
  }

  function renderUsage(u) {
    if (!u) return;
    usageLine.textContent = `Questions today ${u.questions_today}/${u.daily_limit}`;
    usageLine.classList.toggle("setup-error", u.questions_today >= u.daily_limit);
  }

  function costStatus(status) {
    const text = {
      not_initialized: "Not loaded yet",
      missing_key: "Admin key is missing",
      missing_project: "Project id is missing",
      disabled: "Cost monitoring is off",
      unauthorized: "Admin key was rejected",
      rate_limit: "OpenAI rate limit, showing the last value",
      timeout: "OpenAI timed out, showing the last value",
      network: "OpenAI is unreachable, showing the last value",
      server: "OpenAI failed, showing the last value",
      bad_config: "Cost settings are invalid",
      stale: "stale",
    };
    return text[status] || status;
  }

  function renderCosts(costs) {
    costsBox.replaceChildren();
    if (!costs) return;
    costsBox.appendChild(el("div", "setup-cost-label", "OpenAI API costs"));
    [
      ["Today", costs.today_usd],
      ["This month", costs.month_usd],
      ["Since tracking start", costs.total_since_tracking_start_usd],
    ].forEach((pair) => {
      const row = el("div", "", pair[0] + "  " + pair[1] + " " + costs.currency);
      costsBox.appendChild(row);
    });
    const note = el("div", "small");
    const bits = [];
    if (costs.last_successful_update_utc) bits.push("Updated " + costs.last_successful_update_utc);
    if (costs.stale) bits.push(costStatus(costs.status));
    note.textContent = bits.join(" · ");
    note.classList.toggle("setup-error", Boolean(costs.stale));
    costsBox.appendChild(note);
  }

  async function loadCosts() {
    try {
      const response = await fetch("/api/openai/costs", {cache: "no-store"});
      if (response.status === 401) {
        location.href = "/";
        return;
      }
      if (!response.ok) return;
      renderCosts(await response.json());
    } catch (error) {
      return;
    }
  }

  function scroll() {
    log.scrollTop = log.scrollHeight;
  }

  function say(role, text) {
    log.appendChild(el("div", "setup-msg setup-" + role, text));
    scroll();
  }

  async function post(url, body) {
    const response = await fetch(url, {
      method: "POST",
      cache: "no-store",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body || {}),
    });

    if (response.status === 401) {
      location.href = "/";
      throw new Error("Service closed.");
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(typeof data.detail === "string" ? data.detail : "The request failed.");
    }

    return data;
  }

  function proposalCard(proposal, requestText) {
    const box = el("div", "setup-proposal");

    if (proposal.changes.length) {
      const table = el("table");
      const head = el("tr");
      ["Key", "Now", "New"].forEach((t) => head.appendChild(el("th", "", t)));
      table.appendChild(head);

      proposal.changes.forEach((c) => {
        const row = el("tr", c.confirm ? "setup-confirm" : "");
        const name = el("td");
        name.appendChild(el("div", "", c.label));
        name.appendChild(el("div", "small", c.key));
        row.appendChild(name);
        row.appendChild(el("td", "", show(c.old)));
        row.appendChild(el("td", "", show(c.new)));
        table.appendChild(row);
      });

      box.appendChild(table);
    }

    proposal.edges.forEach((line) => box.appendChild(el("div", "", line)));

    if (proposal.changes.length) {
      box.appendChild(el("div", "small", proposal.restart
        ? "Applies after a service restart."
        : "Applies at once. No restart."));
    }

    proposal.errors.forEach((line) => box.appendChild(el("div", "setup-error", line)));

    const needConfirm = proposal.changes.some((c) => c.confirm);

    if (needConfirm) {
      box.appendChild(el("div", "setup-error",
        "The value is outside the reasonable range. Accept once more to write it."));
    }

    if (!proposal.changes.length) {
      log.appendChild(box);
      scroll();
      return;
    }

    const actions = el("div", "actions");
    const yes = el("button", "btn-run", "Accept");
    const no = el("button", "btn-stop", "Cancel");
    yes.type = no.type = "button";
    let armed = !needConfirm;

    function close(text) {
      yes.disabled = no.disabled = true;
      if (text) box.appendChild(el("div", "small", text));
      input.focus();
    }

    yes.addEventListener("click", async () => {
      if (!armed) {
        armed = true;
        yes.textContent = "Write it";
        return;
      }

      yes.disabled = no.disabled = true;

      try {
        await post("/api/setup/apply", {
          changes: proposal.changes.map((c) => ({key: c.key, old: c.old, new: c.new})),
          request: requestText,
          confirmed: needConfirm,
        });
        close("Written.");
        history.push({role: "assistant", content: "The change was written."});
      } catch (error) {
        box.appendChild(el("div", "setup-error", error.message));
        close();
      }

      refresh();
    });

    no.addEventListener("click", () => {
      close("Cancelled. Nothing was written.");
      history.push({role: "assistant", content: "The customer cancelled the proposal."});
    });

    actions.appendChild(yes);
    actions.appendChild(no);
    box.appendChild(actions);
    log.appendChild(box);
    scroll();
  }

  async function ask(text) {
    say("user", text);
    send.disabled = input.disabled = true;
    const waiting = el("div", "setup-msg setup-wait", "The agent is thinking…");
    log.appendChild(waiting);
    scroll();

    try {
      const data = await post("/api/setup/chat", {text: text, history: history});
      waiting.remove();
      renderUsage(data.usage);
      say("agent", data.reply);
      history.push({role: "user", content: text});
      history.push({role: "assistant", content: data.reply});
      if (data.proposal) proposalCard(data.proposal, text);
    } catch (error) {
      waiting.remove();
      say("error", error.message);
    } finally {
      send.disabled = input.disabled = false;
      input.focus();
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text || send.disabled) return;
    input.value = "";
    ask(text);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  function stamp(ts) {
    const d = new Date(ts * 1000);
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}. ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  async function revert(entry) {
    try {
      const data = await post("/api/setup/revert", {ts: entry.ts});
      say("agent", "Proposal to revert the change from " + stamp(entry.ts) + ":");
      proposalCard(data.proposal, "Revert the change from " + stamp(entry.ts));
    } catch (error) {
      say("error", error.message);
    }
  }

  function renderHistory(entries) {
    historyTable.replaceChildren();

    if (!entries.length) {
      const row = el("tr");
      row.appendChild(el("td", "small", "No changes yet."));
      historyTable.appendChild(row);
      return;
    }

    entries.forEach((entry) => {
      const row = el("tr");
      row.appendChild(el("td", "", stamp(entry.ts)));
      const what = el("td");
      entry.changes.forEach((c) => {
        what.appendChild(el("div", "", `${c.key}: ${show(c.old)} → ${show(c.new)}`));
      });
      if (entry.request) what.appendChild(el("div", "small", entry.request));
      row.appendChild(what);
      const cell = el("td");
      const button = el("button", "", "Revert");
      button.type = "button";
      button.addEventListener("click", () => revert(entry));
      cell.appendChild(button);
      row.appendChild(cell);
      historyTable.appendChild(row);
    });
  }

  async function refresh() {
    try {
      const response = await fetch("/api/setup/status", {cache: "no-store"});
      if (response.status === 401) {
        location.href = "/";
        return;
      }
      const data = await response.json();

      renderHistory(data.history || []);
      renderUsage(data.usage);
      loadCosts();
      agentNote.textContent = data.agent ? "" : "The agent is disabled in common.yaml. The change list and Revert still work.";
      restartBox.hidden = !data.restart_pending;
      restartBtn.disabled = data.drive_running !== false;
      restartNote.textContent = data.drive_running === true
        ? "The drive is running. Restart waits for STOP."
        : data.drive_running === false ? "" : "Drive state is unknown.";
    } catch (error) {
      return;
    }
  }

  restartBtn.addEventListener("click", async () => {
    restartBtn.disabled = true;
    restartNote.textContent = "Restarting…";

    try {
      await post("/api/setup/restart");
    } catch (error) {
      restartNote.textContent = error.message;
      refresh();
      return;
    }

    const started = Date.now();
    const poll = window.setInterval(async () => {
      if (Date.now() - started < 5000) return;
      try {
        const response = await fetch("/api/hmi/session", {cache: "no-store"});
        if (response.ok) {
          window.clearInterval(poll);
          location.reload();
        }
      } catch (error) {
        return;
      }
    }, 1000);
  });

  refresh();
  window.setInterval(refresh, 10000);
  input.focus();

})();
