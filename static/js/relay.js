let tickInFlight = false;

async function fetchJSON(url){
  const r = await fetch(url,{cache:"no-store"});
  if(!r.ok) throw new Error("HTTP "+r.status);
  return await r.json();
}

async function postJSON(url,data){

  const r = await fetch(url,{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify(data),
    cache:"no-store"
  });

  const body = await r.json().catch(() => ({}));

  if(!r.ok){
    throw new Error(body.detail || ("HTTP "+r.status));
  }

  return body;
}


/* ================= RENDER ================= */

function escapeHtml(s){
  return String(s)
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;");
}

/** name "NA" / prázdny (case insensitive) = nezobrazovať v HMI */
function isRelayVisible(label){
  if(label === undefined || label === null) return false;
  const n = String(label).trim().toLowerCase();
  return n !== "" && n !== "na";
}

function renderRelayControl(el,data){

  const relay = data.relay_state || {};
  const names = data.relay_names || {};

  let html=`
  <tr>
    <th>Name</th>
    <th>State</th>
    <th>Source</th>
    <th>Action</th>
  </tr>
  `;

  let visible = 0;

  for(let i=1;i<=8;i++){

    const key = "r"+i;
    const label = names[key] ?? key;

    if(!isRelayVisible(label)) continue;

    const r = relay[key] || {state:0, source:"hmi"};
    const state = Number(r.state) === 1;
    const source = (r.source ?? "hmi") || "hmi";

    const stateTxt = state
      ? '<span class="relay-on">ON</span>'
      : '<span class="relay-off">OFF</span>';

    let actionTxt="";

    // manuálne ovládanie pre hmi / prázdny source; auto len badge
    if(source === "auto"){
      actionTxt=`<span class="badge-auto">${escapeHtml(source)}</span>`;
    }else{
      actionTxt=`
        <button onclick="setRelay('${key}',1)">ON</button>
        <button onclick="setRelay('${key}',0)">OFF</button>
      `;
    }

    html+=`
    <tr>
      <td>${escapeHtml(label)}</td>
      <td>${stateTxt}</td>
      <td>${escapeHtml(source)}</td>
      <td>${actionTxt}</td>
    </tr>
    `;

    visible++;
  }

  if(visible === 0){
    html += `<tr><td colspan="4">No relays</td></tr>`;
  }

  el.innerHTML=html;
}


/* ================= ACTION ================= */

async function setRelay(name,state){

  try{

    const result = await postJSON("/api/relay/set",{name:name,state:state});

    if(result.status && result.status !== "ok"){
      throw new Error(result.detail || result.status);
    }

    // počkaj na voľný tick (max ~1 s), potom vynúť refresh
    for(let i=0;i<10 && tickInFlight;i++){
      await new Promise(r => setTimeout(r, 100));
    }

    tickInFlight = false;
    await tick();

  }catch(e){

    console.error("setRelay failed:", e);
    alert("Relay set failed: " + (e.message || e));
  }
}


/* ================= LOOP ================= */

async function tick(){

  if(tickInFlight) return;
  tickInFlight = true;

  try{

    const data = await fetchJSON("/api/latest");

    document.getElementById("lastUpdate").textContent = data.server_time;
    document.getElementById("refreshMs").textContent = data.refresh_ms;

    renderRelayControl(
      document.getElementById("relayControlTable"),
      data
    );

  }catch(e){

    document.getElementById("lastUpdate").textContent="ERROR";
    console.error(e);

  }finally{

    tickInFlight = false;
  }
}


/* ================= START ================= */

const RELAY_REFRESH_MS = (typeof REFRESH_MS === "number" && REFRESH_MS > 0)
  ? REFRESH_MS
  : 2000;

tick();

setInterval(tick, RELAY_REFRESH_MS);
