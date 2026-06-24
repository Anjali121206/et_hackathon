/**
 * SentinelSafe — Industrial Safety Intelligence Dashboard
 * =========================================================
 * Complete client-side application powering the real-time
 * safety monitoring dashboard with WebSocket live updates,
 * DRI gauge visualization, simulation engine, and event timeline.
 */

// ─── State ────────────────────────────────────────────────────────────────────
const state = {
    ws: null,
    wsReconnectTimer: null,
    wsReconnectDelay: 1000,
    zones: {},
    events: [],
    peakDRI: 0,
    totalPermits: 0,
    totalViolations: 0,
    simulationRunning: false,
    selectedZone: null,
    gaugeAnimFrame: null,
    currentGaugeDRI: 0,
    targetGaugeDRI: 0,
    driHistory: [],
    lastTerminalMsg: ''
};

const ZONE_IDS = [
    'ZONE_COKE_OVEN_04', 'ZONE_BF_02', 'ZONE_SMS_01',
    'ZONE_ROLLING_03', 'ZONE_GAS_HOLDER', 'ZONE_POWER_PLANT'
];

const ZONE_NAMES = {
    'ZONE_COKE_OVEN_04': 'Coke Oven Battery #4',
    'ZONE_BF_02': 'Blast Furnace #2',
    'ZONE_SMS_01': 'Steel Melting Shop #1',
    'ZONE_ROLLING_03': 'Rolling Mill #3',
    'ZONE_GAS_HOLDER': 'Gas Holder Station',
    'ZONE_POWER_PLANT': 'Captive Power Plant'
};

// ─── Clock ────────────────────────────────────────────────────────────────────
function updateClock() {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    const s = String(now.getSeconds()).padStart(2, '0');
    const clockEl = document.getElementById('headerClock');
    if (clockEl) clockEl.textContent = `${h}:${m}:${s}`;
}
setInterval(updateClock, 1000);
updateClock();

// ─── WebSocket Connection ─────────────────────────────────────────────────────
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    try {
        state.ws = new WebSocket(wsUrl);

        state.ws.onopen = () => {
            console.log('📡 WebSocket connected');
            state.wsReconnectDelay = 1000;
            updateSystemStatus(true);
        };

        state.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleWSMessage(data);
            } catch (e) {
                console.error('WS parse error:', e);
            }
        };

        state.ws.onclose = () => {
            console.log('📡 WebSocket disconnected, reconnecting...');
            updateSystemStatus(false);
            scheduleReconnect();
        };

        state.ws.onerror = (err) => {
            console.error('WebSocket error:', err);
            state.ws.close();
        };
    } catch (e) {
        console.error('WebSocket connection failed:', e);
        scheduleReconnect();
    }
}

function scheduleReconnect() {
    if (state.wsReconnectTimer) clearTimeout(state.wsReconnectTimer);
    state.wsReconnectTimer = setTimeout(() => {
        state.wsReconnectDelay = Math.min(state.wsReconnectDelay * 1.5, 10000);
        connectWebSocket();
    }, state.wsReconnectDelay);
}

function updateSystemStatus(online) {
    const statusEl = document.getElementById('systemStatus');
    if (!statusEl) return;
    const dot = statusEl.querySelector('.status-dot');
    const text = statusEl.querySelector('span:last-child');
    if (online) {
        dot.className = 'status-dot online';
        text.textContent = 'All Agents Operational';
        statusEl.style.borderColor = 'rgba(0, 255, 136, 0.15)';
        statusEl.style.color = '#00ff88';
    } else {
        dot.className = 'status-dot offline';
        text.textContent = 'Reconnecting...';
        statusEl.style.borderColor = 'rgba(255, 170, 0, 0.15)';
        statusEl.style.color = '#ffaa00';
        dot.style.background = '#ffaa00';
        dot.style.boxShadow = '0 0 8px #ffaa00';
    }
}

