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

bindGd20Buttons();

tick();

setInterval(tick,REFRESH_MS);