console.log("graph.js v3 loaded")

let chart = null
let liveTimer = null
let liveMode = false
let liveInFlight = false
let chartGeneration = 0

const MAX_POINTS = 300
const LIVE_POLL_MS = 5000

//--------------------------------------------------
// LIGHT FILTER — preserve null gaps
//--------------------------------------------------

function avgFilter(data, window = 5) {

    const result = []
    const buf = []

    for (let i = 0; i < data.length; i++) {

        const v = data[i]

        if (v == null || !Number.isFinite(Number(v))) {
            result.push(null)
            buf.length = 0
            continue
        }

        const num = Number(v)
        buf.push(num)

        if (buf.length > window)
            buf.shift()

        const sum = buf.reduce((a, b) => a + b, 0)
        result.push(sum / buf.length)
    }

    return result
}

//--------------------------------------------------
// LIMIT DATA
//--------------------------------------------------

function limitData(arr) {

    if (!arr) return []

    if (arr.length > MAX_POINTS)
        return arr.slice(-MAX_POINTS)

    return arr
}

//--------------------------------------------------
// AUTOSCALE
//--------------------------------------------------

function autoScale(minVal, maxVal) {

    if (!Number.isFinite(minVal) || !Number.isFinite(maxVal))
        return { min: 0, max: 1 }

    const span = Math.abs(maxVal - minVal)
    const magnitude = Math.max(Math.abs(minVal), Math.abs(maxVal))
    const pad = Math.max(span * 0.15, magnitude * 0.01, 0.5)

    return {
        min: minVal - pad,
        max: maxVal + pad
    }
}

//--------------------------------------------------
// SELECTED CHANNELS
//--------------------------------------------------

function channelLabel(ch) {

    const boxes = document.querySelectorAll("input[type=checkbox]")

    for (const cb of boxes) {

        if (cb.value.toLowerCase() !== ch) continue

        const label = (cb.dataset.label || "").trim()
        if (label) return label
    }

    return ch.toUpperCase()
}

function getSelected(prefix) {

    let result = []

    document.querySelectorAll("input[type=checkbox]").forEach(cb => {

        if (!cb.checked) return

        const v = cb.value.toLowerCase()

        if (v.startsWith(prefix))
            result.push(v)
    })

    return result
}

function ensureSelection() {

    const any = document.querySelector("input[type=checkbox]:checked")
    if (any) return true

    const first = document.querySelector("input[type=checkbox]")
    if (!first) return false

    first.checked = true
    return true
}

//--------------------------------------------------
// RANGE
//--------------------------------------------------

function getRange() {

    const val = document.getElementById("range").value

    if (val.endsWith("m"))
        return { minutes: parseInt(val, 10), hours: null }

    if (val.endsWith("h"))
        return { minutes: null, hours: parseInt(val, 10) }

    return { minutes: null, hours: 24 }
}

/** LIVE drží 5 min, 10 min, 30 min a 1 h. Dlhší rozsah ukazuje posledných 10 min. */
function getLiveMinutes() {

    const range = getRange()

    if (range.minutes)
        return Math.max(1, range.minutes)

    if (range.hours === 1)
        return 60

    return 10
}

//--------------------------------------------------
// LIVE BUTTON
//--------------------------------------------------

function setLiveButton(state) {

    const btn = document.getElementById("btnLive")
    if (!btn) return

    if (state) {
        btn.classList.add("btn-live-active")
        btn.classList.remove("btn-live")
        btn.textContent = "LIVE ON"
    } else {
        btn.classList.remove("btn-live-active")
        btn.classList.add("btn-live")
        btn.textContent = "LIVE"
    }
}

//--------------------------------------------------
// BUILD DATASETS FROM API PAYLOAD
//--------------------------------------------------