// ─── WebSocket Message Handler ────────────────────────────────────────────────
function handleWSMessage(data) {
    switch (data.type) {
        case 'initial_state':
            if (data.zones) {
                data.zones.forEach(z => {
                    state.zones[z.zone_id] = z;
                });
            }
            if (data.events) {
                state.events = data.events;
            }
            refreshAllUI();
            break;

        case 'telemetry_update':
            if (data.zone_status) {
                const zoneId = data.event?.zone_id || data.zone_status.zone_id;
                state.zones[zoneId] = { ...data.zone_status, zone_id: zoneId };
            }
            if (data.event) {
                addEventToTimeline(data.event);
            }
            refreshAllUI();
            break;

        case 'permit_update':
            if (data.event) {
                addEventToTimeline(data.event);
            }
            state.totalPermits++;
            refreshStats();
            refreshTimeline();
            break;

        case 'vision_update':
            if (data.vision) {
                const violations = data.vision.ppe_violations || [];
                state.totalViolations += violations.length;
            }
            if (data.event) {
                addEventToTimeline(data.event);
            }
            refreshStats();
            refreshTimeline();
            break;

        case 'pong':
            break;

        default:
            console.log('Unknown WS message type:', data.type);
    }
}

function addEventToTimeline(event) {
    state.events.unshift(event);
    if (state.events.length > 200) state.events.pop();
}

// ─── Refresh All UI ───────────────────────────────────────────────────────────
function refreshAllUI() {
    refreshZoneMap();
    refreshStats();
    refreshDRIGauge();
    refreshAgentPipeline();
    refreshTimeline();
}

// ─── Zone Map Updates ─────────────────────────────────────────────────────────
function refreshZoneMap() {
    let peakDRI = 0;
    let peakZone = null;

    ZONE_IDS.forEach(zoneId => {
        const zoneData = state.zones[zoneId];
        const group = document.getElementById(`zone-${zoneId}`);
        if (!group) return;

        const dri = zoneData?.computed_dri || 0;
        const riskLevel = zoneData?.risk_level || 'NORMAL';

        // Update DRI text
        const driText = group.querySelector('.zone-dri-text');
        if (driText) {
            driText.textContent = dri.toFixed(2);
        }

        // Track peak DRI
        if (dri > peakDRI) {
            peakDRI = dri;
            peakZone = zoneId;
        }

        // Update zone color class
        group.classList.remove('zone-normal', 'zone-elevated', 'zone-high', 'zone-critical');
        const riskClass = `zone-${riskLevel.toLowerCase()}`;
        group.classList.add(riskClass);

        // Update colors for text and elements
        const color = getRiskColor(riskLevel);
        const texts = group.querySelectorAll('text');
        texts.forEach(t => {
            if (t.classList.contains('zone-dri-text')) {
                t.setAttribute('fill', color);
            }
        });

        // Update the zone title header fill
        const headerRect = group.querySelectorAll('rect')[1];
        if (headerRect) {
            headerRect.setAttribute('fill', hexToRgba(color, 0.15));
        }

        // Update title text color
        const titleText = group.querySelectorAll('text')[0];
        if (titleText) {
            titleText.setAttribute('fill', color);
        }

        // Update sensor dots (excluding workers)
        const sensorCircles = group.querySelectorAll('circle:not(.worker-dot)');
        sensorCircles.forEach(c => {
            c.setAttribute('fill', hexToRgba(color, 0.2));
            c.setAttribute('stroke', color);
        });

        // Update workers
        const workers = group.querySelectorAll('.worker-dot');
        workers.forEach(w => {
            if (riskLevel === 'CRITICAL' || riskLevel === 'HIGH') {
                w.setAttribute('class', 'worker-dot danger');
            } else {
                w.setAttribute('class', 'worker-dot safe');
            }
        });
    });

    state.peakDRI = peakDRI;
    state.peakZone = peakZone;
}

function getRiskColor(level) {
    switch (level) {
        case 'CRITICAL': return '#ff0040';
        case 'HIGH': return '#ff6600';
        case 'ELEVATED': return '#ffaa00';
        default: return '#00ff88';
    }
}

function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// ─── Stats Updates ────────────────────────────────────────────────────────────
function refreshStats() {
    const zonesWithData = Object.keys(state.zones).length;
    document.getElementById('statZonesValue').textContent = zonesWithData || '6';

    document.getElementById('statPermitsValue').textContent = state.totalPermits;
    document.getElementById('statViolationsValue').textContent = state.totalViolations;

    const driEl = document.getElementById('statDRIValue');
    driEl.textContent = state.peakDRI.toFixed(2);

    const driCard = document.getElementById('statDRI');
    driCard.classList.remove('critical');
    if (state.peakDRI >= 0.85) {
        driCard.classList.add('critical');
    }
}

