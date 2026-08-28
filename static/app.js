let audioArmed = false;
let audioCtx = null;
let lastCriticalAudioGen = -1;
let currentGeneration = 0;

let riskGaugeChart = null;
let networkMapChart = null;

document.addEventListener('DOMContentLoaded', () => {
    // Initialize Risk Gauge
    const gaugeDom = document.getElementById('risk-gauge');
    if (gaugeDom && window.echarts) {
        riskGaugeChart = echarts.init(gaugeDom);
        riskGaugeChart.setOption({
            series: [{
                type: 'gauge',
                progress: { show: true },
                detail: { valueAnimation: true, formatter: '{value}' },
                data: [{ value: 0, name: 'Risk' }]
            }]
        });
    }

    // Initialize Network Map
    const mapDom = document.getElementById('network-map');
    if (mapDom && window.echarts) {
        networkMapChart = echarts.init(mapDom);
        networkMapChart.setOption({
            series: [{
                type: 'graph',
                layout: 'force',
                roam: true,
                label: { show: true, position: 'right' },
                force: { repulsion: 200, edgeLength: 100 },
                data: [
                    { name: 'Internet' },
                    { name: 'Gateway' },
                    { name: 'Web Service' },
                    { name: 'File Service' },
                    { name: 'Admin System' },
                    { name: 'Digital Vault' }
                ],
                links: []
            }]
        });
    }

    window.addEventListener('resize', () => {
        if (riskGaugeChart) riskGaugeChart.resize();
        if (networkMapChart) networkMapChart.resize();
    });

    const sse = new EventSource('/events');
    sse.addEventListener('message', (e) => {
        try {
            const data = JSON.parse(e.data);
            if (data.payload && typeof data.payload.generation !== 'undefined') {
                currentGeneration = data.payload.generation;
            }
            if (data.kind === 'STATE') {
                handleStateUpdate(data.payload);
            } else if (data.kind === 'EVENT') {
                handleEventUpdate(data.payload);
            } else if (data.kind === 'AI_RESULT') {
                handleAiResult(data.payload);
            } else if (data.kind === 'RESET') {
                handleReset();
            }
        } catch (err) {
            console.error('Failed to parse SSE data', err);
        }
    });
});

function handleStateUpdate(payload) {
    document.getElementById('kpi-events').textContent = payload.event_count || 0;
    document.getElementById('kpi-status').textContent = payload.current_state || 'NORMAL';
    
    // Update body state class for critical pulse
    if (payload.current_state === 'CRITICAL_INTRUSION') {
        document.body.classList.add('state-critical');
        playCriticalAudio();
    } else {
        document.body.classList.remove('state-critical');
    }
    
    updateCharts(payload);

    if (payload.current_state === 'CONTAINED') {
        document.getElementById('kpi-status').textContent = 'THREAT CONTAINED';
        document.body.classList.remove('state-critical');
    }

    updateTimeline(payload.timeline || []);

    if (payload.ai_result) {
        handleAiResult(payload.ai_result);
    }
}

function handleEventUpdate(payload) {
    document.getElementById('kpi-events').textContent = payload.event_count;
    document.getElementById('kpi-status').textContent = payload.current_state;
    if (payload.raw_event && payload.raw_event.target_service) {
        document.getElementById('kpi-target').textContent = payload.raw_event.target_service;
    }
    
    // Show AI analyzing
    const aiIndicator = document.getElementById('ai-status-indicator');
    aiIndicator.textContent = 'Analyzing with Groq AI...';
    aiIndicator.classList.remove('hidden');
    document.getElementById('ai-content').classList.add('hidden');

    updateTimeline(payload.timeline || []);

    if (payload.current_state === 'CRITICAL_INTRUSION') {
        document.body.classList.add('state-critical');
        playCriticalAudio();
    }
    
    updateCharts({ current_risk: payload.current_risk, raw_event: payload.raw_event });
}

function handleAiResult(result) {
    if (!result) return;
    document.getElementById('ai-status-indicator').classList.add('hidden');
    document.getElementById('ai-content').classList.remove('hidden');

    document.getElementById('ai-title').textContent = result.executive_title || 'No Title';
    document.getElementById('ai-summary').textContent = result.executive_summary || '';
    document.getElementById('ai-impact').textContent = result.business_impact || '';
    document.getElementById('ai-action').textContent = result.recommended_action || '';
    document.getElementById('ai-severity').textContent = result.severity || '';
}

