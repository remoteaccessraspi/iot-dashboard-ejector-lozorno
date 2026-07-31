console.log("graph.js v2 loaded")

let chart = null
let liveTimer = null
let LIVE_WINDOW = 120
let liveMode = false

const MAX_POINTS = 300   // HARD LIMIT – kritické pre výkon

//--------------------------------------------------
// LIGHT FILTER (O(n))
//--------------------------------------------------

function avgFilter(data, window = 5) {

    let result = []
    let sum = 0

    for (let i = 0; i < data.length; i++) {

        sum += data[i] || 0

        if (i >= window)
            sum -= data[i - window] || 0

        result.push(sum / Math.min(i + 1, window))
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

//--------------------------------------------------
// RANGE
//--------------------------------------------------

function getRange() {

    const val = document.getElementById("range").value

    if (val.endsWith("m"))
        return { minutes: parseInt(val), hours: null }

    if (val.endsWith("h"))
        return { minutes: null, hours: parseInt(val) }

    return { minutes: null, hours: 24 }
}

//--------------------------------------------------
// LIVE BUTTON
//--------------------------------------------------

function setLiveButton(state){

    const btn = document.getElementById("btnLive")
    if(!btn) return

    if(state){
        btn.classList.add("btn-live-active")
        btn.classList.remove("btn-live")
        btn.textContent = "LIVE ON"
    }else{
        btn.classList.remove("btn-live-active")
        btn.classList.add("btn-live")
        btn.textContent = "LIVE"
    }
}

//--------------------------------------------------
// LOAD GRAPH
//--------------------------------------------------

async function loadGraph() {

    stopLive()

    const range = getRange()

    let url = range.minutes
        ? `/api/live?minutes=${range.minutes}`
        : `/api/history?hours=${range.hours}`

    const r = await fetch(url, { cache: "no-store" })
    if (!r.ok) return console.error("API error")

    const data = await r.json()
    if (!data.time) return console.error("Invalid API")

    let labels = limitData(data.time)

    let tChannels = getSelected("t")
    let pChannels = getSelected("p")

    let datasets = []

    let tempMin = Infinity
    let tempMax = -Infinity

    let pressMin = Infinity
    let pressMax = -Infinity

//--------------------------------------------------
// TEMPERATURE
//--------------------------------------------------

    for (const ch of tChannels) {

        if (!data.t || !data.t[ch]) continue

        let raw = limitData(data.t[ch])
        let values = avgFilter(raw, 5)

        values.forEach(v => {
            if (v != null) {
                if (v < tempMin) tempMin = v
                if (v > tempMax) tempMax = v
            }
        })

        datasets.push({
            label: ch.toUpperCase(),
            data: values,
            yAxisID: "yTemp",
            pointRadius: 0,
            tension: 0.2
        })
    }

//--------------------------------------------------
// PRESSURE
//--------------------------------------------------

    for (const ch of pChannels) {

        if (!data.p || !data.p[ch]) continue

        let raw = limitData(data.p[ch])
        let values = avgFilter(raw, 5)

        values.forEach(v => {
            if (v != null) {
                if (v < pressMin) pressMin = v
                if (v > pressMax) pressMax = v
            }
        })

        datasets.push({
            label: ch.toUpperCase(),
            data: values,
            yAxisID: "yPress",
            pointRadius: 0,
            tension: 0.2
        })
    }

    if (datasets.length === 0) {
        alert("No data selected")
        return
    }

    if (chart)
        chart.destroy()

    const tempScale = autoScale(tempMin, tempMax)
    const pressScale = autoScale(pressMin, pressMax)

//--------------------------------------------------
// CHART
//--------------------------------------------------

    chart = new Chart(document.getElementById("chart"), {

        type: "line",

        data: {
            labels: labels,
            datasets: datasets
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
                    algorithm: 'lttb',
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
                    min: pressScale.min,
                    max: pressScale.max,
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
                    min: tempScale.min,
                    max: tempScale.max,
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

//--------------------------------------------------
// LIVE UPDATE
//--------------------------------------------------

async function updateLive() {

    if (!chart) return

    const r = await fetch("/api/live?minutes=10", { cache: "no-store" })
    if (!r.ok) return

    const data = await r.json()
    if (!data.time) return

    const lastIndex = data.time.length - 1

    chart.data.labels.push(data.time[lastIndex])

    if (chart.data.labels.length > LIVE_WINDOW)
        chart.data.labels.shift()

    chart.data.datasets.forEach(ds => {

        let name = ds.label.toLowerCase()
        let val = null

        if (name.startsWith("t") && data.t[name])
            val = data.t[name][lastIndex]

        if (name.startsWith("p") && data.p[name])
            val = data.p[name][lastIndex]

        ds.data.push(val)

        if (ds.data.length > LIVE_WINDOW)
            ds.data.shift()
    })

    chart.update("none")
}

//--------------------------------------------------
// LIVE CONTROL
//--------------------------------------------------

function startLive() {

    if (liveTimer) return

    liveMode = true
    setLiveButton(true)

    LIVE_WINDOW = 120   // fixný bezpečný window

    updateLive()
    liveTimer = setInterval(updateLive, 5000)
}

function stopLive() {

    clearInterval(liveTimer)
    liveTimer = null

    liveMode = false
    setLiveButton(false)
}

function toggleLive(){

    liveMode ? stopLive() : startLive()
}

//--------------------------------------------------
// INIT
//--------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {

    console.log("Graph v2 ready")

    loadGraph()
})