// ─── DRI Gauge (Canvas) ──────────────────────────────────────────────────────
function refreshDRIGauge() {
    // Use peak zone data if available
    const peakZoneData = state.peakZone ? state.zones[state.peakZone] : null;
    const dri = peakZoneData?.computed_dri || 0;
    const riskLevel = peakZoneData?.risk_level || 'NORMAL';

    state.targetGaugeDRI = dri;

    // Animate the gauge
    if (!state.gaugeAnimFrame) {
        animateGauge();
    }

    // Update DRI main display
    const driMainVal = document.getElementById('driMainValue');
    driMainVal.textContent = dri.toFixed(2);
    driMainVal.className = 'dri-main-value';
    if (riskLevel === 'CRITICAL') driMainVal.classList.add('critical');
    else if (riskLevel === 'HIGH') driMainVal.classList.add('high');
    else if (riskLevel === 'ELEVATED') driMainVal.classList.add('elevated');

    // Update badge
    const badge = document.getElementById('driLevelBadge');
    badge.textContent = riskLevel;
    badge.className = 'card-badge';
    if (riskLevel === 'CRITICAL') badge.classList.add('critical-badge');
    else if (riskLevel === 'HIGH') badge.classList.add('elevated-badge');
    else if (riskLevel === 'ELEVATED') badge.classList.add('warning-badge');

    // Update factor bars
    if (peakZoneData) {
        updateFactorBar('factorBarTelemetry', 'factorTelemetryVal', peakZoneData.telemetry_risk || 0);
        updateFactorBar('factorBarPermit', 'factorPermitVal', peakZoneData.permit_factor || 0);
        updateFactorBar('factorBarVision', 'factorVisionVal', peakZoneData.vision_factor || 0);
    }

    // Predictive Forecast Logic
    const now = Date.now();
    state.driHistory.push({ t: now, v: dri });
    // Keep last 10 seconds of history
    state.driHistory = state.driHistory.filter(h => now - h.t <= 10000);

    const trendEl = document.getElementById('driTrendRate');
    const critEl = document.getElementById('timeToCritical');

    if (state.driHistory.length >= 2) {
        const first = state.driHistory[0];
        const last = state.driHistory[state.driHistory.length - 1];
        const dt = (last.t - first.t) / 1000; // seconds
        if (dt > 0) {
            const dv = last.v - first.v;
            const ratePerSec = dv / dt;
            const ratePerHr = ratePerSec * 3600;
            
            trendEl.textContent = `${ratePerHr > 0 ? '+' : ''}${ratePerHr.toFixed(2)} / hr`;
            trendEl.style.color = ratePerHr > 0 ? 'var(--neon-amber)' : 'var(--neon-green)';

            if (ratePerSec > 0 && dri < 0.85) {
                const timeToCrit = (0.85 - dri) / ratePerSec; // seconds
                const mins = Math.ceil(timeToCrit / 60);
                critEl.textContent = `Est. Time to Critical: ${mins} min${mins !== 1 ? 's' : ''}`;
                critEl.classList.add('active');
            } else {
                critEl.classList.remove('active');
            }
        }
    }

    // Draw sparkline
    const canvas = document.getElementById('driSparklineCanvas');
    if (canvas && state.driHistory.length > 1) {
        const ctx = canvas.getContext('2d');
        const w = canvas.width;
        const h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        
        const firstT = state.driHistory[0].t;
        const lastT = state.driHistory[state.driHistory.length - 1].t;
        const dt = lastT - firstT;
        
        ctx.beginPath();
        for (let i = 0; i < state.driHistory.length; i++) {
            const pt = state.driHistory[i];
            const x = dt > 0 ? ((pt.t - firstT) / dt) * w : w;
            const y = h - (pt.v * h); // Map 0-1 to h-0
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = 'rgba(0, 240, 255, 0.6)';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Fill under line
        ctx.lineTo(w, h);
        ctx.lineTo(0, h);
        ctx.fillStyle = 'rgba(0, 240, 255, 0.1)';
        ctx.fill();
    }
}

function updateFactorBar(barId, valId, value) {
    const bar = document.getElementById(barId);
    const val = document.getElementById(valId);
    if (bar) bar.style.width = `${Math.min(100, value * 100)}%`;
    if (val) val.textContent = value.toFixed(2);
}

function animateGauge() {
    const diff = state.targetGaugeDRI - state.currentGaugeDRI;
    if (Math.abs(diff) > 0.001) {
        state.currentGaugeDRI += diff * 0.08;
        drawGauge(state.currentGaugeDRI);
        state.gaugeAnimFrame = requestAnimationFrame(animateGauge);
    } else {
        state.currentGaugeDRI = state.targetGaugeDRI;
        drawGauge(state.currentGaugeDRI);
        state.gaugeAnimFrame = null;
    }
}

function drawGauge(dri) {
    const canvas = document.getElementById('driGaugeCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // Handle high DPI displays
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;
    const cx = w / 2;
    const cy = h - 20;
    const radius = Math.min(cx - 20, cy - 10);

    ctx.clearRect(0, 0, w, h);

    // Background arc
    const startAngle = Math.PI;
    const endAngle = 2 * Math.PI;

    ctx.beginPath();
    ctx.arc(cx, cy, radius, startAngle, endAngle);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
    ctx.lineWidth = 18;
    ctx.lineCap = 'round';
    ctx.stroke();

    // Colored segments
    const segments = [
        { from: 0, to: 0.35, color: '#00ff88' },
        { from: 0.35, to: 0.60, color: '#ffaa00' },
        { from: 0.60, to: 0.85, color: '#ff6600' },
        { from: 0.85, to: 1.0, color: '#ff0040' }
    ];

    segments.forEach(seg => {
        const segStart = startAngle + seg.from * Math.PI;
        const segEnd = startAngle + seg.to * Math.PI;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, segStart, segEnd);
        ctx.strokeStyle = hexToRgba(seg.color, 0.12);
        ctx.lineWidth = 18;
        ctx.lineCap = 'butt';
        ctx.stroke();
    });

    // Active arc (filled up to current DRI)
    if (dri > 0) {
        const fillEnd = startAngle + Math.min(1, dri) * Math.PI;
        const gradient = ctx.createLinearGradient(cx - radius, cy, cx + radius, cy);

        if (dri >= 0.85) {
            gradient.addColorStop(0, '#ff6600');
            gradient.addColorStop(1, '#ff0040');
        } else if (dri >= 0.60) {
            gradient.addColorStop(0, '#ffaa00');
            gradient.addColorStop(1, '#ff6600');
        } else if (dri >= 0.35) {
            gradient.addColorStop(0, '#00ff88');
            gradient.addColorStop(1, '#ffaa00');
        } else {
            gradient.addColorStop(0, '#00f0ff');
            gradient.addColorStop(1, '#00ff88');
        }

        ctx.beginPath();
        ctx.arc(cx, cy, radius, startAngle, fillEnd);
        ctx.strokeStyle = gradient;
        ctx.lineWidth = 18;
        ctx.lineCap = 'round';
        ctx.stroke();

        // Glow effect
        ctx.beginPath();
        ctx.arc(cx, cy, radius, startAngle, fillEnd);
        ctx.strokeStyle = hexToRgba(getRiskColor(getDRILevel(dri)), 0.15);
        ctx.lineWidth = 30;
        ctx.lineCap = 'round';
        ctx.stroke();
    }

    // Needle
    const needleAngle = startAngle + Math.min(1, dri) * Math.PI;
    const needleLen = radius - 25;
    const nx = cx + needleLen * Math.cos(needleAngle);
    const ny = cy + needleLen * Math.sin(needleAngle);

    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(nx, ny);
    ctx.strokeStyle = getRiskColor(getDRILevel(dri));
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.stroke();

    // Center dot
    ctx.beginPath();
    ctx.arc(cx, cy, 5, 0, 2 * Math.PI);
    ctx.fillStyle = getRiskColor(getDRILevel(dri));
    ctx.fill();

    // Threshold labels
    ctx.font = '9px Inter, sans-serif';
    ctx.fillStyle = '#3a4a5c';
    ctx.textAlign = 'center';

    const labels = [
        { val: 0, text: '0.0' },
        { val: 0.35, text: '0.35' },
        { val: 0.60, text: '0.60' },
        { val: 0.85, text: '0.85' },
        { val: 1.0, text: '1.0' }
    ];

    labels.forEach(l => {
        const a = startAngle + l.val * Math.PI;
        const lx = cx + (radius + 16) * Math.cos(a);
        const ly = cy + (radius + 16) * Math.sin(a);
        ctx.fillText(l.text, lx, ly);
    });
}

function getDRILevel(dri) {
    if (dri >= 0.85) return 'CRITICAL';
    if (dri >= 0.60) return 'HIGH';
    if (dri >= 0.35) return 'ELEVATED';
    return 'NORMAL';
}

// ─── Agent Pipeline ───────────────────────────────────────────────────────────
function refreshAgentPipeline() {
    const peakZoneData = state.peakZone ? state.zones[state.peakZone] : null;
    const riskLevel = peakZoneData?.risk_level || 'NORMAL';
    const action = peakZoneData?.recommended_action || 'CONTINUOUS_MONITORING';
    const isCritical = peakZoneData?.critical_flag || false;

    // Update agent nodes
    const agents = ['agentTelemetry', 'agentPermit', 'agentVision', 'agentDecision'];
    agents.forEach(id => {
        const node = document.getElementById(id);
        if (!node) return;
        node.classList.remove('active', 'critical-active');
        if (peakZoneData) {
            node.classList.add('active');
            if (isCritical) {
                node.classList.add('critical-active');
            }
        }
    });

    // Update action display (Terminal)
    if (peakZoneData) {
        if (peakZoneData.telemetry_risk > 0.3) {
            addTerminalLine('telemetry', 'Telemetry Agent', `Anomalous readings detected in ${state.peakZone}. Risk: ${peakZoneData.telemetry_risk.toFixed(2)}`);
        }
        if (peakZoneData.permit_factor > 0.2) {
            addTerminalLine('permit', 'Permit Agent', `Active Hot Work Permit found in vicinity. Escalating risk.`);
        }
        if (peakZoneData.vision_factor > 0.2) {
            addTerminalLine('vision', 'Vision Agent', `PPE Violations observed in zone. Workers at risk.`);
        }
        
        if (action !== 'CONTINUOUS_MONITORING') {
            addTerminalLine('decision', 'Decision Agent', `RECOMMENDATION: ${action}`, isCritical);
        }
    }
}

// ─── Event Timeline ───────────────────────────────────────────────────────────
function refreshTimeline() {
    const container = document.getElementById('timelineList');
    const countEl = document.getElementById('eventCount');
    if (!container) return;

    countEl.textContent = `${state.events.length} events`;

    if (state.events.length === 0) {
        container.innerHTML = `
            <div class="timeline-empty">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#2a3a4a" stroke-width="1.5">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <p>No safety events recorded yet.</p>
                <p class="timeline-hint">Run the simulation to see real-time events.</p>
            </div>
        `;
        return;
    }

    const eventsHTML = state.events.slice(0, 50).map(event => {
        const severity = (event.severity || 'INFO').toLowerCase();
        const time = formatTime(event.timestamp);
        const isEmergency = severity === 'emergency';

        return `
            <div class="timeline-event ${isEmergency ? 'emergency' : ''}">
                <div class="event-severity-dot ${severity}"></div>
                <div class="event-content">
                    <div class="event-header">
                        <span class="event-title">${escapeHTML(event.title || 'Event')}</span>
                        <span class="event-zone">${escapeHTML(event.zone_id || '')}</span>
                    </div>
                    <p class="event-description">${escapeHTML(event.description || '')}</p>
                </div>
                <span class="event-time">${time}</span>
            </div>
        `;
    }).join('');

    container.innerHTML = eventsHTML;
}

function formatTime(isoString) {
    if (!isoString) return '--:--';
    try {
        const d = new Date(isoString);
        const h = String(d.getHours()).padStart(2, '0');
        const m = String(d.getMinutes()).padStart(2, '0');
        const s = String(d.getSeconds()).padStart(2, '0');
        return `${h}:${m}:${s}`;
    } catch {
        return '--:--';
    }
}

function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ─── Simulation Engine ────────────────────────────────────────────────────────
async function runSimulation() {
    if (state.simulationRunning) return;
    state.simulationRunning = true;

    const runBtn = document.getElementById('runSimulationBtn');
    const resetBtn = document.getElementById('resetSimulationBtn');
    runBtn.disabled = true;
    resetBtn.style.display = 'none';

    // Reset step indicators
    for (let i = 1; i <= 5; i++) {
        const step = document.getElementById(`simStep${i}`);
        const status = document.getElementById(`simStep${i}Status`);
        step.classList.remove('running', 'done', 'critical-step');
        status.textContent = '⏳';
    }

    try {
        // ── Step 1: Baseline Telemetry ──
        await setStepRunning(1);
        await apiPost('/api/telemetry', {
            sensor_id: 'SCADA_001',
            zone_id: 'ZONE_COKE_OVEN_04',
            carbon_monoxide_ppm: 12.0,
            methane_percentage_lel: 5.0,
            ambient_temperature_celsius: 38.0,
            pressure_bar: 1.02
        });
        await setStepDone(1);
        await sleep(1200);

        // ── Step 2: Register Hot Work Permit ──
        await setStepRunning(2);
        await apiPost('/api/permit', {
            permit_id: 'PTW-2026-0042',
            permit_type: 'HOT_WORK',
            zone_id: 'ZONE_COKE_OVEN_04',
            authorized_personnel: ['R. Sharma', 'K. Patel', 'M. Singh']
        });
        await setStepDone(2);
        await sleep(1200);

        // ── Step 3: Gas Accumulation ──
        await setStepRunning(3);
        await apiPost('/api/telemetry', {
            sensor_id: 'SCADA_001',
            zone_id: 'ZONE_COKE_OVEN_04',
            carbon_monoxide_ppm: 45.0,
            methane_percentage_lel: 12.0,
            ambient_temperature_celsius: 42.0,
            pressure_bar: 1.05
        });
        await setStepDone(3);
        await sleep(1200);

        // ── Step 4: PPE Violations ──
        await setStepRunning(4);
        await apiPost('/api/vision', {
            camera_id: 'CAM_CO_04_A',
            zone_id: 'ZONE_COKE_OVEN_04',
            person_count: 5,
            ppe_violations: ['NO_HELMET', 'NO_GAS_MASK', 'NO_SAFETY_HARNESS']
        });
        await setStepDone(4);
        await sleep(1200);

        // ── Step 5: Final Compound Risk Evaluation ──
        await setStepRunning(5);
        const result = await apiPost('/api/telemetry', {
            sensor_id: 'SCADA_001',
            zone_id: 'ZONE_COKE_OVEN_04',
            carbon_monoxide_ppm: 85.0,
            methane_percentage_lel: 38.0,
            ambient_temperature_celsius: 52.0,
            pressure_bar: 1.15
        });
        await setStepDone(5, result?.critical_flag);

        // If critical, show emergency overlay
        if (result?.critical_flag) {
            showEmergencyOverlay(
                'ZONE_COKE_OVEN_04',
                result.computed_dri
            );
        }

    } catch (error) {
        console.error('Simulation error:', error);
        addEventToTimeline({
            timestamp: new Date().toISOString(),
            zone_id: 'SYSTEM',
            event_type: 'SYSTEM',
            severity: 'WARNING',
            title: 'Simulation Error',
            description: `Simulation could not reach the backend API: ${error.message}. Make sure the server is running.`,
            dri: null,
            agent: 'System'
        });
        refreshTimeline();
    }

    state.simulationRunning = false;
    runBtn.disabled = false;
    resetBtn.style.display = 'flex';
}

async function setStepRunning(n) {
    const step = document.getElementById(`simStep${n}`);
    const status = document.getElementById(`simStep${n}Status`);
    step.classList.add('running');
    status.textContent = '⚡';
}

async function setStepDone(n, isCritical = false) {
    const step = document.getElementById(`simStep${n}`);
    const status = document.getElementById(`simStep${n}Status`);
    step.classList.remove('running');
    step.classList.add('done');
    if (isCritical) {
        step.classList.add('critical-step');
        status.textContent = '🚨';
    } else {
        status.textContent = '✅';
    }
}

function resetSimulation() {
    // Reset step indicators
    for (let i = 1; i <= 5; i++) {
        const step = document.getElementById(`simStep${i}`);
        const status = document.getElementById(`simStep${i}Status`);
        step.classList.remove('running', 'done', 'critical-step');
        status.textContent = '⏳';
    }
    document.getElementById('resetSimulationBtn').style.display = 'none';

    // Reset state
    state.zones = {};
    state.events = [];
    state.peakDRI = 0;
    state.totalPermits = 0;
    state.totalViolations = 0;
    state.targetGaugeDRI = 0;
    state.peakZone = null;

    refreshAllUI();
}

// ─── Emergency Overlay ────────────────────────────────────────────────────────
function showEmergencyOverlay(zoneId, dri) {
    const overlay = document.getElementById('emergencyOverlay');
    document.getElementById('emergencyZone').textContent = zoneId;
    document.getElementById('emergencyDRI').textContent = `DRI: ${dri.toFixed(4)}`;
    overlay.classList.add('active');

    // Play alarm sound pattern via Web Audio API
    playAlarmSound();
}

function dismissEmergency() {
    const overlay = document.getElementById('emergencyOverlay');
    overlay.classList.remove('active');
}

function playAlarmSound() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

        function beep(freq, startTime, duration) {
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.frequency.value = freq;
            osc.type = 'sine';
            gain.gain.setValueAtTime(0.15, startTime);
            gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);
            osc.start(startTime);
            osc.stop(startTime + duration);
        }

        const now = audioCtx.currentTime;
        beep(880, now, 0.2);
        beep(660, now + 0.25, 0.2);
        beep(880, now + 0.5, 0.2);
    } catch (e) {
        // Audio not available, skip
    }
}