function buildSeries(data) {

    let labels = limitData(data.time || [])
    let tChannels = getSelected("t")
    let pChannels = getSelected("p")

    let datasets = []

    let tempMin = Infinity
    let tempMax = -Infinity
    let pressMin = Infinity
    let pressMax = -Infinity

    for (const ch of tChannels) {

        if (!data.t || !data.t[ch]) continue

        let raw = limitData(data.t[ch])

        // zarovnanie dĺžky s labels po limitData
        if (raw.length > labels.length)
            raw = raw.slice(-labels.length)
        else if (raw.length < labels.length)
            raw = Array(labels.length - raw.length).fill(null).concat(raw)

        let values = avgFilter(raw, 5)

        values.forEach(v => {
            if (v != null && Number.isFinite(v)) {
                if (v < tempMin) tempMin = v
                if (v > tempMax) tempMax = v
            }
        })

        datasets.push({
            label: channelLabel(ch),
            data: values,
            yAxisID: "yTemp",
            pointRadius: 0,
            spanGaps: false,
            tension: 0.2
        })
    }

    for (const ch of pChannels) {

        if (!data.p || !data.p[ch]) continue

        let raw = limitData(data.p[ch])

        if (raw.length > labels.length)
            raw = raw.slice(-labels.length)
        else if (raw.length < labels.length)
            raw = Array(labels.length - raw.length).fill(null).concat(raw)

        let values = avgFilter(raw, 5)

        values.forEach(v => {
            if (v != null && Number.isFinite(v)) {
                if (v < pressMin) pressMin = v
                if (v > pressMax) pressMax = v
            }
        })

        datasets.push({
            label: channelLabel(ch),
            data: values,
            yAxisID: "yPress",
            pointRadius: 0,
            spanGaps: false,
            tension: 0.2
        })
    }

    const gd20Keys = {
        gd20_ai2: "ai2_kpa",
        gd20_pid_feedback: "pid_feedback_kpa"
    }

    for (const ch of getSelected("gd20_")) {

        const key = gd20Keys[ch]

        if (!key || !data.gd20 || !data.gd20[key]) continue

        let raw = limitData(data.gd20[key])

        if (raw.length > labels.length)
            raw = raw.slice(-labels.length)
        else if (raw.length < labels.length)
            raw = Array(labels.length - raw.length).fill(null).concat(raw)

        let values = avgFilter(raw, 5)

        values.forEach(v => {
            if (v != null && Number.isFinite(v)) {
                if (v < pressMin) pressMin = v
                if (v > pressMax) pressMax = v
            }
        })

        datasets.push({
            label: channelLabel(ch),
            data: values,
            yAxisID: "yPress",
            pointRadius: 0,
            spanGaps: true,
            tension: 0.2
        })
    }

    return {
        labels,
        datasets,
        tempScale: autoScale(tempMin, tempMax),
        pressScale: autoScale(pressMin, pressMax)
    }
}

//--------------------------------------------------
// RENDER / UPDATE CHART
//--------------------------------------------------

const axisUnits = {
    id: "axisUnits",
    afterDraw(chart) {
        const area = chart.chartArea
        if (!area) return

        const ctx = chart.ctx
        ctx.save()
        ctx.fillStyle = "#fff"
        ctx.font = "bold 18px Arial"
        ctx.textBaseline = "bottom"

        const press = chart.scales.yPress
        const temp = chart.scales.yTemp
        const line = 22
        const y = area.top - 6 - line

        if (press) {
            ctx.textAlign = "left"
            ctx.fillText("kPa", press.left, y)
        }

        if (temp) {
            ctx.textAlign = "right"
            ctx.fillText("°C", temp.right, y)
        }

        ctx.restore()
    }
}

function renderChart(series) {

    if (chart)
        chart.destroy()

    chart = new Chart(document.getElementById("chart"), {

        type: "line",

        plugins: [axisUnits],

        data: {
            labels: series.labels,
            datasets: series.datasets
        },

        options: {

            responsive: true,
            animation: false,

            layout: {
                padding: { top: 36 }
            },

            interaction: {
                mode: "index",
                intersect: false
            },

            plugins: {

                decimation: {
                    enabled: true,
                    algorithm: "lttb",
                    samples: 100
                },

                legend: {
                    labels: {
                        font: { size: 20, weight: "bold" },
                        color: "#fff"
                    }
                },

                tooltip: {
                    titleFont: { size: 18, weight: "bold" },
                    bodyFont: { size: 18, weight: "bold" }
                }
            },

            scales: {

                x: {
                    ticks: {
                        font: { size: 18, weight: "bold" },
                        color: "#fff",
                        maxTicksLimit: 8,
                        maxRotation: 90,
                        minRotation: 90
                    },
                    border: {
                        color: "#fff",
                        width: 2
                    }
                },

                yPress: {
                    position: "left",
                    min: limitsFor("yPress", series.pressScale).min,
                    max: limitsFor("yPress", series.pressScale).max,
                    ticks: {
                        font: { size: 18, weight: "bold" },
                        color: "#fff"
                    },
                    border: {
                        color: "#fff",
                        width: 2
                    }
                },

                yTemp: {
                    position: "right",
                    min: limitsFor("yTemp", series.tempScale).min,
                    max: limitsFor("yTemp", series.tempScale).max,
                    ticks: {
                        font: { size: 18, weight: "bold" },
                        color: "#fff"
                    },
                    border: {
                        color: "#fff",
                        width: 2
                    },
                    grid: { drawOnChartArea: false }
                }
            }
        }
    })
}

function axisExtent(datasets, axisId) {

    let min = Infinity
    let max = -Infinity

    for (const ds of datasets) {

        if (ds.yAxisID !== axisId) continue

        for (const value of ds.data || []) {

            if (value == null || !Number.isFinite(Number(value))) continue

            const num = Number(value)
            if (num < min) min = num
            if (num > max) max = num
        }
    }

    if (!Number.isFinite(min) || !Number.isFinite(max))
        return null

    return autoScale(min, max)
}

const axisMode = { yPress: "auto", yTemp: "auto" }

