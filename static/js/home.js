let homeTickInFlight = false;
let homeCommandBusy = false;

function homeEscape(value) {

  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}


function homeFmt(value, unit) {

  if (value === null || value === undefined) {
    return null;
  }

  const number = Number(value);

  if (!Number.isFinite(number)) {
    return null;
  }

  return number.toFixed(1);
}


function homeChannel(names, values, units, wanted) {

  if (!Array.isArray(names)) {
    return null;
  }

  const index = names.findIndex((name) => String(name).trim() === wanted);

  if (index < 0) {
    return null;
  }

  return {
    name: names[index],
    value: Array.isArray(values) ? values[index] : null,
    unit: Array.isArray(units) ? units[index] : "",
  };
}


function homeParseTime(value) {

  if (!value) {
    return null;
  }

  const parsed = new Date(String(value).replace(" ", "T"));

  return Number.isNaN(parsed.getTime()) ? null : parsed;
}


function homeStale(dbTime, serverTime) {

  const sample = homeParseTime(dbTime);
  const server = homeParseTime(serverTime);

  if (!sample || !server) {
    return false;
  }

  return (server - sample) / 1000 > 10;
}


function homeSetDb(status) {

  const element = document.getElementById("dbStatus");

  if (!element) {
    return;
  }

  if (status === "OK") {
    element.textContent = "OK";
    element.className = "pill ok";
    return;
  }

  element.textContent = status || "ERR";
  element.className = "pill bad";
}


function homeShowChannel(labelId, valueId, channel, stale) {

  const label = document.getElementById(labelId);
  const reading = document.getElementById(valueId);

  if (label && channel) {
    label.textContent = channel.name;
  }

  if (!reading) {
    return;
  }

  const text = channel ? homeFmt(channel.value, channel.unit) : null;
  const unit = channel && text !== null && channel.unit ? " " + channel.unit : "";
  reading.textContent = text === null ? "-" : text + unit;
  reading.classList.toggle("stale", Boolean(stale) && text !== null);
}


function homeServiceRun() {

  return window.HMI_SERVICE === 1;
}


function homeSetDriveButton(running) {

  const button = document.getElementById("homeDrive");

  if (!button) {
    return;
  }

  const stopMode = running === true;
  const serviceRun = homeServiceRun() && !stopMode;
  button.textContent = stopMode ? "STOP" : (serviceRun ? "RUN in service mode" : "RUN");
  button.classList.toggle("btn-run", !stopMode);
  button.classList.toggle("btn-stop", stopMode);

  if (!homeCommandBusy) {
    const temperatures = window.homeReady !== true;
    button.disabled = !stopMode && (
      Boolean(window.homeExternalStop) || (!serviceRun && temperatures)
    );
  }
}


function homeRenderReady(ready) {

  const status = document.getElementById("homeStatus");

  if (!status) {
    return;
  }

  const pill = document.createElement("span");
  pill.className = ready === true ? "pill ok" : "pill bad";
  pill.textContent = ready === true ? "READY" : "NOT READY";
  status.insertBefore(pill, status.firstChild);
}


function homeRenderGd20(gd20) {

  const status = document.getElementById("homeStatus");
  const note = document.getElementById("homeCmd");

  if (!gd20) {
    window.homeExternalStop = false;
    window.homeRunning = false;

    if (status) {
      status.innerHTML = '<span class="pill bad">OFFLINE</span>';
    }

    homeSetDriveButton(false);
    return;
  }

  const externalStop = gd20.external_stop === 1;
  window.homeExternalStop = externalStop;
  window.homeRunning = gd20.running === 1;

  const online = gd20.online === 1
    ? '<span class="pill ok">ONLINE</span>'
    : '<span class="pill bad">OFFLINE</span>';
  const run = gd20.running === 1
    ? '<span class="pill ok">RUN</span>'
    : '<span class="pill idle">STOP</span>';
  const fault = (gd20.fault_code === null || gd20.fault_code === 0)
    ? '<span class="pill ok">NO FAULT</span>'
    : `<span class="pill bad">FAULT ${homeEscape(gd20.fault_code)}</span>`;
  const external = externalStop ? '<span class="pill bad">EXT STOP</span>' : "";
  const hours = Number(gd20.run_hours);
  const hoursLabel = Number.isFinite(hours) ? hours.toFixed(1) : "-";
  const runHours = `<span class="pill idle">RUN HOURS ${homeEscape(hoursLabel)}</span>`;

  if (status) {
    status.innerHTML = online + run + runHours + fault + external;
  }

  homeSetDriveButton(window.homeRunning);

  const temperatures = window.homeReady !== true;
  const serviceRun = homeServiceRun();

  if (note && externalStop) {
    note.textContent = serviceRun
      ? "External switch is open. Close it, then press RUN in service mode."
      : "External switch is open. Close it, then press RUN.";
    note.dataset.kind = "ext";
  } else if (note && serviceRun && window.homeRunning !== true) {
    if (note.dataset.kind !== "command" && note.dataset.kind !== "error") {
      note.textContent = "Service run ignores automatic stops. Use STOP to end it.";
      note.dataset.kind = "service";
    }
  } else if (note && temperatures && window.homeRunning !== true) {
    if (note.dataset.kind !== "alarm" && note.dataset.kind !== "command") {
      note.textContent = "Temperatures do not allow start yet.";
      note.dataset.kind = "ready";
    }
  } else if (note && (note.dataset.kind === "ext" || note.dataset.kind === "ready" || note.dataset.kind === "service")) {
    note.textContent = "";
    note.dataset.kind = "";
  }
}