// ─── API Helpers ──────────────────────────────────────────────────────────────
async function apiPost(url, body) {
    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    return response.json();
}

async function apiGet(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    return response.json();
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// ─── Zone Click Handler ──────────────────────────────────────────────────────
function setupZoneClicks() {
    document.querySelectorAll('.zone-group').forEach(group => {
        group.addEventListener('click', () => {
            const zoneId = group.dataset.zone;
            if (!zoneId) return;

            const zoneData = state.zones[zoneId];
            if (!zoneData) {
                showZoneTooltip(group, zoneId, null);
                return;
            }
            showZoneTooltip(group, zoneId, zoneData);
        });
    });
}

function showZoneTooltip(element, zoneId, data) {
    // Remove existing tooltips
    document.querySelectorAll('.zone-tooltip').forEach(t => t.remove());

    const tooltip = document.createElement('div');
    tooltip.className = 'zone-tooltip';

    const zoneName = ZONE_NAMES[zoneId] || zoneId;

    if (!data) {
        tooltip.innerHTML = `
            <div class="tooltip-header">${zoneName}</div>
            <div class="tooltip-body">
                <p>No data received yet.</p>
                <p class="tooltip-hint">Run the simulation to see live data.</p>
            </div>
        `;
    } else {
        const riskLevel = data.risk_level || 'NORMAL';
        const dri = (data.computed_dri || 0).toFixed(4);
        const color = getRiskColor(riskLevel);

        tooltip.innerHTML = `
            <div class="tooltip-header" style="border-left: 3px solid ${color};">
                <span class="tooltip-title">${zoneName}</span>
                <span class="tooltip-badge" style="color:${color}; background:${hexToRgba(color, 0.1)}">${riskLevel}</span>
            </div>
            <div class="tooltip-body">
                <div class="tooltip-dri" style="color:${color}">DRI: ${dri}</div>
                <div class="tooltip-factors">
                    <div><span>Telemetry:</span><span>${(data.telemetry_risk || 0).toFixed(3)}</span></div>
                    <div><span>Permits:</span><span>${(data.permit_factor || 0).toFixed(3)}</span></div>
                    <div><span>Vision:</span><span>${(data.vision_factor || 0).toFixed(3)}</span></div>
                </div>
                ${data.recommended_action ? `<div class="tooltip-action">→ ${data.recommended_action}</div>` : ''}
            </div>
        `;
    }

    document.body.appendChild(tooltip);

    // Position tooltip near the clicked zone
    const rect = element.getBoundingClientRect();
    tooltip.style.position = 'fixed';
    tooltip.style.left = `${rect.right + 10}px`;
    tooltip.style.top = `${rect.top}px`;
    tooltip.style.zIndex = '500';

    // Keep tooltip within viewport
    const tooltipRect = tooltip.getBoundingClientRect();
    if (tooltipRect.right > window.innerWidth) {
        tooltip.style.left = `${rect.left - tooltipRect.width - 10}px`;
    }
    if (tooltipRect.bottom > window.innerHeight) {
        tooltip.style.top = `${window.innerHeight - tooltipRect.height - 10}px`;
    }

    // Dismiss on click elsewhere
    const dismissHandler = (e) => {
        if (!tooltip.contains(e.target) && !element.contains(e.target)) {
            tooltip.remove();
            document.removeEventListener('click', dismissHandler);
        }
    };
    setTimeout(() => document.addEventListener('click', dismissHandler), 100);

    // Auto-dismiss after 6 seconds
    setTimeout(() => {
        tooltip.remove();
        document.removeEventListener('click', dismissHandler);
    }, 6000);
}

// ─── Initial Data Fetch (for when WS is not available) ────────────────────────
async function fetchInitialData() {
    try {
        const [zones, events] = await Promise.all([
            apiGet('/api/zones'),
            apiGet('/api/events?limit=50')
        ]);

        zones.forEach(z => {
            if (z.zone_id) state.zones[z.zone_id] = z;
        });

        state.events = events || [];
        refreshAllUI();
    } catch (e) {
        console.log('Initial data fetch skipped (server may not be running):', e.message);
    }
}

// ─── Keyboard Shortcuts ──────────────────────────────────────────────────────
document.addEventListener('keydown', (e) => {
    // Escape to dismiss emergency
    if (e.key === 'Escape') {
        dismissEmergency();
    }
    // 'S' to start simulation
    if (e.key === 's' || e.key === 'S') {
        if (!state.simulationRunning && e.target === document.body) {
            runSimulation();
        }
    }
    // 'R' to reset
    if (e.key === 'r' || e.key === 'R') {
        if (!state.simulationRunning && e.target === document.body) {
            resetSimulation();
        }
    }
});

// ─── Window Resize Handler ───────────────────────────────────────────────────
let resizeTimer;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
        drawGauge(state.currentGaugeDRI);
    }, 200);
});

