document.addEventListener('DOMContentLoaded', () => {
    // ECharts Setup
    const riskGaugeDom = document.getElementById('risk-gauge');
    const riskGauge = echarts.init(riskGaugeDom, 'dark');
    
    const gaugeOption = {
        backgroundColor: 'transparent',
        series: [
            {
                type: 'gauge',
                startAngle: 180,
                endAngle: 0,
                min: 0,
                max: 100,
                splitNumber: 10,
                itemStyle: {
                    color: '#00f0ff',
                    shadowColor: 'rgba(0,240,255,0.4)',
                    shadowBlur: 10,
                    shadowOffsetX: 2,
                    shadowOffsetY: 2
                },
                progress: {
                    show: true,
                    roundCap: true,
                    width: 18
                },
                pointer: {
                    icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
                    length: '12%',
                    width: 20,
                    offsetCenter: [0, '-60%'],
                    itemStyle: {
                        color: 'auto'
                    }
                },
                axisLine: {
                    roundCap: true,
                    lineStyle: {
                        width: 18,
                        color: [
                            [0.3, 'rgba(0,255,136,0.3)'],
                            [0.7, 'rgba(255,221,0,0.3)'],
                            [1, 'rgba(255,0,60,0.3)']
                        ]
                    }
                },
                axisTick: {
                    splitNumber: 2,
                    lineStyle: {
                        width: 2,
                        color: 'rgba(255,255,255,0.2)'
                    }
                },
                splitLine: {
                    length: 12,
                    lineStyle: {
                        width: 3,
                        color: 'rgba(255,255,255,0.5)'
                    }
                },
                axisLabel: {
                    distance: 30,
                    color: '#94a1b2',
                    fontSize: 14
                },
                title: {
                    show: false
                },
                detail: {
                    backgroundColor: 'transparent',
                    width: '60%',
                    lineHeight: 40,
                    height: 40,
                    borderRadius: 8,
                    offsetCenter: [0, '35%'],
                    valueAnimation: true,
                    formatter: function (value) {
                        return '{value|' + value.toFixed(0) + '}{unit|/100}';
                    },
                    rich: {
                        value: {
                            fontSize: 50,
                            fontWeight: 'bolder',
                            color: '#fff'
                        },
                        unit: {
                            fontSize: 20,
                            color: '#94a1b2',
                            padding: [0, 0, -20, 10]
                        }
                    }
                },
                data: [{ value: 0 }]
            }
        ]
    };
    riskGauge.setOption(gaugeOption);
    
    window.addEventListener('resize', () => {
        riskGauge.resize();
    });

    // DOM Elements
    const connectionStatus = document.getElementById('connection-status');
    const stateBadge = document.getElementById('current-state-badge');
    const ctxSource = document.getElementById('ctx-source');
    const ctxStage = document.getElementById('ctx-stage');
    const ctxSeverity = document.getElementById('ctx-severity');
    const ctxGeneration = document.getElementById('ctx-generation');
    const aiTitle = document.getElementById('ai-title');
    const aiSummary = document.getElementById('ai-summary');
    const timelineList = document.getElementById('timeline-list');
    const eventsBody = document.getElementById('events-body');
    
    // State renderers
    function updateStateBadge(stateName) {
        stateBadge.textContent = stateName;
        stateBadge.className = 'state-badge'; // Reset
        
        if (stateName === 'NORMAL') {
            stateBadge.classList.add('normal');
        } else if (stateName === 'UNDER_OBSERVATION') {
            stateBadge.classList.add('observation');
        } else if (stateName === 'CRITICAL_INTRUSION' || stateName === 'CONTAINMENT') {
            stateBadge.classList.add('critical');
        } else {
            stateBadge.classList.add('observation'); // Fallback
        }
    }
    
    function updateRiskGauge(riskScore) {
        let color = '#00ff88'; // Normal
        if (riskScore > 30) color = '#ffdd00'; // Observation
        if (riskScore > 70) color = '#ff003c'; // Critical
        
        riskGauge.setOption({
            series: [{
                itemStyle: {
                    color: color,
                    shadowColor: color
                },
                data: [{ value: riskScore }]
            }]
        });
    }
    
    function updateContext(payload) {
        updateStateBadge(payload.current_state);
        updateRiskGauge(payload.current_risk);
        
        ctxSource.textContent = payload.current_source || '--';
        ctxStage.textContent = payload.current_stage || '--';
        ctxGeneration.textContent = payload.generation || '0';
        
        if (payload.ai_result) {
            const ai = payload.ai_result;
            ctxSeverity.textContent = ai.severity || '--';
            aiTitle.textContent = ai.executive_title || 'AI Assessment Complete';
            aiSummary.textContent = ai.executive_summary || 'No summary provided.';
        } else {
            ctxSeverity.textContent = '--';
            aiTitle.textContent = 'Awaiting Telemetry...';
            aiSummary.textContent = 'No active AI classification.';
        }
        
        // Update Timeline
        if (payload.timeline && payload.timeline.length > 0) {
            timelineList.innerHTML = '';
            payload.timeline.forEach(stage => {
                const li = document.createElement('li');
                li.textContent = stage;
                timelineList.appendChild(li);
            });
        } else {
            timelineList.innerHTML = '<li class="timeline-empty">No active incidents.</li>';
        }
    }
    
    function addEventRow(eventData) {
        const tr = document.createElement('tr');
        tr.className = 'new-row';
        
        // Parse time
        let timeStr = eventData.timestamp;
        try {
            const date = new Date(eventData.timestamp);
            if (!isNaN(date.getTime())) {
                timeStr = date.toLocaleTimeString();
            }
        } catch(e) {}
        
        // Risk pill formatting
        const risk = eventData.risk || 0;
        let riskColor = 'rgba(255,255,255,0.1)';
        let textColor = '#fff';
        if (risk > 70) {
            riskColor = 'rgba(255,0,60,0.2)';
            textColor = '#ff003c';
        } else if (risk > 30) {
            riskColor = 'rgba(255,221,0,0.2)';
            textColor = '#ffdd00';
        } else if (risk > 0) {
            riskColor = 'rgba(0,255,136,0.2)';
            textColor = '#00ff88';
        }
        
        tr.innerHTML = `
            <td>${timeStr}</td>
            <td>${eventData.source || '--'}</td>
            <td>${eventData.target_service || '--'}</td>
            <td>${eventData.event_type || '--'}</td>
            <td><span class="risk-pill" style="background:${riskColor}; color:${textColor}">${risk}</span></td>
        `;
        
        eventsBody.insertBefore(tr, eventsBody.firstChild);
        
        // Keep max 50 rows
        while (eventsBody.children.length > 50) {
            eventsBody.removeChild(eventsBody.lastChild);
        }
        
        // Remove animation class after 1s
        setTimeout(() => {
            tr.classList.remove('new-row');
        }, 1000);
    }
    
    // SSE Connection Setup
    function setupSSE() {
        const evtSource = new EventSource('/events');
        
        evtSource.onmessage = function(event) {
            // Heartbeat
            if (event.data === ": heartbeat") return;
            
            try {
                const data = JSON.parse(event.data);
                
                if (data.kind === "STATE") {
                    updateContext(data.payload);
                } else if (data.kind === "EVENT") {
                    addEventRow(data.payload.normalized || data.payload);
                } else if (data.kind === "AI_RESULT") {
                    // Usually followed by a STATE broadcast, but we can do a toast here if needed
                    console.log("Received AI_RESULT:", data.payload);
                }
            } catch(e) {
                console.error("Failed to parse SSE data:", e);
            }
        };
        
        evtSource.onerror = function(err) {
            console.error("EventSource failed:", err);
            connectionStatus.textContent = "Disconnected (Retrying...)";
            connectionStatus.style.color = "var(--accent-magenta)";
            document.querySelector('.pulse-dot').style.backgroundColor = "var(--accent-magenta)";
            document.querySelector('.pulse-dot').style.boxShadow = "0 0 10px var(--accent-magenta)";
        };
        
        evtSource.onopen = function() {
            connectionStatus.textContent = "Live Monitoring";
            connectionStatus.style.color = "var(--text-secondary)";
            document.querySelector('.pulse-dot').style.backgroundColor = "var(--state-normal)";
            document.querySelector('.pulse-dot').style.boxShadow = "0 0 10px var(--state-normal)";
        };
    }
    
    setupSSE();
});
