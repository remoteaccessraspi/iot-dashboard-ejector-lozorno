async function fetchJSON(url){
  const r = await fetch(url,{cache:"no-store"});
  if(!r.ok) throw new Error("HTTP "+r.status);
  return await r.json();
}

async function postJSON(url,data){

  const r = await fetch(url,{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify(data)
  });

  return await r.json();
}


/* ================= RENDER ================= */

function renderRelayControl(el,data){

  const relay = data.relay_state;
  const names = data.relay_names || {};

  if(!relay){
    el.innerHTML="<tr><td colspan=4>No relay data</td></tr>";
    return;
  }

  let html=`
  <tr>
    <th>Name</th>
    <th>State</th>
    <th>Source</th>
    <th>Action</th>
  </tr>
  `;

  const keys = Object.keys(relay).filter(k => k.startsWith("r"));

  keys.sort();

  for(const key of keys){

    const r = relay[key];

    if(!r) continue;

    const label = names[key] ?? key;

    const state = r.state == 1;

    const stateTxt = state
      ? '<span class="relay-on">ON</span>'
      : '<span class="relay-off">OFF</span>';

    const source = r.source ?? "";

    let actionTxt="";

    if(source==="hmi" || source==="init"){

      actionTxt=`
        <button onclick="setRelay('${key}',1)">ON</button>
        <button onclick="setRelay('${key}',0)">OFF</button>
      `;

    }else{

      actionTxt=`<span class="badge-auto">${source}</span>`;
    }

    html+=`
    <tr>
      <td>${label}</td>
      <td>${stateTxt}</td>
      <td>${source}</td>
      <td>${actionTxt}</td>
    </tr>
    `;
  }

  el.innerHTML=html;
}


/* ================= ACTION ================= */

async function setRelay(name,state){

  await postJSON("/api/relay/set",{name:name,state:state});

  tick();
}


/* ================= LOOP ================= */

async function tick(){

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
  }
}


/* ================= START ================= */

tick();

setInterval(tick,2000);