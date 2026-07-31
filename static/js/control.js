/* ================= UTIL ================= */

async function fetchJSON(url){

  try{

    const r = await fetch(url);

    if(!r.ok){
      throw new Error("HTTP " + r.status);
    }

    return await r.json();

  }catch(err){

    console.error("Fetch failed:", err);
    return {};

  }
}


async function postData(url,data){

  try{

    const r = await fetch(url,{
      method:"POST",
      headers:{
        "Content-Type":"application/json"
      },
      body:JSON.stringify(data)
    });

    if(!r.ok){
      throw new Error("HTTP " + r.status);
    }

    return await r.json();

  }catch(err){

    console.error("POST error:", err);

    return {
      status:"error",
      detail:err.message
    };

  }
}


/* ================= SAFE HELPERS ================= */

function getValueSafe(id){

  const el = document.getElementById(id);

  if(!el){
    console.warn("Missing element:",id);
    return null;
  }

  return el.value;
}


function setValueSafe(id,value){

  const el = document.getElementById(id);

  if(!el){
    console.warn("Missing element:",id);
    return;
  }

  if(document.activeElement === el){
    return;
  }

  el.value = value ?? "";
}


/* ================= LOAD VALUES ================= */

async function loadControlValues(){

  if(!document.getElementById("pwm_period")){
    return;
  }

  const data = await fetchJSON("/api/latest");

  if(!data.control_state){
    console.warn("control_state missing in API");
    return;
  }

  const ctrl = data.control_state;

  setValueSafe("pwm_period", ctrl.pwm_period?.value);
  setValueSafe("pwm_duty",   ctrl.pwm_duty?.value);

  setValueSafe("pid_t_set",  ctrl.pid_t_set?.value);
  setValueSafe("pid_t_full", ctrl.pid_t_full?.value);
  setValueSafe("pid_t_move", ctrl.pid_t_move?.value);
}


/* ================= SAVE ALL ================= */

async function saveAll(){

  const pwm_period = Number(getValueSafe("pwm_period"));
  const pwm_duty   = Number(getValueSafe("pwm_duty"));

  const pid_t_set  = Number(getValueSafe("pid_t_set"));
  const pid_t_full = Number(getValueSafe("pid_t_full"));
  const pid_t_move = Number(getValueSafe("pid_t_move"));

  const result = await postData("/api/control/save_all",{

    pwm_period: pwm_period,
    pwm_duty: pwm_duty,

    pid_t_set: pid_t_set,
    pid_t_full: pid_t_full,
    pid_t_move: pid_t_move

  });

  if(result.status === "ok"){

    alert("Control values saved");

  }else{

    alert("ERROR saving control values");
    console.error(result);

  }

}


/* ================= AUTO REFRESH ================= */

function startAutoRefresh(){

  loadControlValues();

  setInterval(function(){

    loadControlValues();

  },2000);

}


/* ================= INIT ================= */

document.addEventListener("DOMContentLoaded",function(){

  startAutoRefresh();

});