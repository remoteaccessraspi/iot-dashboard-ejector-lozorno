#!/usr/bin/env bash
# Po výpadku napätia skontroluje dashboard, Modbus master a Chromium kiosk.
# Najprv reštartuje len to, čo nebeží. Reštart celého počítača je až posledný krok
# a je obmedzený, aby sa stroj nezacyklil.
set -u

ROOT="/home/pi/iot-dashboard-ejector-lozorno"
KIOSK_SCRIPT="${ROOT}/start_kiosk.sh"
URL="${HMI_URL:-http://127.0.0.1:8000/}"
STATE_DIR="/var/lib/iot-kiosk-watchdog"
RUNTIME_DIR="/run/user/1000"
WAYLAND_SOCK="${RUNTIME_DIR}/wayland-0"

GRACE_SEC=120
CHECK_SEC=30
HEARTBEAT_SEC=600
HTTP_FAILS_BEFORE_RESTART=3
KIOSK_FAILS_BEFORE_RELAUNCH=2
RELAUNCH_FAILS_BEFORE_REBOOT=3
WAYLAND_FAILS_BEFORE_LIGHTDM=3
WAYLAND_FAILS_BEFORE_REBOOT=6
MAX_REBOOTS=2
REBOOT_COOLDOWN_SEC=900
HEALTHY_RESET_SEC=600

ONCE=0
if [[ "${1:-}" == "--once" ]]; then
  ONCE=1
fi

mkdir -p "$STATE_DIR"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $*"
}

read_int() {
  local file="$1"
  if [[ -f "$file" ]]; then
    cat "$file" 2>/dev/null || echo 0
  else
    echo 0
  fi
}

write_int() {
  printf '%s\n' "$2" > "$1"
}

proc_cmdline() {
  local pid="$1" cmd
  cmd="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
  cmd="${cmd%"${cmd##*[![:space:]]}"}"
  printf '%s' "$cmd"
}

kiosk_browser_running() {
  local pid cmd
  for pid in $(pgrep -x chromium 2>/dev/null || true); do
    cmd="$(proc_cmdline "$pid")"
    case "$cmd" in
      *"--headless"*|*"--type="*) continue ;;
    esac
    case "$cmd" in
      *"--kiosk"*) return 0 ;;
    esac
  done
  return 1
}

kiosk_script_running() {
  local pid cmd
  for pid in $(pgrep -x bash 2>/dev/null || true); do
    cmd="$(proc_cmdline "$pid")"
    case "$cmd" in
      "$KIOSK_SCRIPT"|bash" $KIOSK_SCRIPT"|*/bash" $KIOSK_SCRIPT")
        return 0
        ;;
    esac
  done
  return 1
}

http_ok() {
  curl -fsS --max-time 5 -o /dev/null "$URL"
}

service_active() {
  systemctl is-active --quiet "$1"
}

wayland_ok() {
  [[ -S "$WAYLAND_SOCK" ]] && pgrep -x labwc >/dev/null 2>&1
}

maybe_reboot() {
  local reason="$1"
  local now count last
  now="$(date +%s)"
  count="$(read_int "$STATE_DIR/reboot_count")"
  last="$(read_int "$STATE_DIR/last_reboot")"
  if (( count >= MAX_REBOOTS )); then
    log "restart pocitaca preskoceny (${count}/${MAX_REBOOTS}): ${reason}"
    return 0
  fi
  if (( last > 0 && now - last < REBOOT_COOLDOWN_SEC )); then
    log "restart pocitaca odlozeny (cooldown): ${reason}"
    return 0
  fi
  write_int "$STATE_DIR/reboot_count" "$((count + 1))"
  write_int "$STATE_DIR/last_reboot" "$now"
  sync
  log "RESTART pocitaca: ${reason}"
  systemctl reboot
}

kill_kiosk_browser() {
  local pid cmd
  for pid in $(pgrep -x chromium 2>/dev/null || true); do
    cmd="$(proc_cmdline "$pid")"
    case "$cmd" in
      *"--headless"*|*"--type="*) continue ;;
    esac
    case "$cmd" in
      *"--kiosk"*) kill "$pid" 2>/dev/null || true ;;
    esac
  done
}

# 0 = spusteny novy kiosk, 2 = uz bezi start, 1 = chyba
relaunch_kiosk() {
  if kiosk_script_running; then
    log "start_kiosk.sh uz caka, dalsi start nespustam"
    return 2
  fi
  if systemctl is-active --quiet iot-kiosk-launch.service; then
    log "iot-kiosk-launch uz bezi"
    return 2
  fi
  systemctl reset-failed iot-kiosk-launch.service >/dev/null 2>&1 || true
  log "spustam kiosk"
  systemd-run --collect --quiet \
    --unit=iot-kiosk-launch \
    --uid=pi --gid=pi \
    --working-directory=/home/pi \
    --setenv=HOME=/home/pi \
    --setenv=XDG_RUNTIME_DIR="$RUNTIME_DIR" \
    --setenv=WAYLAND_DISPLAY=wayland-0 \
    --setenv=XDG_SESSION_TYPE=wayland \
    "$KIOSK_SCRIPT"
}

