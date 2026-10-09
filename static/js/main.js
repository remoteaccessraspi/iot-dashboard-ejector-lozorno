// =====================================================
// FETCH
// =====================================================

let tickInFlight = false;

async function fetchJSON(url){

  const r = await fetch(url,{cache:"no-store"});

  if(!r.ok) throw new Error("HTTP "+r.status);

  return await r.json();
}

function escapeHtml(s){
  return String(s)
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;");
}


// =====================================================
// FORMAT
// =====================================================

function unitKind(unit){

  const u=String(unit||"").trim().toLowerCase();

  if(u.startsWith("kpa")) return "kPa";
  if(u.startsWith("pa")) return "Pa";
  if(u.startsWith("bar")) return "bar";
  if(u.startsWith("ma")) return "mA";

  return "";
}


function fmt(v,unit=null){

  if(v===null || v===undefined) return null;
  if(typeof v!=="number") return String(v);
  if(!Number.isFinite(v)) return String(v);

  const kind=unitKind(unit);

  if(kind==="Pa") return v.toFixed(0);
  if(kind==="kPa") return v.toFixed(1);
  if(kind==="bar") return v.toFixed(3);
  if(kind==="mA") return v.toFixed(2);

  return v.toFixed(1);
}


// názov kanálu – NA alebo "" = nepripojený
function safeName(name){

  if(name===undefined || name===null) return null;

  if(typeof name==="string"){
    const n=name.trim().toLowerCase();
    if(n==="" || n==="na") return null;
  }

  return name;
}


// =====================================================
// TIME UTIL
// =====================================================

function parseTime(str){

  if(!str) return null;

  return new Date(str.replace(" ","T"));
}

function isStale(dbTimeStr,serverTimeStr,thresholdSec=10){

  const dbTime=parseTime(dbTimeStr);
  const srvTime=parseTime(serverTimeStr);

  if(!dbTime || !srvTime) return false;

  const diff=(srvTime-dbTime)/1000;

  return diff>thresholdSec;
}


// =====================================================
// GENERIC TABLE (T, I, P)
// =====================================================

function renderTable(el,names,values,units=null){

  if(!el) return;

  let html="<tr><th>Channel</th><th>Value</th></tr>";

  if(!values || !Array.isArray(values)){
    el.innerHTML=html;
    return;
  }

  let visible=0;

  for(let i=0;i<values.length;i++){

    const label=names ? safeName(names[i]) : `CH${i+1}`;
    if(label===null) continue;

    const unit=(units && units[i]) ? units[i] : null;

    const v=fmt(values[i],unit);

    const vtxt=(v===null) ? "-" : v;

    const unitTxt=unit ? " "+unit : "";

    html+=`
      <tr>
        <td style="text-align:left">${escapeHtml(label)}</td>
        <td>${escapeHtml(vtxt)}${escapeHtml(unitTxt)}</td>
      </tr>
    `;

    visible++;
  }

  if(visible===0){

    html+=`
      <tr>
        <td colspan="2">No sensors</td>
      </tr>
    `;
  }

  el.innerHTML=html;
}


// =====================================================
// DB STATUS
// =====================================================

function setDb(status){

  const el=document.getElementById("dbStatus");

  if(!el) return;

  if(status==="OK"){

    el.textContent="OK";
    el.className="pill ok";

  }else{

    el.textContent=status || "ERR";
    el.className="pill bad";
  }
}


// =====================================================
// MAIN TICK
// =====================================================

