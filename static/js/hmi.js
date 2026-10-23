(function () {

  const closeButton = document.getElementById("serviceClose");

  closeButton?.addEventListener("pointerdown", (event) => {
    window.hmiServiceClosing = true;
    event.stopPropagation();
  });

  closeButton?.addEventListener("click", async () => {
    window.hmiServiceClosing = true;

    try {
      await fetch("/api/hmi/logout", {method: "POST", cache: "no-store"});
    } catch (error) {
    }

    location.href = "/";
  });

  if (!window.HMI_SERVICE) {
    return;
  }

  const idleMs = (Number(window.HMI_IDLE_MIN) || 30) * 60 * 1000;
  let timer = 0;
  let lastTouch = 0;

  function arm() {
    window.clearTimeout(timer);
    timer = window.setTimeout(expire, idleMs);
  }

  async function expire() {
    if (window.hmiServiceClosing) {
      return;
    }

    window.hmiServiceClosing = true;

    try {
      await fetch("/api/hmi/logout", {method: "POST", cache: "no-store"});
    } catch (error) {
      location.href = "/";
      return;
    }

    location.href = "/";
  }

  async function touch() {
    if (window.hmiServiceClosing) {
      return;
    }

    arm();

    const now = Date.now();

    if (now - lastTouch < 60000) {
      return;
    }

    lastTouch = now;

    try {
      const response = await fetch("/api/hmi/activity", {method: "POST", cache: "no-store"});

      if (response.status === 401) {
        location.href = "/";
      }
    } catch (error) {
      return;
    }
  }

  document.addEventListener("pointerdown", touch);
  document.addEventListener("keydown", touch);
  arm();
  touch();

  window.setInterval(async () => {
    if (window.hmiServiceClosing) {
      return;
    }

    try {
      const response = await fetch("/api/hmi/session", {cache: "no-store"});

      if (!response.ok) {
        return;
      }

      const body = await response.json();

      if (!body.service) {
        location.href = "/";
      }
    } catch (error) {
      return;
    }
  }, 15000);

})();