async function homeTick() {

  if (homeTickInFlight) {
    return;
  }

  homeTickInFlight = true;

  try {
    const response = await fetch("/api/latest", {cache: "no-store"});

    if (!response.ok) {
      throw new Error("HTTP " + response.status);
    }

    const data = await response.json();
    window.homeReady = data.ready === true;
    const lastUpdate = document.getElementById("lastUpdate");
    const refresh = document.getElementById("refreshMs");
    const sample = document.getElementById("tLastDb");
    const stale = homeStale(data.t_last_db, data.server_time);

    if (lastUpdate) {
      lastUpdate.textContent = data.server_time || "-";
    }

    if (refresh) {
      refresh.textContent = data.refresh_ms || "-";
    }

    if (sample) {
      sample.textContent = data.t_last_db || "-";
      sample.classList.toggle("bad", stale);
    }

    homeSetDb(data.db_status);
    homeShowChannel(
      "evapInLabel",
      "evapInValue",
      homeChannel(data.t_names, data.t, data.t_units, "t_evap_in"),
      stale
    );
    homeShowChannel(
      "evapOutLabel",
      "evapOutValue",
      homeChannel(data.t_names, data.t, data.t_units, "t_evap_out"),
      stale
    );
    homeRenderGd20(data.gd20);
    homeRenderReady(data.ready);
  } catch (error) {
    homeSetDb("ERR");
  } finally {
    homeTickInFlight = false;
  }
}


async function homeCommand(run) {

  const driveButton = document.getElementById("homeDrive");
  const note = document.getElementById("homeCmd");
  homeCommandBusy = true;

  if (driveButton) {
    driveButton.disabled = true;
  }

  try {
    const response = await fetch("/api/gd20/command", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({run: run, service: run === true && homeServiceRun()}),
      cache: "no-store",
    });

    if (response.status === 409) {
      let detail = "";

      try {
        const payload = await response.json();
        detail = payload && payload.detail ? String(payload.detail) : "";
      } catch (error) {
        detail = "";
      }

      if (note) {
        if (detail === "alarm inhibits run") {
          note.textContent = "RUN is blocked by an alarm.";
          note.dataset.kind = "alarm";
        } else if (detail === "temperatures are not ready") {
          note.textContent = "Temperatures do not allow start yet.";
          note.dataset.kind = "ready";
        } else {
          note.textContent = homeServiceRun()
            ? "External switch is open. Close it, then press RUN in service mode."
            : "External switch is open. Close it, then press RUN.";
          note.dataset.kind = "ext";
        }
      }

      return;
    }

    if (!response.ok) {
      throw new Error("HTTP " + response.status);
    }

    if (note) {
      note.textContent = run ? "RUN queued" : "STOP queued";
      note.dataset.kind = "command";
    }
  } catch (error) {
    if (note) {
      note.textContent = "Command error";
      note.dataset.kind = "error";
    }
  } finally {
    homeCommandBusy = false;
    homeSetDriveButton(window.homeRunning === true);
  }
}


function homeBindService() {

  const openButton = document.getElementById("serviceOpen");
  const form = document.getElementById("serviceForm");
  const input = document.getElementById("servicePassword");
  const error = document.getElementById("serviceError");
  const cancel = document.getElementById("serviceCancel");

  if (!openButton || !form) {
    return;
  }

  openButton.addEventListener("click", () => {
    if (error) {
      error.textContent = "";
    }

    if (input) {
      input.value = "";
    }

    form.hidden = false;
    input?.focus();
  });

  cancel?.addEventListener("click", () => {
    form.hidden = true;

    if (error) {
      error.textContent = "";
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const submit = document.getElementById("serviceSubmit");

    if (submit) {
      submit.disabled = true;
    }

    try {
      const response = await fetch("/api/hmi/service", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({password: input ? input.value : ""}),
        cache: "no-store",
      });

      if (response.ok) {
        location.reload();
        return;
      }

      if (error) {
        error.textContent = response.status === 401
          ? "Wrong password"
          : "Service is unavailable";
      }
    } catch (requestError) {
      if (error) {
        error.textContent = "Service is unavailable";
      }
    } finally {
      if (submit) {
        submit.disabled = false;
      }
    }
  });
}


document.getElementById("homeDrive")?.addEventListener("click", () => {
  homeCommand(window.homeRunning !== true);
});
homeBindService();
homeTick();
setInterval(homeTick, typeof REFRESH_MS === "number" ? REFRESH_MS : 2000);
