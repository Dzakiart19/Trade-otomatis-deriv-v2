if (window['chartjs-plugin-annotation']) {
    Chart.register(window['chartjs-plugin-annotation']);
}

class TradingDashboard {
    constructor() {
        this.ws = null;
        this.charts = {};
        this.priceData = {};
        this.positions = {};
        this.tradeHistory = [];
        this.totalTradesCount = 0;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 2000;
        this.authToken = null;
        this.pendingEntryMarkers = {};
        this.tickCount = 0;
        this.lastTickPrice = null;
        this.currentSignal = 'neutral';
        this.tickPickerData = null;
        this.currentStrategy = 'MULTI_INDICATOR';
        
        this.symbols = [
            'R_100', 'R_75', 'R_50', 'R_25', 'R_10',
            '1HZ100V', '1HZ75V', '1HZ50V'
        ];
        
        this.init();
    }
    
    init() {
        if (window.Telegram?.WebApp?.initData) {
            this.telegramAuth();
            return;
        }
        
        this.authToken = sessionStorage.getItem('dashboard_token');
        
        if (!this.authToken) {
            this.showAuthPrompt();
            return;
        }
        
        this.initCharts();
        this.connectWebSocket();
        this.fetchInitialData();
        
        setInterval(() => this.sendPing(), 30000);
    }
    
