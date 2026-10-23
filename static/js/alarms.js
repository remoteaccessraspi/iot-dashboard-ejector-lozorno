function alarmText(value) {

  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}


function renderAlarmRows(bar, rows, showAck) {

  if (!bar) {
    return;
  }

  if (!rows.length) {
    bar.hidden = true;
    bar.innerHTML = "";
    return;
  }

  bar.hidden = false;
  bar.innerHTML = rows.map((row) => {
    const alarm = row.class === "ALARM";
    const kind = alarm ? "alarm-item" : "warn-item";
    const label = alarm ? "Alarm" : "Warning";
    const ack = showAck && alarm && !row.acked
      ? `<button type="button" data-ack="1" data-code="${alarmText(row.code)}" data-source="${alarmText(row.source)}" data-device="${row.device_id}">Ack</button>`
      : "";
    return `<div class="${kind}"><span><b>${label}</b> ${alarmText(row.message)}</span>${ack}</div>`;
  }).join("");
}


function renderAlarms(rows) {

  const bar = document.getElementById("alarmBar");
  const warnings = document.getElementById("warnBar");
  const alarms = warnings ? rows.filter((row) => row.class === "ALARM") : rows;
  const warns = warnings ? rows.filter((row) => row.class !== "ALARM") : [];

  renderAlarmRows(bar, alarms, bar && bar.dataset.showAck !== "0");
  renderAlarmRows(warnings, warns, false);
}


async function refreshAlarms() {

  const bar = document.getElementById("alarmBar");

  if (!bar) {
    return;
  }

  try {
    const response = await fetch("/api/alarms", {cache: "no-store"});

    if (!response.ok) {
      return;
    }

    const body = await response.json();
    renderAlarms(body.alarms || []);
  } catch (error) {
    return;
  }
}


document.getElementById("alarmBar")?.addEventListener("click", async (event) => {

  const button = event.target.closest("button[data-ack]");

  if (!button) {
    return;
  }

  button.disabled = true;

  try {
    await fetch("/api/alarms/ack", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        code: button.dataset.code,
        source: button.dataset.source,
        device_id: Number(button.dataset.device),
      }),
    });
  } finally {
    refreshAlarms();
  }
});


refreshAlarms();
setInterval(refreshAlarms, 2000);