async function tick(){

  if(tickInFlight) return;
  tickInFlight = true;

  try{

    const data=await fetchJSON("/api/latest");

    // meta
    const lastUpdate=document.getElementById("lastUpdate");
    const refreshMs=document.getElementById("refreshMs");

    if(lastUpdate) lastUpdate.textContent=data.server_time || "-";
    if(refreshMs) refreshMs.textContent=data.refresh_ms || "-";

    setDb(data.db_status);


    // --------------------------------------------------
    // LAST DB WRITE TIMES
    // --------------------------------------------------

    const tLast=document.getElementById("tLastDb");
    const iLast=document.getElementById("iLastDb");

    if(tLast){

      tLast.textContent=data.t_last_db || "-";

      if(isStale(data.t_last_db,data.server_time)){
        tLast.style.color="#b00020";
        tLast.style.fontWeight="700";
      }else{
        tLast.style.color="";
        tLast.style.fontWeight="";
      }
    }

    if(iLast){

      iLast.textContent=data.i_last_db || "-";

      if(isStale(data.i_last_db,data.server_time)){
        iLast.style.color="#b00020";
        iLast.style.fontWeight="700";
      }else{
        iLast.style.color="";
        iLast.style.fontWeight="";
      }
    }


    // --------------------------------------------------
    // SENSOR TABLES
    // --------------------------------------------------

    renderTable(
      document.getElementById("tTable"),
      data.t_names,
      data.t,
      data.t_units
    );

    renderTable(
      document.getElementById("iTable"),
      data.i_names,
      data.i,
      data.i_units
    );

    renderTable(
      document.getElementById("pTable"),
      data.p_names,
      data.p,
      data.p_units
    );

    renderGd20(data.gd20, data.server_time);
    renderEm2rs(data.em2rs, data.server_time);

  }
  catch(e){

    console.error("Tick error:",e);

    const lastUpdate=document.getElementById("lastUpdate");

    if(lastUpdate){
      lastUpdate.textContent="ERROR: "+e.message;
    }

    setDb("ERR");

  }finally{

    tickInFlight = false;
  }

}


// =====================================================
// GD20 CARD
// =====================================================

function gd20Num(value, digits){

  if(value===null || value===undefined || !Number.isFinite(value)) return "-";

  return Number(value).toFixed(digits);
}


function renderGd20(gd20, serverTime){

  const last=document.getElementById("gd20LastDb");
  const status=document.getElementById("gd20Status");
  const table=document.getElementById("gd20Table");

  if(!table || !status) return;

  if(!gd20){
    if(last) last.textContent="-";
    status.innerHTML='<span class="pill bad">OFFLINE</span>';
    table.innerHTML="<tr><td colspan=\"2\">No data</td></tr>";
    return;
  }

  if(last){
    last.textContent=gd20.updated_ts || "-";
    if(gd20.online!==1 || isStale(gd20.updated_ts, serverTime, 15)){
      last.style.color="#b00020";
      last.style.fontWeight="700";
    }else{
      last.style.color="";
      last.style.fontWeight="";
    }
  }

  const online = gd20.online===1
    ? '<span class="pill ok">ONLINE</span>'
    : '<span class="pill bad">OFFLINE</span>';
  const run = gd20.running===1
    ? '<span class="pill ok">RUN</span>'
    : '<span class="pill idle">STOP</span>';
  const fault = (gd20.fault_code===null || gd20.fault_code===0)
    ? '<span class="pill ok">NO FAULT</span>'
    : `<span class="pill bad">FAULT ${escapeHtml(gd20.fault_code)}</span>`;

  status.innerHTML = online + run + fault;

  const rows = [
    ["Setpoint", gd20Num(gd20.pid_setpoint_kpa, 1), "kPa"],
    ["Setpoint command", gd20Num(gd20.setpoint_command_kpa, 1), "kPa"],
    ["PID feedback", gd20Num(gd20.pid_feedback_kpa, 1), "kPa"],
    [gd20.ai2_alias || "ai2_value", gd20Num(gd20.ai2_kpa, 1), "kPa"],
    ["Frequency", gd20Num(gd20.frequency_actual_hz, 2), "Hz"],
    ["Set frequency", gd20Num(gd20.frequency_set_hz, 2), "Hz"],
    ["Current", gd20Num(gd20.output_current_a, 1), "A"],
    ["Output voltage", gd20Num(gd20.output_voltage_v, 0), "V"],
    ["DC bus", gd20Num(gd20.dc_bus_voltage_v, 1), "V"],
    ["Speed", gd20.motor_speed_rpm===null || gd20.motor_speed_rpm===undefined ? "-" : String(gd20.motor_speed_rpm), "rpm"],
  ];

  let html="<tr><th>Value</th><th></th></tr>";

  for(const [label, value, unit] of rows){
    html += `
      <tr>
        <td>${escapeHtml(label)}</td>
        <td>${escapeHtml(value)} ${escapeHtml(unit)}</td>
      </tr>
    `;
  }

  table.innerHTML = html;
}