function handleReset() {
    lastCriticalAudioGen = -1;
    document.getElementById('kpi-events').textContent = '0';
    document.getElementById('kpi-status').textContent = 'NORMAL';
    document.getElementById('kpi-target').textContent = 'N/A';
    
    document.body.classList.remove('state-critical');
    document.body.classList.remove('executive-mode');
    document.getElementById('crime-scene-panel').classList.add('hidden');
    
    document.getElementById('ai-status-indicator').textContent = 'No active threats.';
    document.getElementById('ai-status-indicator').classList.remove('hidden');
    document.getElementById('ai-content').classList.add('hidden');
    
    updateTimeline([]);
    
    if (riskGaugeChart) {
        riskGaugeChart.setOption({
            series: [{ data: [{ value: 0, name: 'Risk' }] }]
        });
    }
    if (networkMapChart) {
        networkMapChart.setOption({
            series: [{ links: [] }]
        });
    }
}

function updateCharts(payload) {
    if (riskGaugeChart && payload.current_risk !== undefined) {
        riskGaugeChart.setOption({
            series: [{ data: [{ value: payload.current_risk, name: 'Risk' }] }]
        });
    }
    if (networkMapChart && payload.raw_event && payload.raw_event.source && payload.raw_event.target_service) {
        const source = 'Internet';
        const target = payload.raw_event.target_service;
        networkMapChart.setOption({
            series: [{
                links: [{ source: source, target: target }]
            }]
        });
    }
}

function updateTimeline(timeline) {
    document.getElementById('stage-discovery').className = 'stage' + (timeline.includes('Discovery') ? ' active' : '');
    document.getElementById('stage-probe').className = 'stage' + (timeline.includes('Service Probe') ? ' active' : '');
    document.getElementById('stage-access').className = 'stage' + (timeline.includes('Access Attempt') ? ' active' : '');
    document.getElementById('stage-escalation').className = 'stage' + (timeline.includes('Escalation') ? ' critical' : '');
    document.getElementById('stage-containment').className = 'stage' + (timeline.includes('Containment') ? ' active' : '');
}

async function isolateThreat() {
    try {
        await fetch('/contain', { method: 'POST' });
    } catch (e) {
        console.error('Isolation failed', e);
    }
}

async function reconstructCrimeScene() {
    try {
        const res = await fetch('/crime-scene', { method: 'POST' });
        const data = await res.json();
        
        document.getElementById('cs-first-seen').textContent = data.first_seen || 'N/A';
        document.getElementById('cs-origin').textContent = data.origin || 'N/A';
        document.getElementById('cs-first-target').textContent = data.first_target || 'N/A';
        document.getElementById('cs-sequence').textContent = (data.activity_sequence || []).join(' → ') || 'N/A';
        document.getElementById('cs-transition').textContent = data.critical_transition || 'N/A';
        
        document.getElementById('crime-scene-panel').classList.remove('hidden');
    } catch (e) {
        console.error('Crime scene failed', e);
    }
}

function toggleExecutiveSummary() {
    document.body.classList.toggle('executive-mode');
}

async function resetDemo() {
    try {
        await fetch('/demo/reset', { method: 'POST' });
    } catch (e) {
        console.error('Reset failed', e);
    }
}

async function replayEvent(num) {
    try {
        await fetch('/demo/replay/' + num, { method: 'POST' });
    } catch (e) {
        console.error('Replay failed', e);
    }
}

async function armAudio() {
    audioArmed = true;
    const btn = document.getElementById('btn-arm-audio');
    btn.classList.add('armed');
    btn.textContent = 'AUDIO ARMED';
    
    try {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            await audioCtx.resume();
        }
    } catch (e) {
        console.error('Failed to init AudioContext', e);
    }
}

function playCriticalAudio() {
    if (!audioArmed || !audioCtx) return;
    if (lastCriticalAudioGen === currentGeneration) return; // Deduplicate
    lastCriticalAudioGen = currentGeneration;

    try {
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
        
        const osc = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        
        osc.type = 'square';
        osc.frequency.setValueAtTime(880, audioCtx.currentTime); // A5
        osc.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.1);
        
        gainNode.gain.setValueAtTime(0, audioCtx.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.5, audioCtx.currentTime + 0.05);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5);
        
        osc.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        osc.start();
        osc.stop(audioCtx.currentTime + 0.6);
    } catch (e) {
        console.error('Audio playback failed', e);
    }
}