// ─── Initialize ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    console.log('🛡️ SentinelSafe Dashboard Initializing...');

    // Draw initial empty gauge
    drawGauge(0);

    // Setup zone click handlers
    setupZoneClicks();

    // Fetch initial data
    fetchInitialData();

    // Connect WebSocket
    connectWebSocket();

    // Periodic ping to keep WS alive
    setInterval(() => {
        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send('ping');
        }
    }, 30000);

    // Initialize worker dots on the plant map
    initWorkers();

    console.log('✅ SentinelSafe Dashboard Ready');
});

// ─── Innovative Additions: Workers & Terminal ──────────────────────────────────
function initWorkers() {
    state.workers = [];
    ZONE_IDS.forEach(zoneId => {
        const group = document.getElementById(`zone-${zoneId}`);
        if (!group) return;

        // Bounding box of the zone rect
        const rect = group.querySelector('.zone-rect');
        if (!rect) return;

        const x = parseFloat(rect.getAttribute('x'));
        const y = parseFloat(rect.getAttribute('y'));
        const w = parseFloat(rect.getAttribute('width'));
        const h = parseFloat(rect.getAttribute('height'));

        // Add 3 random workers per zone
        for (let i = 0; i < 3; i++) {
            const wx = x + 20 + Math.random() * (w - 40);
            const wy = y + 40 + Math.random() * (h - 60);

            const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("cx", wx);
            circle.setAttribute("cy", wy);
            circle.setAttribute("r", "3");
            circle.setAttribute("class", "worker-dot safe");
            group.appendChild(circle);

            state.workers.push({
                element: circle,
                x: wx, y: wy,
                minX: x + 10, maxX: x + w - 10,
                minY: y + 30, maxY: y + h - 10,
                targetX: wx, targetY: wy
            });
        }
    });

    // Start animation loop
    requestAnimationFrame(animateWorkers);
}