async function sendGd20(run){

  const runBtn=document.getElementById("gd20Run");
  const stopBtn=document.getElementById("gd20Stop");
  const note=document.getElementById("gd20Cmd");

  if(runBtn) runBtn.disabled=true;
  if(stopBtn) stopBtn.disabled=true;

  try{
    const r = await fetch("/api/gd20/command",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({run:run}),
      cache:"no-store"
    });

    if(!r.ok) throw new Error("HTTP "+r.status);

    if(note) note.textContent = run ? "RUN queued" : "STOP queued";
  }
  catch(e){
    if(note) note.textContent = "Command error";
    console.error(e);
  }
  finally{
    if(runBtn) runBtn.disabled=false;
    if(stopBtn) stopBtn.disabled=false;
  }
}


async function sendGd20Setpoint(){

  const input=document.getElementById("gd20Setpoint");
  const button=document.getElementById("gd20Set");
  const note=document.getElementById("gd20Cmd");
  const setpoint=input ? Number(input.value) : NaN;
  const low=typeof GD20_SETPOINT_MIN==="number" ? GD20_SETPOINT_MIN : 0;
  const high=typeof GD20_SETPOINT_MAX==="number" ? GD20_SETPOINT_MAX : 1500;

  if(!Number.isFinite(setpoint) || setpoint<low || setpoint>high){
    if(note) note.textContent=`Setpoint must be ${low}..${high} kPa`;
    return;
  }

  if(button) button.disabled=true;

  try{
    const r = await fetch("/api/gd20/setpoint",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({setpoint_kpa:setpoint}),
      cache:"no-store"
    });

    if(!r.ok) throw new Error("HTTP "+r.status);

    if(note) note.textContent=`Setpoint ${setpoint} kPa queued`;
  }
  catch(e){
    if(note) note.textContent="Setpoint error";
    console.error(e);
  }
  finally{
    if(button) button.disabled=false;
  }
}


function bindGd20Buttons(){

  const runBtn=document.getElementById("gd20Run");
  const stopBtn=document.getElementById("gd20Stop");
  const setBtn=document.getElementById("gd20Set");
  const input=document.getElementById("gd20Setpoint");

  if(runBtn) runBtn.addEventListener("click", () => sendGd20(true));
  if(stopBtn) stopBtn.addEventListener("click", () => sendGd20(false));
  if(setBtn) setBtn.addEventListener("click", () => sendGd20Setpoint());
  if(input){
    input.addEventListener("keydown", (event) => {
      if(event.key==="Enter"){
        event.preventDefault();
        sendGd20Setpoint();
      }
    });
  }
}


// =====================================================
// START
// =====================================================

function em2rsNum(value, digits){

  if(value===null || value===undefined || !Number.isFinite(Number(value))) return "-";

  return Number(value).toFixed(digits);
}


