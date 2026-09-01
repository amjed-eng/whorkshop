let audioArmed = false;
let audioCtx = null;
let lastCriticalAudioGen = -1;
let currentGeneration = 0;

let riskGaugeChart = null;
let networkMapChart = null;
let timelineChart = null;

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

    // Initialize Timeline Chart
    const timelineDom = document.getElementById('timeline-chart');
    if (timelineDom && window.echarts) {
        timelineChart = echarts.init(timelineDom);
        timelineChart.setOption({
            grid: { left: '10%', right: '10%', top: '20%', bottom: '20%' },
            xAxis: {
                type: 'category',
                data: ['Discovery', 'Service Probe', 'Access Attempt', 'Escalation', 'Containment'],
                axisLine: { lineStyle: { color: '#00ffcc' } },
                axisLabel: { color: '#00ffcc', interval: 0 }
            },
            yAxis: { type: 'value', show: false, min: 0, max: 1 },
            series: [{
                type: 'scatter',
                symbolSize: 25,
                data: [
                    { value: 0, itemStyle: { color: '#555' } },
                    { value: 0, itemStyle: { color: '#555' } },
                    { value: 0, itemStyle: { color: '#555' } },
                    { value: 0, itemStyle: { color: '#555' } },
                    { value: 0, itemStyle: { color: '#555' } }
                ]
            }]
        });
    }

    window.addEventListener('resize', () => {
        if (riskGaugeChart) riskGaugeChart.resize();
        if (networkMapChart) networkMapChart.resize();
        if (timelineChart) timelineChart.resize();
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
    if (payload.most_targeted_asset) {
        document.getElementById('kpi-target').textContent = payload.most_targeted_asset;
    }
    
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

    if (payload.current_state === 'EXECUTIVE') {
        document.body.classList.add('executive-mode');
    } else {
        document.body.classList.remove('executive-mode');
    }

    updateTimeline(payload.timeline || []);

    if (payload.ai_result) {
        handleAiResult(payload.ai_result);
    }
}

function handleEventUpdate(payload) {
    if (payload.normalized && payload.normalized.target_service) {
        document.getElementById('kpi-target').textContent = payload.normalized.target_service;
    }
    
    // Show AI analyzing
    const aiIndicator = document.getElementById('ai-status-indicator');
    aiIndicator.textContent = 'Analyzing with Groq AI...';
    aiIndicator.classList.remove('hidden');
    document.getElementById('ai-content').classList.add('hidden');

    // EVENT carries normalized evidence only. Risk/state/timeline arrive in the
    // immediately following STATE frame, so do not clear or fabricate them here.
    if (payload.normalized) {
        updateCharts({
            current_risk: payload.current_risk, 
            source: payload.normalized.source, 
            target_service: payload.normalized.target_service
        });
    }
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
    if (timelineChart) {
        timelineChart.setOption({
            series: [{
                data: [
                    { value: 0, itemStyle: { color: '#555' } },
                    { value: 0, itemStyle: { color: '#555' } },
                    { value: 0, itemStyle: { color: '#555' } },
                    { value: 0, itemStyle: { color: '#555' } },
                    { value: 0, itemStyle: { color: '#555' } }
                ]
            }]
        });
    }
}

function mapTargetToCityNode(targetService) {
    const raw = String(targetService || '').trim();
    const target = raw.toLowerCase();
    if (!target) return '';

    if (target.includes('vault') || target.includes('secret')) return 'Digital Vault';
    if (target.includes('admin') || target.includes('management') || target.includes('ssh') || target.includes('rdp')) return 'Admin System';
    if (target.includes('file') || target.includes('ftp') || target.includes('smb') || target.includes('nfs')) return 'File Service';
    if (target.includes('web') || target.includes('http') || target.includes('https')) return 'Web Service';
    if (target.includes('gateway') || target.includes('router') || target.includes('dns')) return 'Gateway';
    return raw;
}

function updateCharts(payload) {
    if (riskGaugeChart && payload.current_risk !== undefined) {
        riskGaugeChart.setOption({
            series: [{ data: [{ value: payload.current_risk, name: 'Risk' }] }]
        });
    }
    if (networkMapChart && payload.source && payload.target_service) {
        const source = String(payload.source);
        const target = mapTargetToCityNode(payload.target_service);

        const baseNodes = [
            { name: 'Internet' },
            { name: 'Gateway' },
            { name: 'Web Service' },
            { name: 'File Service' },
            { name: 'Admin System' },
            { name: 'Digital Vault' }
        ];

        const nodes = [...baseNodes];
        if (!nodes.find(n => n.name === source)) {
            nodes.push({ name: source, itemStyle: { color: '#ff3b5f' } });
        }
        if (target && !nodes.find(n => n.name === target)) {
            nodes.push({ name: target, itemStyle: { color: '#ffcc66' } });
        }

        const links = [];
        if (source !== 'Gateway') {
            links.push({ source: source, target: 'Gateway' });
        }
        if (target && target !== 'Gateway') {
            links.push({ source: 'Gateway', target: target });
        }

        networkMapChart.setOption({
            series: [{
                data: nodes,
                links: links
            }]
        });
    }
}

function updateTimeline(timeline) {
    if (!timelineChart) return;
    
    const stages = ['Discovery', 'Service Probe', 'Access Attempt', 'Escalation', 'Containment'];
    const data = stages.map(stage => {
        if (timeline.includes(stage)) {
            if (stage === 'Escalation') {
                return { value: 0, itemStyle: { color: '#ff003c' } };
            }
            return { value: 0, itemStyle: { color: '#00ffcc' } };
        }
        return { value: 0, itemStyle: { color: '#555' } };
    });

    timelineChart.setOption({
        series: [{ data: data }]
    });
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

async function toggleExecutiveSummary() {
    try {
        const res = await fetch('/executive', { method: 'POST' });
        if (!res.ok) {
            throw new Error('Executive mode request failed');
        }
        document.body.classList.add('executive-mode');
    } catch (e) {
        console.error('Executive mode failed', e);
    }
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
    const btn = document.getElementById('btn-arm-audio');

    try {
        const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextCtor) {
            throw new Error('Web Audio API unavailable');
        }
        if (!audioCtx) {
            audioCtx = new AudioContextCtor();
        }
        if (audioCtx.state === 'suspended') {
            await audioCtx.resume();
        }
        audioArmed = true;
        btn.classList.add('armed');
        btn.textContent = 'AUDIO ARMED';
    } catch (e) {
        audioArmed = false;
        btn.classList.remove('armed');
        btn.textContent = 'AUDIO UNAVAILABLE';
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