function animateWorkers() {
    state.workers.forEach(w => {
        // Occasionally pick a new target
        if (Math.random() < 0.02) {
            w.targetX = w.minX + Math.random() * (w.maxX - w.minX);
            w.targetY = w.minY + Math.random() * (w.maxY - w.minY);
        }

        // Move towards target smoothly
        const dx = w.targetX - w.x;
        const dy = w.targetY - w.y;
        w.x += dx * 0.05;
        w.y += dy * 0.05;

        w.element.setAttribute('cx', w.x);
        w.element.setAttribute('cy', w.y);
    });
    requestAnimationFrame(animateWorkers);
}

function addTerminalLine(agentClass, agentName, text, isCritical = false) {
    const terminal = document.getElementById('agentTerminal');
    if (!terminal) return;

    const msgKey = `${agentClass}-${text}`;
    if (state.lastTerminalMsg === msgKey) return; // Prevent spam
    state.lastTerminalMsg = msgKey;

    const line = document.createElement('div');
    line.className = `terminal-line ${agentClass} ${isCritical ? 'critical' : ''}`;
    
    const now = new Date();
    const ts = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;

    line.innerHTML = `<span class="timestamp">[${ts}]</span><span class="agent-name">[${agentName}]</span> ${text}`;
    terminal.appendChild(line);

    // Auto scroll
    terminal.scrollTop = terminal.scrollHeight;
    
    // Limit lines
    while (terminal.children.length > 20) {
        terminal.removeChild(terminal.firstChild);
    }
}