function renderEm2rs(em2rs, serverTime){

  const last=document.getElementById("em2rsLastDb");
  const status=document.getElementById("em2rsStatus");
  const table=document.getElementById("em2rsTable");
  const note=document.getElementById("em2rsNote");

  if(!table || !status) return;

  window.em2rsView = em2rs || null;

  if(!em2rs){
    if(last) last.textContent="-";
    status.innerHTML='<span class="pill bad">OFFLINE</span>';
    table.innerHTML="<tr><td class=\"em2rs-label\" colspan=\"6\">No data</td></tr>";
    applyEm2rsButtons();
    return;
  }

  const sample = em2rs.sample_ts || em2rs.updated_ts;
  const pollStale = em2rs.online!==1 || isStale(sample, serverTime, 15);
  const unchanged = Boolean(
    em2rs.sample_ts
    && em2rs.updated_ts
    && em2rs.updated_ts !== em2rs.sample_ts
    && isStale(em2rs.updated_ts, serverTime, 15)
  );
  const steady = document.getElementById("em2rsSteady");

  if(last){
    last.textContent=sample || "-";
    if(pollStale){
      last.style.color="#b00020";
      last.style.fontWeight="700";
    }else{
      last.style.color="";
      last.style.fontWeight="";
    }
  }

  if(steady){
    steady.textContent = (!pollStale && unchanged)
      ? "Hodnoty sa nezmenili od " + em2rs.updated_ts + "."
      : "";
  }

  const online = em2rs.online===1
    ? '<span class="pill ok">ONLINE</span>'
    : '<span class="pill bad">OFFLINE</span>';
  const mode = em2rs.mode==="AUTO"
    ? '<span class="pill idle">AUTO</span>'
    : '<span class="pill ok">MANUAL</span>';
  const run = em2rs.running===1
    ? '<span class="pill ok">RUNNING</span>'
    : '<span class="pill idle">STOP</span>';
  const alarm = em2rs.alarm===1
    ? `<span class="pill bad">ALARM</span>`
    : '<span class="pill ok">OK</span>';

  status.innerHTML = online + mode + run + alarm;

  const requested = em2rs.requested_position_pct===null || em2rs.requested_position_pct===undefined
    ? "-"
    : `${em2rsNum(em2rs.requested_position_pct, 0)} % / ${em2rs.requested_position_steps ?? "-"}`;
  const actual = em2rs.actual_position_steps===null || em2rs.actual_position_steps===undefined
    ? "-"
    : `${em2rsNum(em2rs.actual_position_pct, 1)} % / ${em2rs.actual_position_steps}`;
  const check = em2rs.position_check
    ? `${em2rs.position_check} (${em2rs.actual_delta_steps ?? "-"} / ${em2rs.expected_delta_steps ?? "-"})`
    : "-";

  const setpoint = em2rs.setpoint_command_kpa===null || em2rs.setpoint_command_kpa===undefined
    ? "-"
    : `${em2rsNum(em2rs.setpoint_command_kpa, 1)} kPa`;

  const homing=["Homing", em2rs.position_valid===1 ? "platný" : "potrebný"];
  const rows = [
    ["Režim", em2rs.mode || "-"],
    ["Setpoint p7", setpoint],
    ["Požadované", requested],
    ["Skutočné", actual],
    ["Kontrola pulzov", check],
    ["Fáza", em2rs.motion_phase || "-"],
  ];

  const rowCount=Math.ceil(rows.length / 2);
  let html="";
  for(let r=0; r<rowCount; r++){
    const left=rows[r*2];
    const mid=rows[r*2+1];
    html += `
      <tr>
        <td class="em2rs-label">${left ? escapeHtml(left[0]) : ""}</td>
        <td class="em2rs-value">${left ? escapeHtml(left[1]) : ""}</td>
        <td class="em2rs-label">${mid ? escapeHtml(mid[0]) : ""}</td>
        <td class="em2rs-value">${mid ? escapeHtml(mid[1]) : ""}</td>
        ${r===0 ? `<td class="em2rs-label" rowspan="${rowCount}">${escapeHtml(homing[0])}</td><td class="em2rs-value" rowspan="${rowCount}">${escapeHtml(homing[1])}</td>` : ""}
      </tr>
    `;
  }

  table.innerHTML = html;

  if(note){
    if(em2rs.alarm_text){
      note.textContent = em2rs.alarm_text;
      note.dataset.kind = "alarm";
    }else if(note.dataset.kind === "alarm"){
      note.textContent = "";
      note.dataset.kind = "";
    }
  }

  const setpointInput=document.getElementById("em2rsSetpoint");
  if(setpointInput && document.activeElement!==setpointInput && setpointInput.dataset.dirty!=="1"){
    if(em2rs.setpoint_command_kpa!==null && em2rs.setpoint_command_kpa!==undefined){
      setpointInput.value=String(em2rs.setpoint_command_kpa);
    }
  }

  applyEm2rsButtons();
}


function applyEm2rsButtons(){

  const view=window.em2rsView;
  const blocked = !view || view.mode==="AUTO" || view.running===1 || view.alarm===1;
  const homing=document.getElementById("em2rsHoming");
  const setBtn=document.getElementById("em2rsSet");
  const down=document.getElementById("em2rsDown");
  const up=document.getElementById("em2rsUp");
  const input=document.getElementById("em2rsPosition");

  if(homing) homing.disabled=blocked;
  if(setBtn) setBtn.disabled=blocked;
  if(down) down.disabled=blocked;
  if(up) up.disabled=blocked;
  if(input) input.disabled=blocked;
}


