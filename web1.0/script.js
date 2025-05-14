document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded and parsed");

    // --- Configuration ---
    let API_BASE_URL = ''; // 将根据用户配置的IP和端口动态设置
    const API_ENDPOINTS = {
        // --- GET Endpoints ---
        getConfig: `/api/config`,
        getStatus: `/api/status`,
        getHoldings: `/api/holdings`,
        getLogs: `/api/logs`,
        getPositionsAll: `/api/positions-all`, // 新增：获取所有持仓数据
        // --- POST Endpoints ---
        saveConfig: `/api/config/save`,
        checkConnection: '/api/connection/status',
        startMonitor: `/api/monitor/start`,
        stopMonitor: `/api/monitor/stop`,
        clearLogs: `/api/logs/clear`,
        clearCurrentData: `/api/data/clear_current`, 
        clearBuySellData: `/api/data/clear_buysell`, 
        importSavedData: `/api/data/import`,
        initHoldings: `/api/holdings/init`,
        executeBuy: `/api/actions/execute_buy`,
        updateHoldingParams: `/api/holdings/update`
    };

    const POLLING_INTERVAL = 5000; // 每2秒更新一次数据
    let pollingIntervalId = null;
    let isMonitoring = false; // 监控状态

    // --- DOM Element References ---
    const elements = {
        messageArea: document.getElementById('messageArea'),
        // 配置表单元素
        singleBuyAmount: document.getElementById('singleBuyAmount'),
        firstProfitSell: document.getElementById('firstProfitSell'),
        firstProfitSellEnabled: document.getElementById('firstProfitSellEnabled'),
        stockGainSellPencent: document.getElementById('stockGainSellPencent'),
        firstProfitSellPencent: document.getElementById('firstProfitSellPencent'),
        allowBuy: document.getElementById('allowBuy'),
        allowSell: document.getElementById('allowSell'),
        stopLossBuy: document.getElementById('stopLossBuy'),
        stopLossBuyEnabled: document.getElementById('stopLossBuyEnabled'),
        stockStopLoss: document.getElementById('stockStopLoss'),
        StopLossEnabled: document.getElementById('StopLossEnabled'),
        singleStockMaxPosition: document.getElementById('singleStockMaxPosition'),
        totalMaxPosition: document.getElementById('totalMaxPosition'),
        connectPort: document.getElementById('connectPort'),
        totalAccounts: document.getElementById('totalAccounts'),
        globalAllowBuySell: document.getElementById('globalAllowBuySell'),
        // 账户信息和状态
        accountId: document.getElementById('accountId'),
        availableBalance: document.getElementById('availableBalance'),
        maxHoldingValue: document.getElementById('maxHoldingValue'),
        totalAssets: document.getElementById('totalAssets'),
        lastUpdateTimestamp: document.getElementById('last-update-timestamp'),
        statusIndicator: document.getElementById('statusIndicator'),
        // 按钮
        toggleMonitorBtn: document.getElementById('toggleMonitorBtn'),
        saveConfigBtn: document.getElementById('saveConfigBtn'),
        clearLogBtn: document.getElementById('clearLogBtn'),
        clearCurrentDataBtn: document.getElementById('clearCurrentDataBtn'),
        clearBuySellDataBtn: document.getElementById('clearBuySellDataBtn'),
        importDataBtn: document.getElementById('importDataBtn'),
        initHoldingsBtn: document.getElementById('initHoldingsBtn'),
        executeBuyBtn: document.getElementById('executeBuyBtn'),
        // 买入设置
        buyStrategy: document.getElementById('buyStrategy'),
        buyQuantity: document.getElementById('buyQuantity'),
        // 持仓表格
        holdingsTableBody: document.getElementById('holdingsTableBody'),
        selectAllHoldings: document.getElementById('selectAllHoldings'),
        holdingsLoading: document.getElementById('holdingsLoading'),
        holdingsError: document.getElementById('holdingsError'),
        // 订单日志
        orderLog: document.getElementById('orderLog'),
        logLoading: document.getElementById('logLoading'),

        logError: document.getElementById('logError'),
    };

    // --- 工具函数 ---
    function showMessage(text, type = 'info', duration = 5000) {
        elements.messageArea.innerHTML = ''; 
        const messageDiv = document.createElement('div');
        messageDiv.textContent = text;
        messageDiv.className = `status-message ${type}`;
        elements.messageArea.appendChild(messageDiv);

        if (duration > 0) {
            setTimeout(() => {
                if (messageDiv.parentNode === elements.messageArea) {
                    elements.messageArea.removeChild(messageDiv);
                }
            }, duration);
        }
    }

    // 更新API基础URL
    function updateApiBaseUrl() {
        const ip = elements.totalAccounts.value || '127.0.0.1';
        const port = elements.connectPort.value || '5000';
        API_BASE_URL = `http://${ip}:${port}`;
        
        // 更新所有API端点
        for (let key in API_ENDPOINTS) {
            API_ENDPOINTS[key] = `${API_BASE_URL}${API_ENDPOINTS[key]}`;
        }
        console.log("API Base URL updated:", API_BASE_URL);
    }

    async function apiRequest(url, options = {}) {
        console.log(`API Request: ${options.method || 'GET'} ${url}`, options.body ? JSON.parse(options.body) : '');
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    ...options.headers,
                },
                ...options,
            });

            if (!response.ok) {
                let errorMsg = `HTTP error! Status: ${response.status}`;
                try {
                    const errData = await response.json();
                    errorMsg += ` - ${errData.message || JSON.stringify(errData)}`;
                } catch (e) { /* 忽略非JSON响应错误 */ }
                throw new Error(errorMsg);
            }

            const data = await response.json();
            console.log(`API Response: ${options.method || 'GET'} ${url}`, data);
            return data;
        } catch (error) {
            console.error(`API Error: ${options.method || 'GET'} ${url}`, error);
            showMessage(`请求失败: ${error.message}`, 'error');
            throw error;
        }
    }

    // --- UI更新函数 ---
    function updateConfigForm(config) {
        console.log("Updating config form:", config);
        if (!config) return;
        elements.singleBuyAmount.value = config.singleBuyAmount ?? '35000';
        elements.firstProfitSell.value = config.firstProfitSell ?? '5.00';
        elements.firstProfitSellEnabled.checked = config.firstProfitSellEnabled ?? true;
        elements.stockGainSellPencent.value = config.stockGainSellPencent ?? '60.00';
        elements.firstProfitSellPencent.checked = config.firstProfitSellPencent ?? true;
        elements.allowBuy.checked = config.allowBuy ?? true;
        elements.allowSell.checked = config.allowSell ?? true;
        elements.stopLossBuy.value = config.stopLossBuy ?? '5.00';
        elements.stopLossBuyEnabled.checked = config.stopLossBuyEnabled ?? true;
        elements.stockStopLoss.value = config.stockStopLoss ?? '7.00';
        elements.StopLossEnabled.checked = config.StopLossEnabled ?? true;
        elements.singleStockMaxPosition.value = config.singleStockMaxPosition ?? '70000';
        elements.totalMaxPosition.value = config.totalMaxPosition ?? '400000';
        elements.connectPort.value = config.connectPort ?? '5000';
        elements.totalAccounts.value = config.totalAccounts ?? '127.0.0.1';
        elements.globalAllowBuySell.checked = config.globalAllowBuySell ?? true;
    }

    function updateStatusDisplay(statusData) {
        console.log("Updating status display:", statusData);
        if (!statusData) return;

        // 账户信息
        elements.accountId.textContent = statusData.account?.id ?? '--';
        elements.availableBalance.textContent = statusData.account?.availableBalance?.toFixed(2) ?? '--';
        elements.maxHoldingValue.textContent = statusData.account?.maxHoldingValue?.toFixed(2) ?? '--';
        elements.totalAssets.textContent = statusData.account?.totalAssets?.toFixed(2) ?? '--';
        elements.lastUpdateTimestamp.textContent = statusData.account?.timestamp ?? new Date().toLocaleString('zh-CN');
    
        // 监控状态
        isMonitoring = statusData.isMonitoring ?? false;
        if (isMonitoring) {
            elements.statusIndicator.textContent = '运行中';
            elements.statusIndicator.className = 'text-lg font-bold text-green-600';
            elements.toggleMonitorBtn.textContent = '停止执行监控';
            elements.toggleMonitorBtn.classList.remove('bg-blue-600', 'hover:bg-blue-700');
            elements.toggleMonitorBtn.classList.add('bg-red-600', 'hover:bg-red-700');
            startPolling(); // 开始轮询数据
        } else {
            elements.statusIndicator.textContent = '未运行';
            elements.statusIndicator.className = 'text-lg font-bold text-red-600';
            elements.toggleMonitorBtn.textContent = '开始执行监控';
            elements.toggleMonitorBtn.classList.remove('bg-red-600', 'hover:bg-red-700');
            elements.toggleMonitorBtn.classList.add('bg-blue-600', 'hover:bg-blue-700');
            stopPolling(); // 停止轮询数据
        }

    }

    // 更新持仓表格 - 适配新的字段对应关系
    function updateHoldingsTable(holdings) {
        console.log("Updating holdings table:", holdings);
        elements.holdingsTableBody.innerHTML = ''; // 清空现有行
        elements.holdingsLoading.classList.add('hidden');
        elements.holdingsError.classList.add('hidden');

        if (!Array.isArray(holdings) || holdings.length === 0) {
            elements.holdingsTableBody.innerHTML = '<tr><td colspan="15" class="text-center p-4 text-gray-500">无持仓数据</td></tr>';
            return;
        }

        holdings.forEach(stock => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50 even:bg-gray-100';
            
            // 根据新的字段对应关系创建表格行
            row.innerHTML = `
                <td class="border p-2"><input type="checkbox" class="holding-checkbox" data-id="${stock.id || stock.stock_code}"></td>
                <td class="border p-2">${stock.stock_code || '--'}</td>
                <td class="border p-2">${stock.stock_name || stock.name || '--'}</td>                
                <td class="border p-2 ${parseFloat(stock.change_percentage || 0) >= 0 ? 'text-red-600' : 'text-green-600'}">${parseFloat(stock.change_percentage || 0).toFixed(2)}%</td>
                <td class="border p-2">${parseFloat(stock.current_price || 0).toFixed(2)}</td>
                <td class="border p-2">${parseFloat(stock.cost_price || 0).toFixed(2)}</td>
                <td class="border p-2 ${parseFloat(stock.profit_ratio || 0) >= 0 ? 'text-red-600' : 'text-green-600'}">${parseFloat(stock.profit_ratio || 0).toFixed(2)}%</td>
                <td class="border p-2">${stock.market_value || '--'}</td>
                <td class="border p-2">${stock.available || 0}</td>       
                <td class="border p-2">${stock.volume || 0}</td>         
                <td class="border p-2 text-center"><input type="checkbox" ${stock.profit_triggered ? 'checked' : ''} disabled></td>
                <td class="border p-2">${parseFloat(stock.today_highest_price || stock.highest_price || 0).toFixed(2)}</td>                
                <td class="border p-2">${parseFloat(stock.stop_loss_price || 0).toFixed(2)}</td> 
                <td class="border p-2 whitespace-nowrap">${(stock.open_date || '').split(' ')[0]}</td>                               
                <td class="border p-2">${parseFloat(stock.base_cost_price || stock.cost_price || 0).toFixed(2)}</td>

            `;

            elements.holdingsTableBody.appendChild(row);

        });

        // 添加复选框监听器
        addHoldingCheckboxListeners();
    }

    function addHoldingCheckboxListeners() {
        const checkboxes = elements.holdingsTableBody.querySelectorAll('.holding-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                // 检查是否所有复选框都被选中
                const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                elements.selectAllHoldings.checked = allChecked;
            });
        });
    }

    function updateLogs(logEntries) {
    
        // 记住当前滚动位置和是否在底部
        const isAtBottom = elements.orderLog.scrollTop + elements.orderLog.clientHeight >= elements.orderLog.scrollHeight - 10;
        const currentScrollTop = elements.orderLog.scrollTop;
        
        elements.logLoading.classList.add('hidden');
        elements.logError.classList.add('hidden');
        console.log("Updating logs:", logEntries);

        if (typeof logEntries === 'string') {
            elements.orderLog.value = logEntries;
        } else if (Array.isArray(logEntries)) {
            // 假设每个 logEntry 是一个对象，我们需要将其转换为字符串
            const formattedLogs = logEntries.map(entry => {
                // 根据你的交易记录对象结构调整格式化方式
                if (typeof entry === 'object' && entry !== null) {
                    // 使用 entry.trade_time, entry.trade_type,  而不是  entry.time, entry.action
                    //  并且没有 stock_name,  trade_type  需要转换一下
                    const action = entry.trade_type === 'BUY' ? '买入' : (entry.trade_type === 'SELL' ? '卖出' : entry.trade_type);
                    return `时间: ${entry.trade_time || ''}, 代码: ${entry.stock_code || ''}, 名称: , 操作: ${action || ''}, 价格: ${entry.price || ''}, 数量: ${entry.volume || ''}, 状态: `;

                    //  如果后端返回了 stock_name  字段，  把上面 return 语句中的  名称: ,  改成  名称: ${entry.stock_name || ''},

                } else {
                    return String(entry); // 如果不是对象，直接转换为字符串
                }
            });
            elements.orderLog.value = formattedLogs.join('\n');
        } else {
            elements.orderLog.value = "无法识别的日志格式，请检查数据类型";
            console.error("未知的日志数据格式:", logEntries);
            elements.logError.textContent = "未知的日志数据格式，请检查控制台错误信息";
        }
        
        // 只有当之前在底部时，才自动滚动到底部
        if (isAtBottom) {
            setTimeout(() => {
                elements.orderLog.scrollTop = elements.orderLog.scrollHeight;
            }, 10);
        } else {
            // 否则保持原来的滚动位置
            setTimeout(() => {
                elements.orderLog.scrollTop = currentScrollTop;
            }, 10);
        }
    }

    // --- 数据获取函数 ---
    async function fetchConfig() {
        try {
            const data = await apiRequest(API_ENDPOINTS.getConfig);
            updateConfigForm(data);
        } catch (error) {
            showMessage("加载配置失败", 'error');
        }
    }

    async function fetchStatus() {
        try {
            const data = await apiRequest(API_ENDPOINTS.getStatus);
            updateStatusDisplay(data);
        } catch (error) {
            showMessage("加载状态信息失败", 'error');
            updateStatusDisplay({ isMonitoring: false, account: {} });
        }
    }

    // 获取持仓数据 - 使用positions-all接口
    async function fetchHoldings() {
        elements.holdingsLoading.classList.remove('hidden');
        elements.holdingsError.classList.add('hidden');
        elements.holdingsTableBody.innerHTML = ''; // 加载时清空
        
        try {            
            const data = await apiRequest(API_ENDPOINTS.getPositionsAll);
            console.log('Data received from positions-all:', data);
            
            if (data.status === 'success' && Array.isArray(data.data)) {
                updateHoldingsTable(data.data);
            } else {
                throw new Error(data.message || '数据格式错误');
            }
        } catch (error) {
            elements.holdingsLoading.classList.add('hidden');
            elements.holdingsError.classList.remove('hidden');
            elements.holdingsError.textContent = `加载持仓数据失败: ${error.message}`;
            showMessage("加载持仓数据失败", 'error');
        }
    }

    // 修改 fetchLogs 函数以获取交易记录
    async function fetchLogs() {  
        elements.logLoading.classList.remove('hidden');
        elements.logError.classList.add('hidden');
        elements.orderLog.value = ''; // 加载时清空
        try {
            // 使用正确的 API 端点获取交易记录
            const response = await fetch(`${API_BASE_URL}/api/trade-records`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.status === 'success' && Array.isArray(data.data)) {
                // 使用交易记录更新 UI
                updateLogs(data.data);
            } else {
                throw new Error(data.message || '数据格式错误');
            }
        } catch (error) {
            elements.logLoading.classList.add('hidden');
            elements.logError.classList.remove('hidden');
            elements.logError.textContent = `加载交易记录失败: ${error.message}`;
            showMessage("加载交易记录失败", 'error');
        }
    }

    // --- 操作处理函数 ---
    async function handleToggleMonitor() {
        const endpoint = isMonitoring ? API_ENDPOINTS.stopMonitor : API_ENDPOINTS.startMonitor;
        const actionText = isMonitoring ? '停止' : '启动';
        elements.toggleMonitorBtn.disabled = true;
        showMessage(`${actionText}监控中...`, 'loading', 0);

        try {
            // 获取所有表单值，构建配置数据
            const configData = getConfigData();
            
            const data = await apiRequest(endpoint, { 
                method: 'POST',                
                body: JSON.stringify(configData)
            });
            
            showMessage(`${actionText}监控 ${data.success ? '成功' : '失败'}: ${data.message || ''}`, 
                data.success ? 'success' : 'error');
                
            await fetchStatus();
        } catch (error) {
            await fetchStatus();
        } finally {
            elements.toggleMonitorBtn.disabled = false;
            elements.messageArea.innerHTML = '';
        }

    }

    // 获取所有配置表单的值
    function getConfigData() {
        return {
            singleBuyAmount: parseFloat(elements.singleBuyAmount.value) || 35000,
            firstProfitSell: parseFloat(elements.firstProfitSell.value) || 5.0,
            firstProfitSellEnabled: elements.firstProfitSellEnabled.checked,
            stockGainSellPencent: parseFloat(elements.stockGainSellPencent.value) || 60.0,
            firstProfitSellPencent: elements.firstProfitSellPencent.checked,
            allowBuy: elements.allowBuy.checked,
            allowSell: elements.allowSell.checked,
            stopLossBuy: parseFloat(elements.stopLossBuy.value) || 5.0,
            stopLossBuyEnabled: elements.stopLossBuyEnabled.checked,
            stockStopLoss: parseFloat(elements.stockStopLoss.value) || 7.0,
            StopLossEnabled: elements.StopLossEnabled.checked,
            singleStockMaxPosition: parseFloat(elements.singleStockMaxPosition.value) || 70000,
            totalMaxPosition: parseFloat(elements.totalMaxPosition.value) || 400000,
            connectPort: elements.connectPort.value || '5000',
            totalAccounts: elements.totalAccounts.value || '127.0.0.1',
            globalAllowBuySell: elements.globalAllowBuySell.checked            
        };
    }

    async function handleSaveConfig() {
        const configData = getConfigData();
        console.log("Saving config:", configData);
        showMessage("保存配置中...", 'loading', 0);
        elements.saveConfigBtn.disabled = true;

        try {
            const data = await apiRequest(API_ENDPOINTS.saveConfig, {
                method: 'POST',                
                body: JSON.stringify(configData),
            });
            showMessage(data.message || "配置已保存", 'success');
        } catch (error) {
            // 错误已由apiRequest处理
        } finally {
            elements.saveConfigBtn.disabled = false;
            elements.messageArea.innerHTML = '';
        }

    }

    async function handleClearLogs() {
        if (!confirm("确定要清空所有日志吗？此操作不可撤销。")) return;
        showMessage("清空日志中...", 'loading', 0);
        elements.clearLogBtn.disabled = true;
        try {
            const data = await apiRequest(API_ENDPOINTS.clearLogs, { method: 'POST' });
            showMessage(data.message || "日志已清空", 'success');
            elements.orderLog.value = ''; // 立即清空前端显示
        } catch (error) {
            // 错误已由apiRequest处理
        } finally {
            elements.clearLogBtn.disabled = false;
            elements.messageArea.innerHTML = '';
        }

    }

    // 初始化持仓数据 - 特殊处理，需要更新API地址
    async function handleInitHoldings() {
        if (!confirm("确定要初始化持仓数据吗？")) return;
        
        // 更新API基础URL
        updateApiBaseUrl();
        
        elements.initHoldingsBtn.disabled = true;
        const originalText = elements.initHoldingsBtn.textContent;
        elements.initHoldingsBtn.textContent = "初始化中...";
        showMessage("正在初始化持仓数据...", 'loading', 0);

        try {
            const configData = getConfigData();
            const data = await apiRequest(API_ENDPOINTS.initHoldings, {                
                method: 'POST',
                body: JSON.stringify(configData),
            });
            showMessage(data.message || "持仓数据初始化成功", 'success');
            await fetchHoldings(); // 刷新持仓数据
            await fetchStatus(); // 刷新账户状态
        } catch (error) {
            // 错误已由apiRequest处理
        } finally {
            elements.initHoldingsBtn.disabled = false;
            elements.initHoldingsBtn.textContent = originalText;
            elements.messageArea.innerHTML = '';
        }

    }

    // 通用操作处理
    async function handleGenericAction(button, endpoint, confirmationMessage) {
        if (confirmationMessage && !confirm(confirmationMessage)) return;

        button.disabled = true;
        const originalText = button.textContent;
        button.textContent = "处理中...";
        showMessage("正在执行操作...", 'loading', 0);

        try {
            const data = await apiRequest(endpoint, { method: 'POST' });            
            showMessage(data.message || "操作成功", 'success');
            // 根据操作类型刷新相关数据
            if (endpoint === API_ENDPOINTS.clearCurrentData || endpoint === API_ENDPOINTS.clearBuySellData) {
                await fetchHoldings(); // 刷新持仓数据
            }
            if (endpoint === API_ENDPOINTS.importSavedData) {
                await fetchAllData(); // 导入数据后刷新所有数据
            }
        } catch (error) {
            // 错误已由apiRequest处理
        } finally {
            button.disabled = false;
            button.textContent = originalText;
            elements.messageArea.innerHTML = '';

        }
    }

    async function handleExecuteBuy() {
        const buyData = {
            strategy: elements.buyStrategy.value,
            quantity: parseInt(elements.buyQuantity.value) || 0,
            ...getConfigData() // 包含所有配置参数
        };
        
        if (buyData.quantity <= 0) {
            showMessage("请输入有效的买入数量", "error");
            return;
        }

        elements.executeBuyBtn.disabled = true;
        showMessage(`执行买入 (${buyData.strategy}, ${buyData.quantity}只)...`, 'loading', 0);

        try {
            const data = await apiRequest(API_ENDPOINTS.executeBuy, {
                method: 'POST',                
                body: JSON.stringify(buyData),
            });
            showMessage(data.message || "买入指令已发送", 'success');
            // 刷新相关数据
            await fetchHoldings();
            await fetchLogs();
            await fetchStatus(); // 更新余额等
        } catch (error) {
            // 错误已由apiRequest处理
        } finally {
            elements.executeBuyBtn.disabled = false;
            elements.messageArea.innerHTML = '';
        }

    }

    function showRefreshStatus() {
        // 如果已经存在刷新状态元素，则移除它
        const existingStatus = document.getElementById('refreshStatus');
        if (existingStatus) {
            existingStatus.remove();
        }
        
        // 创建新的刷新状态元素
        const statusElement = document.createElement('div');
        statusElement.id = 'refreshStatus';
        statusElement.className = 'fixed bottom-2 right-2 bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs';
        statusElement.innerHTML = '数据刷新中...';
        document.body.appendChild(statusElement);
        
        // 0.5秒后淡出
        setTimeout(() => {
            statusElement.style.animation = 'fadeOut 0.5s ease-in-out';
            setTimeout(() => {
                if (statusElement.parentNode) {
                    statusElement.parentNode.removeChild(statusElement);
                }
            }, 500);
        }, 500);
    }

    // --- 轮询机制 ---
    function startPolling() {
        if (pollingIntervalId) return; // 已在轮询中
        console.log("Starting data polling...");
        // 先立即轮询一次
        pollData();
        pollingIntervalId = setInterval(pollData, POLLING_INTERVAL);
    }

    function stopPolling() {
        if (!pollingIntervalId) return; // 未在轮询
        console.log("Stopping data polling.");
        clearInterval(pollingIntervalId);
        pollingIntervalId = null;
    }

    async function pollData() {
        console.log("Polling for data updates...");
        // 添加刷新状态
        elements.orderLog.classList.add('refreshing');

        // 显示刷新状态
        showRefreshStatus();

        // 并行获取所需的数据
        await Promise.allSettled([
            fetchStatus(), // 包含账户信息的状态
            fetchHoldings(), // 持仓数据
            fetchLogs() // 日志数据
        ]);

        // 刷新完成后移除状态
        Promise.allSettled([/* 原有异步操作 */]).finally(() => {
            elements.orderLog.classList.remove('refreshing');
        });

        console.log("Polling cycle finished.");
    }

    // 在HTML中添加状态指示器元素
    function addConnectionStatusIndicator() {
        const statusDiv = document.createElement('div');
        statusDiv.id = 'connectionStatus';
        statusDiv.className = 'connection-status disconnected';
        statusDiv.textContent = 'API未连接';
        document.body.appendChild(statusDiv);
    }

    // 添加API连接检查函数
    async function checkApiConnection() {
        try {
            console.log("Checking API connection at:", API_ENDPOINTS.checkConnection);
            const response = await fetch(API_ENDPOINTS.checkConnection);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log("Connection check response:", data);
            updateConnectionStatus(data.connected);
        } catch (error) {
            console.error("Error checking API connection:", error);
            updateConnectionStatus(false);
        } finally {
            setTimeout(checkApiConnection, 5000);
        }
    }

    function updateConnectionStatus(isConnected) {
        const statusElement = document.getElementById('connectionStatus');
        if (isConnected) {
            statusElement.textContent = "API已连接";
            statusElement.classList.remove('disconnected');
            statusElement.classList.add('connected');
        } else {
            statusElement.textContent = "API未连接";
            statusElement.classList.remove('connected');
            statusElement.classList.add('disconnected');
        }
    }

    // 添加连接状态指示器
    addConnectionStatusIndicator();
    
    // 启动连接检查
    setTimeout(checkApiConnection, 1000);

    // --- 事件监听器 ---
    elements.toggleMonitorBtn.addEventListener('click', handleToggleMonitor);
    elements.saveConfigBtn.addEventListener('click', handleSaveConfig);
    elements.clearLogBtn.addEventListener('click', handleClearLogs);
    elements.clearCurrentDataBtn.addEventListener('click', () => handleGenericAction(
        elements.clearCurrentDataBtn,
        API_ENDPOINTS.clearCurrentData,
        "确定要清空当前数据吗？"
    ));
    elements.clearBuySellDataBtn.addEventListener('click', () => handleGenericAction(
        elements.clearBuySellDataBtn,
        API_ENDPOINTS.clearBuySellData,
        "确定要清空买入/卖出数据吗？"
    ));
    elements.importDataBtn.addEventListener('click', () => handleGenericAction(
        elements.importDataBtn,
        API_ENDPOINTS.importSavedData,
        "确定要导入已保存的数据吗？当前设置和持仓将被覆盖。"
    ));
    elements.initHoldingsBtn.addEventListener('click', handleInitHoldings);
    elements.executeBuyBtn.addEventListener('click', handleExecuteBuy);

    // 持仓表格"全选"复选框监听器
    elements.selectAllHoldings.addEventListener('change', (event) => {
        const isChecked = event.target.checked;
        const checkboxes = elements.holdingsTableBody.querySelectorAll('.holding-checkbox');
        checkboxes.forEach(cb => cb.checked = isChecked);
    });

    // IP/端口变化监听器
    elements.totalAccounts.addEventListener('change', updateApiBaseUrl);
    elements.connectPort.addEventListener('change', updateApiBaseUrl);

    // --- 初始数据加载 ---
    async function fetchAllData() {
        // 初始化API基础URL
        updateApiBaseUrl();
        
        showMessage("正在加载初始数据...", 'loading', 0);
        await Promise.allSettled([
            fetchConfig(),
            fetchStatus(), // 获取状态和账户信息
            fetchHoldings(),
            fetchLogs()
        ]);
        showMessage("数据加载完成", 'success', 2000);

        // 如果监控已开启，自动启动轮询
        if (isMonitoring) {
            startPolling();
        }

        // If monitoring is active, polling will start automatically
        setTimeout(checkApiConnection, 1000); // Add a 1-second delay
    }

    console.log("Adding event listeners and fetching initial data...");
    fetchAllData(); // 脚本运行时加载初始数据

});

console.log("Script loaded");