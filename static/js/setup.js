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

  const history = [];

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function show(value) {
    if (Array.isArray(value)) return value.join(", ");
    if (value === true) return "áno";
    if (value === false) return "nie";
    return String(value);
  }

  function tokens(n) {
    return Number(n || 0).toLocaleString("sk-SK");
  }

  function usd(n) {
    return Number(n || 0).toLocaleString("sk-SK", {minimumFractionDigits: 2, maximumFractionDigits: 2}) + " $";
  }

  function renderUsage(u) {
    if (!u) return;
    usageLine.textContent =
      `Tokeny dnes ${tokens(u.today_tokens)} (${usd(u.today_usd)}) · ` +
      `mesiac ${tokens(u.month_tokens)} (${usd(u.month_usd)}) · ` +
      `zostáva ${usd(u.left_usd)} z ${usd(u.budget_usd)} · ` +
      `otázky dnes ${u.questions_today}/${u.daily_limit}`;
    usageLine.classList.toggle("setup-error", u.left_usd <= 0 || u.questions_today >= u.daily_limit);
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
      throw new Error("Servis sa zatvoril.");
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(typeof data.detail === "string" ? data.detail : "Požiadavka zlyhala.");
    }

    return data;
  }

  function proposalCard(proposal, requestText) {
    const box = el("div", "setup-proposal");

    if (proposal.changes.length) {
      const table = el("table");
      const head = el("tr");
      ["Kľúč", "Teraz", "Nové"].forEach((t) => head.appendChild(el("th", "", t)));
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
        ? "Platí až po reštarte služieb."
        : "Platí hneď, reštart netreba."));
    }

    proposal.errors.forEach((line) => box.appendChild(el("div", "setup-error", line)));

    const needConfirm = proposal.changes.some((c) => c.confirm);

    if (needConfirm) {
      box.appendChild(el("div", "setup-error",
        "Hodnota je mimo rozumného rozsahu. Súhlas treba potvrdiť ešte raz."));
    }

    if (!proposal.changes.length) {
      log.appendChild(box);
      scroll();
      return;
    }

    const actions = el("div", "actions");
    const yes = el("button", "btn-run", "Súhlas");
    const no = el("button", "btn-stop", "Zrušiť");
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
        yes.textContent = "Naozaj zapísať";
        return;
      }

      yes.disabled = no.disabled = true;

      try {
        await post("/api/setup/apply", {
          changes: proposal.changes.map((c) => ({key: c.key, old: c.old, new: c.new})),
          request: requestText,
          confirmed: needConfirm,
        });
        close("Zapísané.");
        history.push({role: "assistant", content: "Zmena bola zapísaná."});
      } catch (error) {
        box.appendChild(el("div", "setup-error", error.message));
        close();
      }

      refresh();
    });

    no.addEventListener("click", () => {
      close("Zrušené, nič sa nezapísalo.");
      history.push({role: "assistant", content: "Zákazník návrh zrušil."});
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
    const waiting = el("div", "setup-msg setup-wait", "Agent premýšľa…");
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
      say("agent", "Návrh na vrátenie zmeny z " + stamp(entry.ts) + ":");
      proposalCard(data.proposal, "Vrátiť zmenu z " + stamp(entry.ts));
    } catch (error) {
      say("error", error.message);
    }
  }

  function renderHistory(entries) {
    historyTable.replaceChildren();

    if (!entries.length) {
      const row = el("tr");
      row.appendChild(el("td", "small", "Zatiaľ žiadne zmeny."));
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
      const button = el("button", "", "Vrátiť");
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
      agentNote.textContent = data.agent ? "" : "Agent je v common.yaml vypnutý. Zoznam zmien a Vrátiť fungujú.";
      restartBox.hidden = !data.restart_pending;
      restartBtn.disabled = data.drive_running !== false;
      restartNote.textContent = data.drive_running === true
        ? "Menič beží, reštart počká na STOP."
        : data.drive_running === false ? "" : "Stav meniča nie je známy.";
    } catch (error) {
      return;
    }
  }

  restartBtn.addEventListener("click", async () => {
    restartBtn.disabled = true;
    restartNote.textContent = "Reštartujem…";

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