async function sendEm2rs(url, body, okText){

  const note=document.getElementById("em2rsNote");

  try{
    const r = await fetch(url,{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(body || {}),
      cache:"no-store"
    });

    if(!r.ok){
      let detail="Command error";
      try{
        const payload=await r.json();
        if(payload && payload.detail) detail=String(payload.detail);
      }catch(_e){}
      if(note) note.textContent=detail;
      return;
    }

    if(note){
      note.dataset.kind="local";
      note.textContent=okText;
    }
  }
  catch(e){
    if(note) note.textContent="Command error";
    console.error(e);
    return false;
  }

  return true;
}


function bindEm2rsButtons(){

  const manual=document.getElementById("em2rsManual");
  const auto=document.getElementById("em2rsAuto");
  const homing=document.getElementById("em2rsHoming");
  const setBtn=document.getElementById("em2rsSet");
  const down=document.getElementById("em2rsDown");
  const up=document.getElementById("em2rsUp");
  const reset=document.getElementById("em2rsReset");
  const input=document.getElementById("em2rsPosition");
  const setpointBtn=document.getElementById("em2rsSetpointSet");
  const setpointInput=document.getElementById("em2rsSetpoint");

  if(manual) manual.addEventListener("click", () => sendEm2rs("/api/em2rs/mode", {mode:"MANUAL"}, "Manual queued"));
  if(auto) auto.addEventListener("click", () => sendEm2rs("/api/em2rs/mode", {mode:"AUTO"}, "Auto queued"));
  if(homing) homing.addEventListener("click", () => sendEm2rs("/api/em2rs/homing", {}, "Homing queued"));
  if(reset) reset.addEventListener("click", () => sendEm2rs("/api/em2rs/alarm-reset", {}, "Alarm reset queued"));
  if(setpointBtn) setpointBtn.addEventListener("click", () => sendEm2rsSetpoint());
  if(setpointInput){
    setpointInput.addEventListener("input", () => {
      setpointInput.dataset.dirty="1";
    });
    setpointInput.addEventListener("keydown", (event) => {
      if(event.key==="Enter"){
        event.preventDefault();
        sendEm2rsSetpoint();
      }
    });
  }
  if(setBtn) setBtn.addEventListener("click", () => sendEm2rsPosition());
  if(down) down.addEventListener("click", () => stepEm2rsPosition(-1));
  if(up) up.addEventListener("click", () => stepEm2rsPosition(1));
  if(input){
    input.addEventListener("keydown", (event) => {
      if(event.key==="Enter"){
        event.preventDefault();
        sendEm2rsPosition();
      }
    });
  }
}


function stepEm2rsPosition(delta){

  const input=document.getElementById("em2rsPosition");
  if(!input || input.disabled) return;

  const current=Number(input.value);
  const base=Number.isFinite(current) ? current : 0;
  const next=Math.min(100, Math.max(0, base + delta));
  input.value=String(next);
}


function sendEm2rsSetpoint(){

  const input=document.getElementById("em2rsSetpoint");
  const setpoint=input ? Number(input.value) : NaN;
  const low=typeof EM2RS_SETPOINT_MIN==="number" ? EM2RS_SETPOINT_MIN : 0;
  const high=typeof EM2RS_SETPOINT_MAX==="number" ? EM2RS_SETPOINT_MAX : 220;

  if(!Number.isFinite(setpoint) || setpoint<low || setpoint>high){
    const note=document.getElementById("em2rsNote");
    if(note) note.textContent=`Setpoint musí byť ${low}..${high} kPa`;
    return;
  }

  sendEm2rs("/api/em2rs/setpoint", {setpoint_kpa:setpoint}, `Setpoint ${setpoint} kPa queued`).then((ok) => {
    if(ok && input) input.dataset.dirty="";
  });
}


function sendEm2rsPosition(){

  const input=document.getElementById("em2rsPosition");
  const percent=input ? Number(input.value) : NaN;

  if(!Number.isFinite(percent) || percent<0 || percent>100){
    const note=document.getElementById("em2rsNote");
    if(note) note.textContent="Poloha musí byť 0..100 %";
    return;
  }

  sendEm2rs("/api/em2rs/position", {position_pct:percent}, `Poloha ${percent} % queued`);
}


bindGd20Buttons();
bindEm2rsButtons();

tick();

setInterval(tick,REFRESH_MS);