function channelFullRange(cb) {

    const declaredMin = Number(cb.dataset.fullMin)
    const declaredMax = Number(cb.dataset.fullMax)

    if (Number.isFinite(declaredMin) && Number.isFinite(declaredMax) && declaredMax > declaredMin)
        return { min: declaredMin, max: declaredMax }

    const text = cb.closest("label") ? cb.closest("label").textContent : ""
    const match = text.match(/\((-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\)/)

    if (!match) return null

    return { min: Number(match[1]), max: Number(match[2]) }
}

function axisOfChannel(value) {

    return value.toLowerCase().startsWith("t") ? "yTemp" : "yPress"
}

function fullSpan(axisId) {

    let min = null
    let max = null

    document.querySelectorAll("input[type=checkbox]:checked").forEach(cb => {

        if (axisOfChannel(cb.value) !== axisId) return

        const span = channelFullRange(cb)
        if (!span) return

        min = min === null ? span.min : Math.min(min, span.min)
        max = max === null ? span.max : Math.max(max, span.max)
    })

    if (min === null || max === null || max <= min) return null

    return { min, max }
}

function limitsFor(axisId, fitted) {

    if (axisMode[axisId] === "full") {
        const full = fullSpan(axisId)
        if (full) return full
    }

    return fitted || { min: 0, max: 1 }
}

function paintAxisButtons() {

    const buttons = [
        ["yPress", "btnScalePress"],
        ["yTemp", "btnScaleTemp"],
    ]

    for (const [axisId, id] of buttons) {

        const btn = document.getElementById(id)
        if (!btn) continue

        const full = axisMode[axisId] === "full"
        btn.classList.toggle("axis-full", full)
        btn.classList.toggle("axis-auto", !full)
        btn.textContent = full ? "Full" : "Autoscale"
    }
}

function toggleAxisScale(axisId) {

    if (!chart || !chart.options.scales[axisId]) return

    axisMode[axisId] = axisMode[axisId] === "full" ? "auto" : "full"

    const fitted = axisExtent(chart.data.datasets, axisId) || autoScale(Infinity, -Infinity)
    const limits = limitsFor(axisId, fitted)

    chart.options.scales[axisId].min = limits.min
    chart.options.scales[axisId].max = limits.max
    paintAxisButtons()
    chart.update("none")
}

function applySeriesToChart(series) {

    if (!chart) {
        renderChart(series)
        return
    }

    chart.data.labels = series.labels
    chart.data.datasets = series.datasets

    const tempLimits = limitsFor("yTemp", series.tempScale)
    const pressLimits = limitsFor("yPress", series.pressScale)

    chart.options.scales.yTemp.min = tempLimits.min
    chart.options.scales.yTemp.max = tempLimits.max
    chart.options.scales.yPress.min = pressLimits.min
    chart.options.scales.yPress.max = pressLimits.max

    chart.update("none")
}

//--------------------------------------------------
// LOAD GRAPH (history / selected range)
//--------------------------------------------------

async function loadGraph() {

    stopLive()

    const gen = ++chartGeneration

    if (!ensureSelection()) {
        console.warn("No channels available")
        return
    }

    const range = getRange()

    let url = range.minutes
        ? `/api/live?minutes=${range.minutes}`
        : `/api/history?hours=${range.hours}`

    const r = await fetch(url, { cache: "no-store" })
    if (!r.ok) return console.error("API error")

    const data = await r.json()
    if (!data.time) return console.error("Invalid API")

    if (gen !== chartGeneration) return

    const series = buildSeries(data)

    if (series.datasets.length === 0) {
        console.warn("No data for selected channels")
        return
    }

    renderChart(series)
}

//--------------------------------------------------
// LIVE — full refresh of live window (dev-friendly)
//--------------------------------------------------

async function refreshLive() {

    if (liveInFlight) return
    liveInFlight = true

    const gen = chartGeneration

    try {

        if (!ensureSelection()) return

        const minutes = getLiveMinutes()
        const r = await fetch(`/api/live?minutes=${minutes}`, { cache: "no-store" })
        if (!r.ok) return

        const data = await r.json()
        if (!data.time) return

        // Load/stopLive medzitým zrušili túto generáciu
        if (gen !== chartGeneration || !liveMode) return

        const series = buildSeries(data)

        if (series.datasets.length === 0) return

        applySeriesToChart(series)

    } catch (e) {

        console.error("LIVE refresh error:", e)

    } finally {

        liveInFlight = false
    }
}

function startLive() {

    if (liveTimer) return

    liveMode = true
    chartGeneration++
    setLiveButton(true)

    refreshLive()
    liveTimer = setInterval(refreshLive, LIVE_POLL_MS)
}

function stopLive() {

    clearInterval(liveTimer)
    liveTimer = null

    liveMode = false
    chartGeneration++
    setLiveButton(false)
}

function toggleLive() {

    liveMode ? stopLive() : startLive()
}

//--------------------------------------------------
// INIT
//--------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {

    console.log("Graph v3 ready")

    // predvolene prvý dostupný kanál + načítaj graf
    ensureSelection()

    const pressBtn = document.getElementById("btnScalePress")
    const tempBtn = document.getElementById("btnScaleTemp")

    if (pressBtn) pressBtn.addEventListener("click", () => toggleAxisScale("yPress"))
    if (tempBtn) tempBtn.addEventListener("click", () => toggleAxisScale("yTemp"))
    paintAxisButtons()

    loadGraph()
})
