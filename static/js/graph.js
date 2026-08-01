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

    if (!isFinite(minVal) || !isFinite(maxVal))
        return { min: 0, max: 1 }

    let minScaled = minVal >= 0 ? minVal * 0.8 : minVal * 1.2
    let maxScaled = maxVal >= 0 ? maxVal * 1.2 : maxVal * 0.8

    let range = maxScaled - minScaled
    let minRange = Math.max(Math.abs(maxVal - minVal) * 0.1, 0.5)

    if (range < minRange) {

        let center = (maxVal + minVal) / 2
        minScaled = center - minRange / 2
        maxScaled = center + minRange / 2
    }

    return { min: minScaled, max: maxScaled }
}

//--------------------------------------------------
// SELECTED CHANNELS
//--------------------------------------------------

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

/** LIVE vždy používa minútové okno (aj keď je vybraný hodinový range). */
function getLiveMinutes() {

    const range = getRange()

    if (range.minutes)
        return Math.max(1, range.minutes)

    // pri 1h/6h/... LIVE ukazuje posledných 10 min (vývojársky real-time)
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
            label: ch.toUpperCase(),
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
            label: ch.toUpperCase(),
            data: values,
            yAxisID: "yPress",
            pointRadius: 0,
            spanGaps: false,
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

function renderChart(series) {

    if (chart)
        chart.destroy()

    chart = new Chart(document.getElementById("chart"), {

        type: "line",

        data: {
            labels: series.labels,
            datasets: series.datasets
        },

        options: {

            responsive: true,
            animation: false,

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
                    min: series.pressScale.min,
                    max: series.pressScale.max,
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
                    min: series.tempScale.min,
                    max: series.tempScale.max,
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

function applySeriesToChart(series) {

    if (!chart) {
        renderChart(series)
        return
    }

    chart.data.labels = series.labels
    chart.data.datasets = series.datasets

    chart.options.scales.yTemp.min = series.tempScale.min
    chart.options.scales.yTemp.max = series.tempScale.max
    chart.options.scales.yPress.min = series.pressScale.min
    chart.options.scales.yPress.max = series.pressScale.max

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
    loadGraph()
})