check_once() {
  local now uptime_sec http_fails kiosk_fails relaunch_fails wayland_fails healthy_since
  now="$(date +%s)"
  uptime_sec="${now}"
  if [[ -r /proc/uptime ]]; then
    uptime_sec="$(awk '{print int($1)}' /proc/uptime)"
  fi
  if (( uptime_sec < GRACE_SEC )); then
    log "ochranna doba po starte (${uptime_sec}s < ${GRACE_SEC}s), zatial bez zasahu"
    return 0
  fi

  http_fails="$(read_int "$STATE_DIR/http_fails")"
  kiosk_fails="$(read_int "$STATE_DIR/kiosk_fails")"
  relaunch_fails="$(read_int "$STATE_DIR/relaunch_fails")"
  wayland_fails="$(read_int "$STATE_DIR/wayland_fails")"
  healthy_since="$(read_int "$STATE_DIR/healthy_since")"

  local dashboard_http=0 master_ok=0 session_ok=0 kiosk_ok=0 healthy=1

  if service_active iot-master; then
    master_ok=1
  else
    healthy=0
    log "iot-master nebezi, restart sluzby"
    systemctl restart iot-master || log "restart iot-master zlyhal"
  fi

  if service_active iot-dashboard && http_ok; then
    dashboard_http=1
    http_fails=0
  else
    healthy=0
    http_fails=$((http_fails + 1))
    log "dashboard neodpoveda (${http_fails}/${HTTP_FAILS_BEFORE_RESTART})"
    if (( http_fails >= HTTP_FAILS_BEFORE_RESTART )); then
      if ! service_active mariadb; then
        log "mariadb nebezi, restart sluzby"
        systemctl restart mariadb || log "restart mariadb zlyhal"
        sleep 3
      fi
      log "restart iot-dashboard"
      systemctl restart iot-dashboard || log "restart iot-dashboard zlyhal"
      http_fails=0
      if kiosk_browser_running; then
        log "dashboard bol restartovany, kiosk sa nacita znova"
        kill_kiosk_browser
      fi
    fi
  fi

  if wayland_ok; then
    session_ok=1
    wayland_fails=0
  else
    healthy=0
    wayland_fails=$((wayland_fails + 1))
    log "graficka session nebezi (${wayland_fails})"
    if (( wayland_fails == WAYLAND_FAILS_BEFORE_LIGHTDM )); then
      log "restart lightdm"
      systemctl restart lightdm || log "restart lightdm zlyhal"
    elif (( wayland_fails >= WAYLAND_FAILS_BEFORE_REBOOT )); then
      maybe_reboot "graficka session nenabehla"
      wayland_fails=0
    fi
  fi

  if (( session_ok == 1 )); then
    if kiosk_browser_running; then
      kiosk_ok=1
      kiosk_fails=0
      relaunch_fails=0
    else
      healthy=0
      kiosk_fails=$((kiosk_fails + 1))
      log "kiosk nebezi (${kiosk_fails}/${KIOSK_FAILS_BEFORE_RELAUNCH})"
      if (( kiosk_fails >= KIOSK_FAILS_BEFORE_RELAUNCH )); then
        relaunch_kiosk
        local relaunch_rc=$?
        kiosk_fails=0
        if (( relaunch_rc != 2 )); then
          if (( relaunch_rc != 0 )); then
            log "spustenie kiosku zlyhalo"
          fi
          relaunch_fails=$((relaunch_fails + 1))
          if (( relaunch_fails >= RELAUNCH_FAILS_BEFORE_REBOOT )); then
            maybe_reboot "kiosk sa po opakovanych pokusoch nespustil"
            relaunch_fails=0
          fi
        fi
      fi
    fi
  fi

  if (( healthy == 1 )); then
    if (( healthy_since == 0 )); then
      healthy_since="$now"
    elif (( now - healthy_since >= HEALTHY_RESET_SEC )); then
      if (( $(read_int "$STATE_DIR/reboot_count") > 0 )); then
        log "system je v poriadku, pocitadlo restartov vynulovane"
      fi
      write_int "$STATE_DIR/reboot_count" 0
    fi
    local last_beat
    last_beat="$(read_int "$STATE_DIR/last_heartbeat")"
    if (( last_beat == 0 || now - last_beat >= HEARTBEAT_SEC )); then
      log "ok: dashboard, master aj kiosk bezia"
      write_int "$STATE_DIR/last_heartbeat" "$now"
    fi
  else
    healthy_since=0
  fi

  write_int "$STATE_DIR/http_fails" "$http_fails"
  write_int "$STATE_DIR/kiosk_fails" "$kiosk_fails"
  write_int "$STATE_DIR/relaunch_fails" "$relaunch_fails"
  write_int "$STATE_DIR/wayland_fails" "$wayland_fails"
  write_int "$STATE_DIR/healthy_since" "$healthy_since"
}

if (( ONCE == 1 )); then
  check_once
  exit 0
fi

log "watchdog spusteny"
while true; do
  check_once || log "kontrola skoncila chybou"
  sleep "$CHECK_SEC"
done
