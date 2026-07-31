// =====================================================
// FETCH
// =====================================================

async function fetchJSON(url){

  const r = await fetch(url,{cache:"no-store"});

  if(!r.ok) throw new Error("HTTP "+r.status);

  return await r.json();
}


// =====================================================
// FORMAT
// =====================================================

function fmt(v,unit=null){

  if(v===null || v===undefined) return null;
  if(typeof v!=="number") return String(v);
  if(!Number.isFinite(v)) return String(v);

  if(unit==="Pa") return v.toFixed(0);
  if(unit==="kPa") return v.toFixed(1);
  if(unit==="bar") return v.toFixed(3);
  if(unit==="mA") return v.toFixed(2);

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
        <td style="text-align:left">${label}</td>
        <td>${vtxt}${unitTxt}</td>
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
// RELAY TABLE
// =====================================================

function renderRelayTable(el,names,states,modes){

  const tbody=document.getElementById("relayBody");

  if(!tbody) return;

  let html="";
  let visible=0;

  if(!states || !Array.isArray(states)){
    tbody.innerHTML=html;
    return;
  }

  for(let i=0;i<states.length;i++){

    const name=names ? safeName(names[i]) : `R${i+1}`;

    if(name===null) continue;

    const state=states[i]===1;

    const mode=modes && modes[i] ? modes[i] : "manual";

    const stateTxt=state
      ? '<span class="relay-on">ON</span>'
      : '<span class="relay-off">OFF</span>';

    const modeTxt=mode==="auto"
      ? '<span class="badge-auto">AUTO</span>'
      : '<span class="badge-manual">Man</span>';

    html+=`
      <tr>
        <td style="text-align:left">${name}</td>
        <td>${stateTxt}</td>
        <td>${modeTxt}</td>
      </tr>
    `;

    visible++;
  }

  if(visible===0){

    html+=`
      <tr>
        <td colspan="3">No relays</td>
      </tr>
    `;
  }

  tbody.innerHTML=html;
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


    // --------------------------------------------------
    // RELAY TABLE (convert relay_state)
    // --------------------------------------------------

    if(data.relay_state){

      const names=[];
      const states=[];
      const modes=[];

      const relayNames = data.relay_names || {};

      for(let i=1;i<=8;i++){

        const key="r"+i;

        const r=data.relay_state[key];

        // použijeme názov zo settings.yaml
        const label = relayNames[key] ?? key;

        names.push(label);

        if(r){

          states.push(r.state);

          modes.push(r.source==="auto" ? "auto" : "manual");

        }else{

          states.push(0);
          modes.push("manual");
        }
      }

      renderRelayTable(
        document.getElementById("relayTable"),
        names,
        states,
        modes
      );
    }

  }
  catch(e){

    console.error("Tick error:",e);

    const lastUpdate=document.getElementById("lastUpdate");

    if(lastUpdate){
      lastUpdate.textContent="ERROR: "+e.message;
    }

    setDb("ERR");
  }

}


// =====================================================
// START
// =====================================================

tick();

setInterval(tick,REFRESH_MS);