    async telegramAuth() {
        const tg = window.Telegram.WebApp;
        const initData = tg.initData;
        
        sessionStorage.removeItem('dashboard_token');
        this.authToken = null;
        
        try {
            const response = await fetch('/api/auth/telegram', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ initData })
            });
            
            const data = await response.json();
            
            if (response.status === 403 && data.error === 'not_authenticated') {
                console.log('User not authenticated in bot, showing login required');
                this.showLoginRequired(data.message);
                tg.ready();
                return;
            }
            
            if (!response.ok) {
                console.error('Telegram auth failed:', response.status);
                this.showAuthPrompt();
                return;
            }
            
            if (data.success && data.token) {
                this.authToken = data.token;
                this.telegramUser = data.user;
                sessionStorage.setItem('dashboard_token', data.token);
                
                tg.ready();
                tg.expand();
                
                this.initCharts();
                this.connectWebSocket();
                this.fetchInitialData();
                this.showTelegramWelcome(data.user);
                
                setInterval(() => this.sendPing(), 30000);
            } else {
                console.error('Telegram auth response invalid:', data);
                this.showAuthPrompt();
            }
        } catch (e) {
            console.error('Telegram auth error:', e);
            this.showAuthPrompt();
        }
    }
    
    showTelegramWelcome(user) {
        const header = document.querySelector('.header h1');
        if (header && user?.first_name) {
            header.textContent = `Welcome, ${user.first_name}!`;
        }
    }
    
    showLoginRequired(message) {
        const container = document.querySelector('.container');
        container.innerHTML = `
            <div class="login-required-container">
                <div class="login-icon">🔒</div>
                <h1>Login Diperlukan</h1>
                <p class="message">${message || 'Anda belum login ke bot.'}</p>
                <div class="instructions">
                    <p><strong>Cara Login:</strong></p>
                    <ol>
                        <li>Kembali ke chat bot</li>
                        <li>Ketik <code>/login</code> atau <code>/start</code></li>
                        <li>Pilih tipe akun (Demo/Real)</li>
                        <li>Masukkan token API Deriv Anda</li>
                        <li>Setelah login berhasil, buka Dashboard lagi</li>
                    </ol>
                </div>
                <button id="close-btn" onclick="window.Telegram?.WebApp?.close()">Tutup</button>
            </div>
            <style>
                .login-required-container { 
                    max-width: 400px; 
                    margin: 50px auto; 
                    text-align: center;
                    background: var(--bg-secondary);
                    padding: 40px;
                    border-radius: 12px;
                    border: 1px solid var(--border-color);
                }
                .login-icon { font-size: 4rem; margin-bottom: 20px; }
                .login-required-container h1 { 
                    color: var(--accent-red); 
                    margin-bottom: 15px;
                    font-size: 1.5rem;
                }
                .login-required-container .message { 
                    color: var(--text-secondary); 
                    margin-bottom: 25px;
                    font-size: 1rem;
                }
                .instructions {
                    text-align: left;
                    background: var(--bg-card);
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 25px;
                }
                .instructions p { margin-bottom: 10px; color: var(--text-primary); }
                .instructions ol { 
                    margin: 0; 
                    padding-left: 20px;
                    color: var(--text-secondary);
                }
                .instructions li { margin-bottom: 8px; }
                .instructions code {
                    background: var(--bg-secondary);
                    padding: 2px 6px;
                    border-radius: 4px;
                    color: var(--accent-primary);
                }
                #close-btn {
                    width: 100%;
                    padding: 12px;
                    background: var(--accent-primary);
                    color: #fff;
                    border: none;
                    border-radius: 8px;
                    font-size: 1rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: opacity 0.2s;
                }
                #close-btn:hover { opacity: 0.9; }
            </style>
        `;
    }
    
    showAuthPrompt() {
        const container = document.querySelector('.container');
        container.innerHTML = `
            <div class="auth-container">
                <h1>Deriv Trading Bot Dashboard</h1>
                <div class="auth-form">
                    <p>Enter your dashboard access token to continue.</p>
                    <p class="hint">The token is displayed in the bot console logs when it starts.</p>
                    <input type="password" id="token-input" placeholder="Enter access token" autocomplete="off">
                    <button id="auth-btn">Connect</button>
                    <div id="auth-error" class="auth-error"></div>
                </div>
            </div>
            <style>
                .auth-container { 
                    max-width: 400px; 
                    margin: 100px auto; 
                    text-align: center;
                    background: var(--bg-secondary);
                    padding: 40px;
                    border-radius: 12px;
                    border: 1px solid var(--border-color);
                }
                .auth-form { margin-top: 30px; }
                .auth-form p { color: var(--text-secondary); margin-bottom: 10px; }
                .auth-form .hint { font-size: 0.85rem; color: #888; }
                #token-input {
                    width: 100%;
                    padding: 12px;
                    margin: 20px 0;
                    border: 1px solid var(--border-color);
                    border-radius: 8px;
                    background: var(--bg-card);
                    color: var(--text-primary);
                    font-size: 1rem;
                }
                #auth-btn {
                    width: 100%;
                    padding: 12px;
                    background: var(--accent-primary);
                    color: #fff;
                    border: none;
                    border-radius: 8px;
                    font-size: 1rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background 0.2s ease;
                }
                #auth-btn:hover { background: #2563EB; }
                .auth-error { 
                    color: var(--accent-red); 
                    margin-top: 15px;
                    font-size: 0.9rem;
                }
            </style>
        `;
        
        document.getElementById('auth-btn').addEventListener('click', () => this.authenticate());
        document.getElementById('token-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.authenticate();
        });
    }
    
    async authenticate() {
        const tokenInput = document.getElementById('token-input');
        const errorDiv = document.getElementById('auth-error');
        const token = tokenInput.value.trim();
        
        if (!token) {
            errorDiv.textContent = 'Please enter a token';
            return;
        }
        
        errorDiv.textContent = 'Verifying...';
        
        try {
            const response = await fetch('/api/health');
            if (!response.ok) throw new Error('Server not available');
            
            const testResponse = await fetch('/api/summary', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (testResponse.status === 401) {
                errorDiv.textContent = 'Invalid token. Please check and try again.';
                return;
            }
            
            if (!testResponse.ok) {
                throw new Error('Connection failed');
            }
            
            sessionStorage.setItem('dashboard_token', token);
            this.authToken = token;
            
            window.location.reload();
        } catch (e) {
            errorDiv.textContent = `Error: ${e.message}`;
        }
    }
    
    logout() {
        sessionStorage.removeItem('dashboard_token');
        window.location.reload();
    }
    
    initCharts() {
        this.symbols.forEach(symbol => {
            const canvas = document.getElementById(`chart-${symbol}`);
            if (!canvas) return;
            
            const ctx = canvas.getContext('2d');
            
            this.priceData[symbol] = {
                labels: [],
                prices: [],
                entryIndex: null,
                entryPrice: null
            };
            
            const chartOptions = {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: true },
                    annotation: {
                        annotations: {}
                    }
                },
                scales: {
                    x: {
                        display: false,
                        grid: { display: false }
                    },
                    y: {
                        display: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.06)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#6B7280',
                            font: { size: 10 },
                            maxTicksLimit: 4
                        }
                    }
                },
                elements: {
                    point: { radius: 0 },
                    line: {
                        tension: 0.1,
                        borderWidth: 2
                    }
                }
            };
            
            this.charts[symbol] = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            data: [],
                            borderColor: '#3B82F6',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            fill: true,
                            pointRadius: 0
                        },
                        {
                            label: 'Entry Point',
                            data: [],
                            borderColor: 'transparent',
                            backgroundColor: 'transparent',
                            pointRadius: [],
                            pointBackgroundColor: [],
                            pointBorderColor: [],
                            pointBorderWidth: 2,
                            showLine: false
                        }
                    ]
                },
                options: chartOptions
            });
        });
    }
    
    updateChartEntryMarkers(symbol) {
        const chart = this.charts[symbol];
        const priceData = this.priceData[symbol];
        if (!chart || !priceData) return;
        
        const position = this.getPositionForSymbol(symbol);
        
        if (position) {
            const entryPrice = position.entry_price;
            const direction = position.direction.toLowerCase();
            const isCall = direction === 'call';
            const color = isCall ? '#10B981' : '#EF4444';
            
            chart.options.plugins.annotation.annotations = {
                entryLine: {
                    type: 'line',
                    yMin: entryPrice,
                    yMax: entryPrice,
                    borderColor: color,
                    borderWidth: 2,
                    borderDash: [6, 4],
                    label: {
                        display: true,
                        content: `Entry: ${entryPrice.toFixed(2)} (${position.direction})`,
                        position: 'start',
                        backgroundColor: color,
                        color: '#000',
                        font: {
                            size: 10,
                            weight: 'bold'
                        },
                        padding: { top: 2, bottom: 2, left: 4, right: 4 }
                    }
                }
            };
            
            const entryDataset = chart.data.datasets[1];
            const dataLength = priceData.prices.length;
            
            entryDataset.data = new Array(dataLength).fill(null);
            entryDataset.pointRadius = new Array(dataLength).fill(0);
            entryDataset.pointBackgroundColor = new Array(dataLength).fill('transparent');
            entryDataset.pointBorderColor = new Array(dataLength).fill('transparent');
            
            if (priceData.entryIndex !== null && priceData.entryIndex < dataLength) {
                const idx = priceData.entryIndex;
                entryDataset.data[idx] = entryPrice;
                entryDataset.pointRadius[idx] = 8;
                entryDataset.pointBackgroundColor[idx] = color;
                entryDataset.pointBorderColor[idx] = '#fff';
            }
        } else {
            chart.options.plugins.annotation.annotations = {};
            
            const entryDataset = chart.data.datasets[1];
            entryDataset.data = [];
            entryDataset.pointRadius = [];
            entryDataset.pointBackgroundColor = [];
            entryDataset.pointBorderColor = [];
            
            priceData.entryIndex = null;
            priceData.entryPrice = null;
        }
        
        chart.update('none');
    }
    
    getPositionForSymbol(symbol) {
        const positions = Object.values(this.positions);
        return positions.find(pos => pos.symbol === symbol);
    }
    
    markEntryPoint(symbol, entryPrice) {
        const priceData = this.priceData[symbol];
        
        if (!priceData || priceData.prices.length === 0) {
            this.pendingEntryMarkers[symbol] = entryPrice;
            this.updateChartCardIndicator(symbol);
            return;
        }
        
        priceData.entryIndex = priceData.prices.length - 1;
        priceData.entryPrice = entryPrice;
        
        delete this.pendingEntryMarkers[symbol];
        
        this.updateChartEntryMarkers(symbol);
        this.updateChartCardIndicator(symbol);
    }
    
    processPendingEntryMarkers(symbol) {
        if (this.pendingEntryMarkers[symbol]) {
            const entryPrice = this.pendingEntryMarkers[symbol];
            this.markEntryPoint(symbol, entryPrice);
        }
    }
    
    updateChartCardIndicator(symbol) {
        const chartCard = document.querySelector(`.chart-card[data-symbol="${symbol}"]`);
        if (!chartCard) return;
        
        const existingIndicator = chartCard.querySelector('.position-indicator');
        if (existingIndicator) {
            existingIndicator.remove();
        }
        
        chartCard.classList.remove('has-position', 'put');
        
        const position = this.getPositionForSymbol(symbol);
        
        if (position) {
            const direction = position.direction.toLowerCase();
            chartCard.classList.add('has-position');
            if (direction === 'put') {
                chartCard.classList.add('put');
            }
            
            const indicator = document.createElement('div');
            indicator.className = `position-indicator ${direction}`;
            indicator.textContent = direction === 'call' ? 'CALL' : 'PUT';
            chartCard.appendChild(indicator);
        }
    }
    
    updateAllChartCardIndicators() {
        this.symbols.forEach(symbol => {
            this.updateChartCardIndicator(symbol);
        });
    }
    
    connectWebSocket() {
        this.updateConnectionStatus('connecting');
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/stream?token=${encodeURIComponent(this.authToken)}`;
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.updateConnectionStatus('connected');
                this.reconnectAttempts = 0;
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleMessage(message);
                } catch (e) {
                    console.error('Failed to parse message:', e);
                }
            };
            
            this.ws.onclose = (event) => {
                console.log('WebSocket disconnected', event.code, event.reason);
                this.updateConnectionStatus('disconnected');
                
                if (event.code === 4001) {
                    sessionStorage.removeItem('dashboard_token');
                    window.location.reload();
                    return;
                }
                
                this.scheduleReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('disconnected');
            };
        } catch (e) {
            console.error('Failed to create WebSocket:', e);
            this.updateConnectionStatus('disconnected');
            this.scheduleReconnect();
        }
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Max reconnect attempts reached');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.min(this.reconnectAttempts, 5);
        
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.connectWebSocket(), delay);
    }
    
    sendPing() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send('ping');
        }
    }
    
    handleMessage(message) {
        switch (message.type) {
            case 'snapshot':
                this.handleSnapshot(message.data);
                break;
            case 'event':
                this.handleEvent(message.channel, message.data);
                break;
            case 'pong':
                break;
            default:
                console.log('Unknown message type:', message.type);
        }
    }
    
    handleSnapshot(snapshot) {
        console.log('Received snapshot:', snapshot);
        
        if (snapshot.last_ticks) {
            Object.entries(snapshot.last_ticks).forEach(([symbol, tick]) => {
                this.updateTick(tick);
            });
        }
        
        if (snapshot.open_positions) {
            this.positions = snapshot.open_positions;
            this.renderPositions();
            
            Object.values(this.positions).forEach(pos => {
                this.markEntryPoint(pos.symbol, pos.entry_price);
            });
            
            this.updateAllChartCardIndicators();
        }
        
        if (snapshot.trade_history) {
            this.tradeHistory = snapshot.trade_history;
            this.totalTradesCount = snapshot.total_trades_count || snapshot.trade_history.length;
            this.renderTradeHistory();
        }
        
        if (snapshot.balance) {
            this.updateBalance(snapshot.balance);
        }
        
        if (snapshot.status) {
            this.updateTradingStatus(snapshot.status);
        }
    }
    
    handleEvent(channel, data) {
        switch (channel) {
            case 'tick':
                this.updateTick(data);
                break;
            case 'position':
                this.handlePositionEvent(data);
                break;
            case 'trade':
                this.handleTradeEvent(data);
                break;
            case 'balance':
                this.updateBalance(data);
                break;
            case 'status':
                this.updateTradingStatus(data);
                break;
            case 'signal':
                this.updateSignalIndicator(data);
                if (data.tick_picker) {
                    this.updateTickPicker(data.tick_picker);
                }
                if (data.strategy_mode) {
                    this.updateStrategyPanel(data.strategy_mode);
                }
                if (data.ldp_data) {
                    this.updateLDPPanel(data.ldp_data);
                }
                if (data.tick_analyzer_data) {
                    this.updateTickAnalyzerPanel(data.tick_analyzer_data);
                }
                if (data.multi_indicator_data) {
                    this.updateMultiIndicatorPanel(data.multi_indicator_data);
                }
                if (data.terminal_data) {
                    this.updateTerminalPanel(data.terminal_data);
                }
                if (data.digitpad_data) {
                    this.updateDigitPadPanel(data.digitpad_data);
                }
                if (data.amt_data) {
                    this.updateAMTPanel(data.amt_data);
                }
                if (data.sniper_data) {
                    this.updateSniperPanel(data.sniper_data);
                }
                break;
        }
    }
    
    updateStrategyPanel(strategyMode) {
        if (this.currentStrategy === strategyMode) return;
        this.currentStrategy = strategyMode;
        
        const strategyNameEl = document.getElementById('current-strategy');
        if (strategyNameEl) {
            const displayName = strategyMode.replace('_', ' ').toLowerCase()
                .split(' ')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
            strategyNameEl.textContent = displayName;
        }
        
        const panels = {
            ldp: document.getElementById('ldp-panel'),
            tick_analyzer: document.getElementById('tick-analyzer-panel'),
            terminal: document.getElementById('terminal-panel'),
            digitpad: document.getElementById('digitpad-panel'),
            amt: document.getElementById('amt-panel'),
            sniper: document.getElementById('sniper-panel'),
            multi_indicator: document.getElementById('multi-indicator-panel')
        };
        
        const tickPickerGeneric = document.getElementById('tick-picker-generic-panel');
        
        Object.values(panels).forEach(panel => {
            if (panel) panel.style.display = 'none';
        });
        
        const modeKey = strategyMode.toLowerCase();
        
        switch (modeKey) {
            case 'ldp':
                if (panels.ldp) panels.ldp.style.display = 'block';
                if (tickPickerGeneric) tickPickerGeneric.style.display = 'none';
                break;
            case 'tick_analyzer':
                if (panels.tick_analyzer) panels.tick_analyzer.style.display = 'block';
                if (tickPickerGeneric) tickPickerGeneric.style.display = 'block';
                break;
            case 'terminal':
                if (panels.terminal) panels.terminal.style.display = 'block';
                if (tickPickerGeneric) tickPickerGeneric.style.display = 'none';
                break;
            case 'digitpad':
                if (panels.digitpad) panels.digitpad.style.display = 'block';
                if (tickPickerGeneric) tickPickerGeneric.style.display = 'none';
                break;
            case 'amt':
                if (panels.amt) panels.amt.style.display = 'block';
                if (tickPickerGeneric) tickPickerGeneric.style.display = 'none';
                break;
            case 'sniper':
                if (panels.sniper) panels.sniper.style.display = 'block';
                if (tickPickerGeneric) tickPickerGeneric.style.display = 'none';
                break;
            case 'multi_indicator':
            default:
                if (panels.multi_indicator) panels.multi_indicator.style.display = 'block';
                if (tickPickerGeneric) tickPickerGeneric.style.display = 'block';
                break;
        }
    }
    
    updateTerminalPanel(data) {
        if (!data) return;
        
        if (data.probability !== undefined) {
            const probEl = document.getElementById('terminal-probability');
            if (probEl) {
                probEl.textContent = `${(data.probability * 100).toFixed(0)}%`;
                probEl.classList.remove('bullish', 'bearish');
                if (data.probability >= 0.8) probEl.classList.add('bullish');
            }
        }
        
        if (data.direction) {
            const dirEl = document.getElementById('terminal-direction');
            if (dirEl) {
                dirEl.textContent = data.direction.toUpperCase();
                dirEl.classList.remove('bullish', 'bearish');
                if (data.direction.toLowerCase() === 'call') dirEl.classList.add('bullish');
                else if (data.direction.toLowerCase() === 'put') dirEl.classList.add('bearish');
            }
        }
        
        if (data.adx !== undefined) {
            const adxEl = document.getElementById('terminal-adx');
            if (adxEl) adxEl.textContent = data.adx.toFixed(1);
        }
        
        const indicators = ['rsi', 'ema', 'macd', 'stoch'];
        indicators.forEach(ind => {
            if (data[ind] !== undefined) {
                const fillEl = document.getElementById(`terminal-${ind}-fill`);
                const signalEl = document.getElementById(`terminal-${ind}-signal`);
                
                if (fillEl) {
                    const value = typeof data[ind] === 'object' ? data[ind].value : data[ind];
                    fillEl.style.width = `${Math.min(100, Math.max(0, value))}%`;
                }
                
                if (signalEl && data[ind + '_signal']) {
                    signalEl.textContent = data[ind + '_signal'];
                    signalEl.classList.remove('bullish', 'bearish', 'neutral');
                    signalEl.classList.add(data[ind + '_signal'].toLowerCase());
                }
            }
        });
        
        if (data.console_log) {
            const consoleEl = document.getElementById('terminal-console');
            if (consoleEl) {
                const line = document.createElement('div');
                line.className = 'console-line';
                line.textContent = data.console_log;
                consoleEl.appendChild(line);
                consoleEl.scrollTop = consoleEl.scrollHeight;
                
                while (consoleEl.children.length > 20) {
                    consoleEl.removeChild(consoleEl.firstChild);
                }
            }
        }
    }
    
    updateDigitPadPanel(data) {
        if (!data) return;
        
        if (data.digit_frequencies) {
            const frequencies = data.digit_frequencies;
            const maxFreq = Math.max(...Object.values(frequencies));
            const minFreq = Math.min(...Object.values(frequencies));
            
            for (let i = 0; i < 10; i++) {
                const pctEl = document.getElementById(`dp-pct-${i}`);
                const cell = document.querySelector(`.digitpad-cell[data-digit="${i}"]`);
                const freq = frequencies[i] || 0;
                
                if (pctEl) pctEl.textContent = `${freq.toFixed(1)}%`;
                
                if (cell) {
                    cell.classList.remove('hot', 'cold');
                    if (freq >= maxFreq - 1) cell.classList.add('hot');
                    else if (freq <= minFreq + 1) cell.classList.add('cold');
                }
            }
        }
        
        if (data.even_percentage !== undefined) {
            const evenPctEl = document.getElementById('dp-even-pct');
            if (evenPctEl) evenPctEl.textContent = `${data.even_percentage.toFixed(1)}%`;
        }
        
        if (data.odd_percentage !== undefined) {
            const oddPctEl = document.getElementById('dp-odd-pct');
            if (oddPctEl) oddPctEl.textContent = `${data.odd_percentage.toFixed(1)}%`;
        }
        
        if (data.differ_percentage !== undefined) {
            const differFill = document.getElementById('dp-differ-fill');
            const differValue = document.getElementById('dp-differ-value');
            if (differFill) differFill.style.width = `${data.differ_percentage}%`;
            if (differValue) differValue.textContent = `${data.differ_percentage.toFixed(0)}%`;
        }
        
        if (data.differ_min !== undefined) {
            const minEl = document.getElementById('dp-differ-min');
            if (minEl) minEl.textContent = `${data.differ_min.toFixed(0)}%`;
        }
        
        if (data.differ_max !== undefined) {
            const maxEl = document.getElementById('dp-differ-max');
            if (maxEl) maxEl.textContent = `${data.differ_max.toFixed(0)}%`;
        }
        
        if (data.signal_text) {
            const signalIndicator = document.getElementById('dp-signal-indicator');
            const signalText = signalIndicator?.querySelector('.dp-signal-text');
            if (signalText) signalText.textContent = data.signal_text;
            
            if (signalIndicator) {
                signalIndicator.classList.remove('strong-buy', 'strong-sell', 'not-good');
                if (data.signal_type === 'strong_buy') signalIndicator.classList.add('strong-buy');
                else if (data.signal_type === 'strong_sell') signalIndicator.classList.add('strong-sell');
                else if (data.signal_type === 'not_good') signalIndicator.classList.add('not-good');
            }
        }
    }
    
    updateAMTPanel(data) {
        if (!data) return;
        
        if (data.growth_rate !== undefined) {
            const growthEl = document.getElementById('amt-growth-rate');
            if (growthEl) growthEl.textContent = `${data.growth_rate}%`;
        }
        
        if (data.current_pnl !== undefined) {
            const pnlEl = document.getElementById('amt-current-pnl');
            if (pnlEl) {
                const pnl = data.current_pnl;
                pnlEl.textContent = `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`;
                pnlEl.classList.remove('positive', 'negative');
                pnlEl.classList.add(pnl >= 0 ? 'positive' : 'negative');
            }
        }
        
        if (data.tick_count !== undefined) {
            const tickEl = document.getElementById('amt-tick-count');
            if (tickEl) tickEl.textContent = data.tick_count;
        }
        
        if (data.take_profit !== undefined) {
            const tpEl = document.getElementById('amt-tp-value');
            if (tpEl) tpEl.textContent = `$${data.take_profit.toFixed(2)}`;
        }
        
        if (data.stop_loss !== undefined) {
            const slEl = document.getElementById('amt-sl-value');
            if (slEl) slEl.textContent = `$${data.stop_loss.toFixed(2)}`;
        }
        
        if (data.progress !== undefined) {
            const progressFill = document.getElementById('amt-progress-fill');
            const progressLabel = document.getElementById('amt-progress-label');
            
            if (progressFill) {
                const width = Math.abs(data.progress) * 50;
                progressFill.style.width = `${width}%`;
                progressFill.style.left = data.progress >= 0 ? '50%' : `${50 - width}%`;
                progressFill.style.background = data.progress >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
            }
            
            if (progressLabel) progressLabel.textContent = `${(data.progress * 100).toFixed(0)}%`;
        }
        
        if (data.status) {
            const statusEl = document.getElementById('amt-status');
            const statusText = statusEl?.querySelector('.amt-status-text');
            if (statusText) statusText.textContent = data.status;
        }
    }
    
    updateSniperPanel(data) {
        if (!data) return;
        
        if (data.signal) {
            const signalEl = document.getElementById('sniper-signal');
            if (signalEl) {
                signalEl.textContent = data.signal.toUpperCase();
                signalEl.classList.remove('bullish', 'bearish');
                if (data.signal.toLowerCase() === 'buy' || data.signal.toLowerCase() === 'call') {
                    signalEl.classList.add('bullish');
                } else if (data.signal.toLowerCase() === 'sell' || data.signal.toLowerCase() === 'put') {
                    signalEl.classList.add('bearish');
                }
            }
        }
        
        if (data.winrate !== undefined) {
            const winrateEl = document.getElementById('sniper-winrate');
            if (winrateEl) winrateEl.textContent = `${data.winrate.toFixed(1)}%`;
        }
        
        if (data.wins !== undefined && data.losses !== undefined) {
            const sessionEl = document.getElementById('sniper-session');
            if (sessionEl) sessionEl.textContent = `${data.wins}W / ${data.losses}L`;
        }
        
        if (data.confidence !== undefined) {
            const confidenceFill = document.getElementById('sniper-confidence-fill');
            const confidenceValue = document.getElementById('sniper-confidence-value');
            
            if (confidenceFill) confidenceFill.style.width = `${data.confidence * 100}%`;
            if (confidenceValue) confidenceValue.textContent = `${(data.confidence * 100).toFixed(0)}%`;
        }
        
        if (data.console_log) {
            const consoleEl = document.getElementById('sniper-console');
            if (consoleEl) {
                const line = document.createElement('div');
                line.className = 'console-line';
                line.textContent = data.console_log;
                consoleEl.appendChild(line);
                consoleEl.scrollTop = consoleEl.scrollHeight;
                
                while (consoleEl.children.length > 20) {
                    consoleEl.removeChild(consoleEl.firstChild);
                }
            }
        }
    }
    
    updateLDPPanel(data) {
        if (!data) return;
        
        if (data.digit_frequencies) {
            const heatmap = document.getElementById('digit-heatmap');
            if (heatmap) {
                const cells = heatmap.querySelectorAll('.digit-cell');
                const frequencies = data.digit_frequencies;
                const maxFreq = Math.max(...Object.values(frequencies));
                const minFreq = Math.min(...Object.values(frequencies));
                
                cells.forEach(cell => {
                    const digit = cell.dataset.digit;
                    const freq = frequencies[digit] || 0;
                    const freqEl = cell.querySelector('.digit-freq');
                    if (freqEl) freqEl.textContent = `${freq.toFixed(1)}%`;
                    
                    cell.classList.remove('hot', 'cold');
                    if (freq >= maxFreq - 1) {
                        cell.classList.add('hot');
                    } else if (freq <= minFreq + 1) {
                        cell.classList.add('cold');
                    }
                });
            }
        }
        
        if (data.hot_digits) {
            const hotDigitsEl = document.getElementById('hot-digits');
            if (hotDigitsEl) {
                hotDigitsEl.textContent = data.hot_digits.join(', ');
            }
        }
        
        if (data.cold_digits) {
            const coldDigitsEl = document.getElementById('cold-digits');
            if (coldDigitsEl) {
                coldDigitsEl.textContent = data.cold_digits.join(', ');
            }
        }
        
        if (data.zones) {
            const lowZoneFill = document.getElementById('low-zone-fill');
            const highZoneFill = document.getElementById('high-zone-fill');
            const lowZonePct = document.getElementById('low-zone-pct');
            const highZonePct = document.getElementById('high-zone-pct');
            
            const lowPct = data.zones.low || 50;
            const highPct = data.zones.high || 50;
            
            if (lowZoneFill) lowZoneFill.style.width = `${lowPct}%`;
            if (highZoneFill) highZoneFill.style.width = `${highPct}%`;
            if (lowZonePct) lowZonePct.textContent = `${lowPct.toFixed(1)}%`;
            if (highZonePct) highZonePct.textContent = `${highPct.toFixed(1)}%`;
        }
        
        if (data.signal_type && data.signal_digit !== undefined) {
            const ldpSignal = document.getElementById('ldp-signal');
            if (ldpSignal) {
                const typeEl = ldpSignal.querySelector('.ldp-signal-type');
                const digitEl = ldpSignal.querySelector('.ldp-signal-digit');
                if (typeEl) typeEl.textContent = data.signal_type;
                if (digitEl) digitEl.textContent = data.signal_digit;
            }
        }
    }
    
    updateTickAnalyzerPanel(data) {
        if (!data) return;
        
        const streakCounter = document.getElementById('streak-counter');
        const streakDirection = document.getElementById('streak-direction');
        const streakCount = document.getElementById('streak-count');
        
        if (data.streak !== undefined) {
            const direction = data.streak >= 0 ? 'UP' : 'DOWN';
            const count = Math.abs(data.streak);
            
            if (streakCounter) {
                streakCounter.classList.remove('up', 'down');
                streakCounter.classList.add(direction.toLowerCase());
            }
            if (streakDirection) streakDirection.textContent = direction;
            if (streakCount) streakCount.textContent = count;
        }
        
        if (data.momentum !== undefined) {
            const momentumIndicator = document.getElementById('momentum-indicator');
            const momentumValue = document.getElementById('momentum-value');
            
            const normalizedMomentum = Math.max(-1, Math.min(1, data.momentum));
            const leftPercent = ((normalizedMomentum + 1) / 2) * 100;
            
            if (momentumIndicator) momentumIndicator.style.left = `${leftPercent}%`;
            if (momentumValue) momentumValue.textContent = data.momentum.toFixed(2);
        }
        
        if (data.patterns) {
            const patternBadges = document.getElementById('pattern-badges');
            if (patternBadges) {
                if (data.patterns.length === 0) {
                    patternBadges.innerHTML = '<span class="pattern-badge none">No pattern</span>';
                } else {
                    patternBadges.innerHTML = data.patterns.map(p => {
                        const badgeClass = p.type === 'bullish' ? 'bullish' : p.type === 'bearish' ? 'bearish' : '';
                        return `<span class="pattern-badge ${badgeClass}">${p.name}</span>`;
                    }).join('');
                }
            }
        }
    }
    
    updateMultiIndicatorPanel(data) {
        if (!data) return;
        
        if (data.rsi !== undefined) {
            const rsiMarker = document.getElementById('rsi-marker');
            const rsiValue = document.getElementById('rsi-value');
            
            if (rsiMarker) rsiMarker.style.left = `${data.rsi}%`;
            if (rsiValue) rsiValue.textContent = data.rsi.toFixed(2);
        }
        
        if (data.trend) {
            const trendIndicator = document.getElementById('trend-indicator');
            if (trendIndicator) {
                const arrow = trendIndicator.querySelector('.trend-arrow');
                const text = trendIndicator.querySelector('.trend-text');
                
                trendIndicator.classList.remove('up', 'down', 'neutral');
                
                if (data.trend === 'UP' || data.trend === 'BULLISH') {
                    trendIndicator.classList.add('up');
                    if (arrow) arrow.textContent = '↑';
                    if (text) text.textContent = 'BULLISH';
                } else if (data.trend === 'DOWN' || data.trend === 'BEARISH') {
                    trendIndicator.classList.add('down');
                    if (arrow) arrow.textContent = '↓';
                    if (text) text.textContent = 'BEARISH';
                } else {
                    trendIndicator.classList.add('neutral');
                    if (arrow) arrow.textContent = '→';
                    if (text) text.textContent = 'NEUTRAL';
                }
            }
        }
        
        if (data.macd) {
            const macdSignal = document.getElementById('macd-signal');
            if (macdSignal) {
                const histogram = macdSignal.querySelector('.macd-histogram');
                const text = macdSignal.querySelector('.macd-text');
                
                if (histogram) {
                    histogram.classList.remove('bullish', 'bearish', 'neutral');
                    if (data.macd === 'BULLISH') {
                        histogram.classList.add('bullish');
                        histogram.textContent = '▲';
                    } else if (data.macd === 'BEARISH') {
                        histogram.classList.add('bearish');
                        histogram.textContent = '▼';
                    } else {
                        histogram.classList.add('neutral');
                        histogram.textContent = '▬';
                    }
                }
                if (text) text.textContent = data.macd;
            }
        }
        
        if (data.confluence !== undefined) {
            const confluenceValue = document.querySelector('#confluence-score .confluence-value');
            const confluenceFill = document.getElementById('confluence-fill');
            
            if (confluenceValue) confluenceValue.textContent = data.confluence;
            if (confluenceFill) confluenceFill.style.width = `${(data.confluence / 5) * 100}%`;
        }
    }
    
    updateTickPicker(data) {
        this.tickPickerData = data;
        
        const windowSizeEl = document.getElementById('tick-window-size');
        const upCountEl = document.getElementById('tick-up-count');
        const upPctEl = document.getElementById('tick-up-pct');
        const downCountEl = document.getElementById('tick-down-count');
        const downPctEl = document.getElementById('tick-down-pct');
        const signalEl = document.getElementById('tick-picker-signal');
        
        if (windowSizeEl) {
            windowSizeEl.textContent = `Window: ${data.window_size || 50} ticks`;
        }
        
        if (upCountEl) {
            upCountEl.textContent = data.tick_up_count ?? 0;
        }
        
        if (upPctEl) {
            const upPct = typeof data.up_percentage === 'number' ? data.up_percentage : 50;
            upPctEl.textContent = `${upPct.toFixed(1)}%`;
        }
        
        if (downCountEl) {
            downCountEl.textContent = data.tick_down_count ?? 0;
        }
        
        if (downPctEl) {
            const downPct = typeof data.down_percentage === 'number' ? data.down_percentage : 50;
            downPctEl.textContent = `${downPct.toFixed(1)}%`;
        }
        
        if (signalEl) {
            const signal = data.signal_direction || 'WAIT';
            signalEl.innerHTML = `<span>${signal}</span>`;
            signalEl.classList.remove('call', 'put', 'wait');
            
            if (signal === 'CALL') {
                signalEl.classList.add('call');
            } else if (signal === 'PUT') {
                signalEl.classList.add('put');
            } else {
                signalEl.classList.add('wait');
            }
        }
    }
    
    updateSignalIndicator(data) {
        const signalEl = document.getElementById('signal');
        const signalIcon = signalEl?.querySelector('.signal-icon');
        const signalText = signalEl?.querySelector('.signal-text');
        const trendDetails = document.getElementById('trend-details');
        
        if (!signalEl || !signalIcon || !signalText) return;
        
        const signalType = (data.signal || data.type || 'neutral').toLowerCase();
        this.currentSignal = signalType;
        
        signalEl.classList.remove('neutral', 'buy', 'sell');
        signalEl.classList.add(signalType);
        
        switch (signalType) {
            case 'buy':
            case 'call':
                signalEl.classList.remove('neutral', 'sell');
                signalEl.classList.add('buy');
                signalIcon.textContent = '📈';
                signalText.textContent = 'BUY';
                break;
            case 'sell':
            case 'put':
                signalEl.classList.remove('neutral', 'buy');
                signalEl.classList.add('sell');
                signalIcon.textContent = '📉';
                signalText.textContent = 'SELL';
                break;
            default:
                signalEl.classList.remove('buy', 'sell');
                signalEl.classList.add('neutral');
                signalIcon.textContent = '⏳';
                signalText.textContent = 'Analyzing...';
        }
        
        if (trendDetails) {
            trendDetails.classList.remove('uptrend', 'downtrend');
            
            if (data.trend) {
                trendDetails.textContent = data.trend;
                if (data.trend.toLowerCase().includes('up') || data.trend.toLowerCase().includes('bullish')) {
                    trendDetails.classList.add('uptrend');
                } else if (data.trend.toLowerCase().includes('down') || data.trend.toLowerCase().includes('bearish')) {
                    trendDetails.classList.add('downtrend');
                }
            } else if (data.symbol) {
                const trendText = signalType === 'buy' || signalType === 'call' 
                    ? `Uptrend detected on ${data.symbol}`
                    : signalType === 'sell' || signalType === 'put'
                    ? `Downtrend detected on ${data.symbol}`
                    : 'No active trend detected';
                trendDetails.textContent = trendText;
                
                if (signalType === 'buy' || signalType === 'call') {
                    trendDetails.classList.add('uptrend');
                } else if (signalType === 'sell' || signalType === 'put') {
                    trendDetails.classList.add('downtrend');
                }
            } else {
                trendDetails.textContent = 'No active trend detected';
            }
        }
    }
    
    updateTickCounter(symbol, price) {
        this.tickCount++;
        this.lastTickPrice = price;
        
        const tickCounterEl = document.getElementById('tick-counter');
        if (tickCounterEl) {
            tickCounterEl.textContent = `Ticks: ${this.tickCount} | Last: ${price.toFixed(2)}`;
        }
    }
    
    updateTick(tick) {
        const symbol = tick.symbol;
        if (!this.priceData[symbol]) return;
        
        const data = this.priceData[symbol];
        const price = tick.price;
        const time = new Date(tick.timestamp || Date.now()).toLocaleTimeString();
        
        this.updateTickCounter(symbol, price);
        
        data.labels.push(time);
        data.prices.push(price);
        
        const maxPoints = 60;
        let shifted = false;
        if (data.labels.length > maxPoints) {
            data.labels.shift();
            data.prices.shift();
            shifted = true;
            
            if (data.entryIndex !== null) {
                data.entryIndex--;
                if (data.entryIndex < 0) {
                    data.entryIndex = null;
                }
            }
        }
        
        if (this.charts[symbol]) {
            this.charts[symbol].data.labels = data.labels;
            this.charts[symbol].data.datasets[0].data = data.prices;
            
            this.processPendingEntryMarkers(symbol);
            
            const position = this.getPositionForSymbol(symbol);
            if (position) {
                this.updateChartEntryMarkers(symbol);
            } else {
                this.charts[symbol].update('none');
            }
        }
        
        const priceEl = document.getElementById(`price-${symbol}`);
        if (priceEl) {
            const prevPrice = parseFloat(priceEl.textContent) || 0;
            priceEl.textContent = price.toFixed(2);
            priceEl.classList.remove('up', 'down');
            if (price > prevPrice) {
                priceEl.classList.add('up');
            } else if (price < prevPrice) {
                priceEl.classList.add('down');
            }
        }
    }
    
    handlePositionEvent(data) {
        switch (data.type) {
            case 'position_open':
                this.positions[data.contract_id] = data;
                this.markEntryPoint(data.symbol, data.entry_price);
                break;
            case 'position_update':
                if (this.positions[data.contract_id]) {
                    Object.assign(this.positions[data.contract_id], {
                        current_price: data.current_price,
                        pnl: data.pnl,
                        duration: data.duration
                    });
                }
                break;
            case 'position_close':
                const closedSymbol = this.positions[data.contract_id]?.symbol;
                delete this.positions[data.contract_id];
                if (closedSymbol) {
                    this.updateChartEntryMarkers(closedSymbol);
                    this.updateChartCardIndicator(closedSymbol);
                }
                break;
            case 'positions_reset':
                this.positions = {};
                this.symbols.forEach(symbol => {
                    if (this.priceData[symbol]) {
                        this.priceData[symbol].entryIndex = null;
                        this.priceData[symbol].entryPrice = null;
                    }
                    this.updateChartEntryMarkers(symbol);
                    this.updateChartCardIndicator(symbol);
                });
                console.log('Positions reset:', data.reason);
                break;
        }
        this.renderPositions();
    }
    
    handleTradeEvent(data) {
        if (data.type === 'trade_history') {
            this.tradeHistory.push(data);
            if (data.total_trades_count !== undefined) {
                this.totalTradesCount = data.total_trades_count;
            } else {
                this.totalTradesCount++;
            }
            if (this.tradeHistory.length > 200) {
                this.tradeHistory.shift();
            }
            this.renderTradeHistory();
        }
    }
    
    renderPositions() {
        const container = document.getElementById('positions-container');
        if (!container) return;
        
        const positionsList = Object.values(this.positions);
        
        if (positionsList.length === 0) {
            container.innerHTML = '<div class="no-positions">No active positions</div>';
            return;
        }
        
        container.innerHTML = positionsList.map(pos => {
            const direction = pos.direction.toLowerCase();
            const pnl = pos.pnl || 0;
            const pnlClass = pnl >= 0 ? 'profit' : 'loss';
            const martingaleBadge = pos.martingale_level > 0 
                ? `<span class="martingale-badge">M${pos.martingale_level}</span>` 
                : '';
            
            return `
                <div class="position-card ${direction}">
                    <div class="position-info">
                        <span class="position-symbol">${pos.symbol}</span>
                        <span class="position-direction ${direction}">${pos.direction}${martingaleBadge}</span>
                    </div>
                    <div class="position-stake">
                        <span class="position-label">Stake</span>
                        <span class="position-value">$${pos.stake.toFixed(2)}</span>
                    </div>
                    <div class="position-entry">
                        <span class="position-label">Entry</span>
                        <span class="position-value">${pos.entry_price.toFixed(2)}</span>
                    </div>
                    <div class="position-pnl">
                        <span class="position-label">P/L</span>
                        <span class="position-value ${pnlClass}">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</span>
                    </div>
                </div>
            `;
        }).join('');
    }
    
    renderTradeHistory() {
        const tbody = document.getElementById('history-tbody');
        if (!tbody) return;
        
        const recentTrades = [...this.tradeHistory].reverse().slice(0, 50);
        
        tbody.innerHTML = recentTrades.map(trade => {
            const time = new Date(trade.timestamp).toLocaleString();
            const direction = trade.direction.toLowerCase();
            const result = trade.result.toLowerCase();
            const profit = trade.profit;
            const profitClass = profit >= 0 ? 'positive' : 'negative';
            
            return `
                <tr>
                    <td>${time}</td>
                    <td>${trade.symbol}</td>
                    <td><span class="direction-badge ${direction}">${trade.direction}</span></td>
                    <td>$${trade.stake.toFixed(2)}</td>
                    <td><span class="result-badge ${result}">${result}</span></td>
                    <td class="profit-cell ${profitClass}">${profit >= 0 ? '+' : ''}$${profit.toFixed(2)}</td>
                </tr>
            `;
        }).join('');
        
        this.updateStats();
    }
    
    updateStats() {
        const totalTrades = this.totalTradesCount;
        const wins = this.tradeHistory.filter(t => t.result.toLowerCase() === 'win').length;
        const recentCount = this.tradeHistory.length;
        const winRate = recentCount > 0 ? ((wins / recentCount) * 100).toFixed(1) : 0;
        const totalPnl = this.tradeHistory.reduce((sum, t) => sum + (t.profit || 0), 0);
        
        const totalEl = document.getElementById('total-trades');
        const winRateEl = document.getElementById('win-rate');
        const pnlEl = document.getElementById('total-pnl');
        
        if (totalEl) totalEl.textContent = totalTrades;
        if (winRateEl) winRateEl.textContent = `${winRate}%`;
        if (pnlEl) {
            pnlEl.textContent = `${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`;
            pnlEl.classList.remove('positive', 'negative');
            pnlEl.classList.add(totalPnl >= 0 ? 'positive' : 'negative');
        }
    }
    
    updateBalance(balance) {
        const balanceEl = document.querySelector('.balance-value');
        if (balanceEl && balance) {
            balanceEl.textContent = `${balance.currency || 'USD'} ${balance.balance.toFixed(2)}`;
        }
    }
    
    updateTradingStatus(status) {
        const tradingEl = document.querySelector('.trading-indicator');
        if (tradingEl && status) {
            const isTrading = status.is_trading;
            const accountType = status.account_type || 'unknown';
            tradingEl.textContent = `Trading: ${isTrading ? 'Active' : 'Stopped'} (${accountType})`;
            tradingEl.classList.remove('active', 'inactive');
            tradingEl.classList.add(isTrading ? 'active' : 'inactive');
        }
    }
    
    updateConnectionStatus(status) {
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-text');
        
        if (statusDot) {
            statusDot.classList.remove('connected', 'disconnected', 'connecting');
            statusDot.classList.add(status);
        }
        
        if (statusText) {
            const texts = {
                connected: 'Connected',
                disconnected: 'Disconnected',
                connecting: 'Connecting...'
            };
            statusText.textContent = texts[status] || status;
        }
    }
    
    async fetchInitialData() {
        const headers = { 'Authorization': `Bearer ${this.authToken}` };
        
        try {
            const [summaryRes, historyRes] = await Promise.all([
                fetch('/api/summary', { headers }),
                fetch('/api/history?limit=50', { headers })
            ]);
            
            if (summaryRes.status === 401 || historyRes.status === 401) {
                sessionStorage.removeItem('dashboard_token');
                window.location.reload();
                return;
            }
            
            if (summaryRes.ok) {
                const summary = await summaryRes.json();
                if (summary.success && summary.data) {
                    if (summary.data.balance) {
                        this.updateBalance(summary.data.balance);
                    }
                    if (summary.data.status) {
                        this.updateTradingStatus(summary.data.status);
                    }
                    if (summary.data.open_positions) {
                        this.positions = summary.data.open_positions;
                        this.renderPositions();
                    }
                }
            }
            
            if (historyRes.ok) {
                const history = await historyRes.json();
                if (history.success && history.data && history.data.trades) {
                    this.tradeHistory = history.data.trades;
                    this.renderTradeHistory();
                }
            }
        } catch (e) {
            console.error('Failed to fetch initial data:', e);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new TradingDashboard();
});
