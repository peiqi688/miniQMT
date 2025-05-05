document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded and parsed");

    // --- Configuration ---
    const API_BASE_URL = ''; // Replace with your actual API base URL e.g., http://localhost:5000
    const API_ENDPOINTS = {
        // --- GET Endpoints ---
        getConfig: `${API_BASE_URL}/api/config`,
        getStatus: `${API_BASE_URL}/api/status`, // Gets status, account info
        getHoldings: `${API_BASE_URL}/api/holdings`,
        getLogs: `${API_BASE_URL}/api/logs`,
        // --- POST Endpoints ---
        saveConfig: `${API_BASE_URL}/api/config/save`,
        startMonitor: `${API_BASE_URL}/api/monitor/start`,
        stopMonitor: `${API_BASE_URL}/api/monitor/stop`,
        clearLogs: `${API_BASE_URL}/api/logs/clear`,
        clearCurrentData: `${API_BASE_URL}/api/data/clear_current`, // Define what 'current data' means
        clearBuySellData: `${API_BASE_URL}/api/data/clear_buysell`, // Define what this data means
        importSavedData: `${API_BASE_URL}/api/data/import`,
        initHoldings: `${API_BASE_URL}/api/holdings/init`,
        executeBuy: `${API_BASE_URL}/api/actions/execute_buy`,
        updateHoldingParams: `${API_BASE_URL}/api/holdings/update` // Example: For updating buy/sell prices in table
    };

    const POLLING_INTERVAL = 5000; // Poll for updates every 5 seconds (adjust as needed)
    let pollingIntervalId = null;
    let isMonitoring = false; // Track monitoring state

    // --- DOM Element References ---
    const elements = {
        messageArea: document.getElementById('messageArea'),
        // Config Form
        singleBuyAmount: document.getElementById('singleBuyAmount'),
        platformStopLoss: document.getElementById('platformStopLoss'),
        platformStopLossEnabled: document.getElementById('platformStopLossEnabled'),
        profitSlowdown: document.getElementById('profitSlowdown'),
        firstProfitSell: document.getElementById('firstProfitSell'),
        firstProfitSellEnabled: document.getElementById('firstProfitSellEnabled'),
        stockStopLoss: document.getElementById('stockStopLoss'),
        stockGainSell: document.getElementById('stockGainSell'),
        allowBuy: document.getElementById('allowBuy'),
        allowSell: document.getElementById('allowSell'),
        singleStockMaxPosition: document.getElementById('singleStockMaxPosition'),
        totalMaxPosition: document.getElementById('totalMaxPosition'),
        connectPort: document.getElementById('connectPort'),
        totalAccounts: document.getElementById('totalAccounts'),
        // Account Info & Status
        accountId: document.getElementById('accountId'),
        availableBalance: document.getElementById('availableBalance'),
        maxHoldingValue: document.getElementById('maxHoldingValue'),
        totalAssets: document.getElementById('totalAssets'),
        statusIndicator: document.getElementById('statusIndicator'),
        // Buttons
        toggleMonitorBtn: document.getElementById('toggleMonitorBtn'),
        saveConfigBtn: document.getElementById('saveConfigBtn'),
        clearLogBtn: document.getElementById('clearLogBtn'),
        clearCurrentDataBtn: document.getElementById('clearCurrentDataBtn'),
        clearBuySellDataBtn: document.getElementById('clearBuySellDataBtn'),
        importDataBtn: document.getElementById('importDataBtn'),
        initHoldingsBtn: document.getElementById('initHoldingsBtn'),
        executeBuyBtn: document.getElementById('executeBuyBtn'),
        // Buy Settings
        buyStrategy: document.getElementById('buyStrategy'),
        buyQuantity: document.getElementById('buyQuantity'),
        // Holdings Table
        holdingsTableBody: document.getElementById('holdingsTableBody'),
        selectAllHoldings: document.getElementById('selectAllHoldings'),
        holdingsLoading: document.getElementById('holdingsLoading'),
        holdingsError: document.getElementById('holdingsError'),
        // Order Log
        orderLog: document.getElementById('orderLog'),
        logLoading: document.getElementById('logLoading'),
        logError: document.getElementById('logError'),
    };

    // --- Utility Functions ---

    /**
     * Displays messages (loading, error, success) in the message area.
     * @param {string} text - The message text.
     * @param {'loading' | 'error' | 'success' | 'info'} type - The message type.
     * @param {number} duration - How long to show the message (ms). 0 for indefinite.
     */
    function showMessage(text, type = 'info', duration = 5000) {
        elements.messageArea.innerHTML = ''; // Clear previous messages
        const messageDiv = document.createElement('div');
        messageDiv.textContent = text;
        messageDiv.className = `status-message ${type}`; // Add base class and type class
        elements.messageArea.appendChild(messageDiv);

        if (duration > 0) {
            setTimeout(() => {
                if (messageDiv.parentNode === elements.messageArea) {
                    elements.messageArea.removeChild(messageDiv);
                }
            }, duration);
        }
    }

    /**
     * Generic function to make API requests.
     * @param {string} url - The API endpoint URL.
     * @param {object} options - Fetch options (method, headers, body, etc.).
     * @returns {Promise<any>} - The JSON response data.
     * @throws {Error} - If the request fails or response is not ok.
     */
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
                } catch (e) { /* Ignore if error response is not JSON */ }
                throw new Error(errorMsg);
            }

            const data = await response.json();
            console.log(`API Response: ${options.method || 'GET'} ${url}`, data);
            return data;
        } catch (error) {
            console.error(`API Error: ${options.method || 'GET'} ${url}`, error);
            showMessage(`请求失败: ${error.message}`, 'error');
            throw error; // Re-throw for specific handlers
        }
    }

    // --- UI Update Functions ---

    function updateConfigForm(config) {
        console.log("Updating config form:", config);
        if (!config) return;
        elements.singleBuyAmount.value = config.singleBuyAmount ?? '';
        elements.platformStopLoss.value = config.platformStopLoss ?? '';
        elements.platformStopLossEnabled.checked = config.platformStopLossEnabled ?? false;
        elements.profitSlowdown.value = config.profitSlowdown ?? '';
        elements.firstProfitSell.value = config.firstProfitSell ?? '';
        elements.firstProfitSellEnabled.checked = config.firstProfitSellEnabled ?? false;
        elements.stockStopLoss.value = config.stockStopLoss ?? '';
        elements.stockGainSell.value = config.stockGainSell ?? '';
        elements.allowBuy.checked = config.allowBuy ?? true;
        elements.allowSell.checked = config.allowSell ?? true;
        elements.singleStockMaxPosition.value = config.singleStockMaxPosition ?? '';
        elements.totalMaxPosition.value = config.totalMaxPosition ?? '';
        elements.connectPort.value = config.connectPort ?? '';
        elements.totalAccounts.value = config.totalAccounts ?? '';
    }

    function updateStatusDisplay(statusData) {
        console.log("Updating status display:", statusData);
        if (!statusData) return;

        // Account Info
        elements.accountId.textContent = statusData.account?.id ?? '--';
        elements.availableBalance.textContent = statusData.account?.availableBalance?.toFixed(2) ?? '--';
        elements.maxHoldingValue.textContent = statusData.account?.maxHoldingValue?.toFixed(2) ?? '--';
        elements.totalAssets.textContent = statusData.account?.totalAssets?.toFixed(2) ?? '--';

        // Monitoring Status
        isMonitoring = statusData.isMonitoring ?? false;
        if (isMonitoring) {
            elements.statusIndicator.textContent = '运行中';
            elements.statusIndicator.className = 'text-lg font-bold text-green-600';
            elements.toggleMonitorBtn.textContent = '停止执行监控';
            elements.toggleMonitorBtn.classList.remove('bg-blue-600', 'hover:bg-blue-700');
            elements.toggleMonitorBtn.classList.add('bg-red-600', 'hover:bg-red-700');
            startPolling(); // Start polling if monitoring is active
        } else {
            elements.statusIndicator.textContent = '未运行';
            elements.statusIndicator.className = 'text-lg font-bold text-red-600';
            elements.toggleMonitorBtn.textContent = '开始执行监控';
            elements.toggleMonitorBtn.classList.remove('bg-red-600', 'hover:bg-red-700');
            elements.toggleMonitorBtn.classList.add('bg-blue-600', 'hover:bg-blue-700');
            stopPolling(); // Stop polling if monitoring stopped
        }
        // Potentially disable/enable other buttons based on status
        // e.g., elements.saveConfigBtn.disabled = isMonitoring;
    }

    function updateHoldingsTable(holdings) {
        console.log("Updating holdings table:", holdings);
        elements.holdingsTableBody.innerHTML = ''; // Clear existing rows
        elements.holdingsLoading.classList.add('hidden');
        elements.holdingsError.classList.add('hidden');

        if (!Array.isArray(holdings) || holdings.length === 0) {
            elements.holdingsTableBody.innerHTML = '<tr><td colspan="14" class="text-center p-4 text-gray-500">无持仓数据</td></tr>';
            return;
        }

        holdings.forEach(stock => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50 even:bg-gray-100';
            row.innerHTML = `
                <td class="border p-2"><input type="checkbox" class="holding-checkbox" data-id="${stock.id || stock.code}"></td>
                <td class="border p-2">${stock.code || '--'}</td>
                <td class="border p-2">${stock.name || '--'}</td>
                <td class="border p-2 ${stock.changePercent >= 0 ? 'text-green-600' : 'text-red-600'}">${stock.changePercent?.toFixed(2) ?? '--'}%</td>
                <td class="border p-2">${stock.costPrice?.toFixed(2) ?? '--'}</td>
                <td class="border p-2">${stock.marketValue?.toFixed(2) ?? '--'}</td>
                <td class="border p-2 ${stock.isLoss ? 'text-red-600' : 'text-green-600'}">${stock.isLoss ? '亏损' : '盈利'}</td>
                <td class="border p-2">${stock.availableQty ?? '--'}</td>
                <td class="border p-2">${stock.holdingQty ?? '--'}</td>
                <td class="border p-2"><input type='number' class='w-20 border rounded px-1 text-sm holding-input' data-id="${stock.id || stock.code}" data-field="buyPrice" value='${stock.buyPrice?.toFixed(2) ?? ''}' placeholder="买入价"/></td>
                <td class="border p-2"><input type='number' class='w-20 border rounded px-1 text-sm holding-input' data-id="${stock.id || stock.code}" data-field="sellPrice" value='${stock.sellPrice?.toFixed(2) ?? ''}' placeholder="卖出价"/></td>
                <td class="border p-2"><input type='number' class='w-20 border rounded px-1 text-sm holding-input' data-id="${stock.id || stock.code}" data-field="pendingPrice" value='${stock.pendingPrice?.toFixed(2) ?? ''}' placeholder="挂单价"/></td>
                <td class="border p-2 whitespace-nowrap">${stock.updateTime || '--'}</td>
                <td class="border p-2">${stock.lowestPrice?.toFixed(2) ?? '--'}</td>
            `;
            elements.holdingsTableBody.appendChild(row);
        });

        // Add event listeners for dynamically created inputs if needed (e.g., for auto-save on change)
         addHoldingInputListeners();
    }

     function addHoldingInputListeners() {
        const inputs = elements.holdingsTableBody.querySelectorAll('.holding-input');
        inputs.forEach(input => {
            input.addEventListener('change', handleHoldingInputChange); // Or 'blur'
        });
    }

    async function handleHoldingInputChange(event) {
        const input = event.target;
        const id = input.dataset.id;
        const field = input.dataset.field;
        const value = input.value;

        console.log(`Holding input changed: ID=${id}, Field=${field}, Value=${value}`);
        // Optional: Send update to backend immediately
        try {
             showMessage(`正在更新 ${id} 的 ${field}...`, 'loading', 2000);
             const updateData = { id: id, params: { [field]: parseFloat(value) || 0 } }; // Construct payload as needed by backend
             await apiRequest(API_ENDPOINTS.updateHoldingParams, {
                 method: 'POST',
                 body: JSON.stringify(updateData),
             });
             showMessage(`${id} 的 ${field} 更新成功`, 'success');
         } catch (error) {
             showMessage(`更新 ${id} 的 ${field} 失败: ${error.message}`, 'error');
             // Optional: Revert input value if needed
         }
    }


    function updateLogs(logEntries) {
        console.log("Updating logs:", logEntries);
        elements.logLoading.classList.add('hidden');
        elements.logError.classList.add('hidden');

        if (typeof logEntries === 'string') {
             // Assume backend returns a single string block
             elements.orderLog.value = logEntries;
        } else if (Array.isArray(logEntries)) {
            // Assume backend returns an array of log lines
            elements.orderLog.value = logEntries.join('\n');
        } else {
             elements.orderLog.value = "无法识别的日志格式";
        }
        // Auto-scroll to bottom
        elements.orderLog.scrollTop = elements.orderLog.scrollHeight;
    }

    // --- Data Fetching Functions ---

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
             // Reset status display on error?
              updateStatusDisplay({ isMonitoring: false, account: {} });
        }
    }

    async function fetchHoldings() {
        elements.holdingsLoading.classList.remove('hidden');
        elements.holdingsError.classList.add('hidden');
        elements.holdingsTableBody.innerHTML = ''; // Clear while loading
        try {
            const data = await apiRequest(API_ENDPOINTS.getHoldings);
            updateHoldingsTable(data);
        } catch (error) {
            elements.holdingsLoading.classList.add('hidden');
            elements.holdingsError.classList.remove('hidden');
            elements.holdingsError.textContent = `加载持仓数据失败: ${error.message}`;
            showMessage("加载持仓数据失败", 'error');
        }
    }

    async function fetchLogs() {
        elements.logLoading.classList.remove('hidden');
        elements.logError.classList.add('hidden');
         elements.orderLog.value = ''; // Clear while loading
        try {
            // Assuming backend returns logs as { logs: "line1\nline2..." } or { logs: ["line1", "line2"] }
            const data = await apiRequest(API_ENDPOINTS.getLogs);
            updateLogs(data.logs || data || ''); // Handle different response structures
        } catch (error) {
             elements.logLoading.classList.add('hidden');
             elements.logError.classList.remove('hidden');
             elements.logError.textContent = `加载日志失败: ${error.message}`;
             showMessage("加载日志失败", 'error');
        }
    }

    // --- Action Handlers ---

    async function handleToggleMonitor() {
        const endpoint = isMonitoring ? API_ENDPOINTS.stopMonitor : API_ENDPOINTS.startMonitor;
        const actionText = isMonitoring ? '停止' : '启动';
        elements.toggleMonitorBtn.disabled = true;
        showMessage(`${actionText}监控中...`, 'loading', 0); // Indefinite loading message

        try {
            const data = await apiRequest(endpoint, { method: 'POST' });
            showMessage(`${actionText}监控 ${data.success ? '成功' : '失败'}: ${data.message || ''}`, data.success ? 'success' : 'error');
            // Fetch status immediately to update UI correctly
            await fetchStatus();
        } catch (error) {
             // Error message already shown by apiRequest
             // Ensure button is re-enabled even on failure
             await fetchStatus(); // Refresh status anyway
        } finally {
            elements.toggleMonitorBtn.disabled = false;
             elements.messageArea.innerHTML = ''; // Clear loading message if not replaced by success/error
        }
    }

     async function handleSaveConfig() {
        const configData = {
            singleBuyAmount: parseFloat(elements.singleBuyAmount.value) || 0,
            platformStopLoss: parseFloat(elements.platformStopLoss.value) || 0,
            platformStopLossEnabled: elements.platformStopLossEnabled.checked,
            profitSlowdown: parseFloat(elements.profitSlowdown.value) || 0,
            firstProfitSell: parseFloat(elements.firstProfitSell.value) || 0,
            firstProfitSellEnabled: elements.firstProfitSellEnabled.checked,
            stockStopLoss: parseFloat(elements.stockStopLoss.value) || 0,
            stockGainSell: parseFloat(elements.stockGainSell.value) || 0,
            allowBuy: elements.allowBuy.checked,
            allowSell: elements.allowSell.checked,
            singleStockMaxPosition: parseFloat(elements.singleStockMaxPosition.value) || 0,
            totalMaxPosition: parseFloat(elements.totalMaxPosition.value) || 0,
            connectPort: elements.connectPort.value,
            totalAccounts: parseInt(elements.totalAccounts.value) || 0,
        };
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
            // Error message shown by apiRequest
        } finally {
             elements.saveConfigBtn.disabled = false;
             elements.messageArea.innerHTML = ''; // Clear loading message if not replaced by success/error
        }
    }

    async function handleClearLogs() {
        if (!confirm("确定要清空所有日志吗？此操作不可撤销。")) return;
        showMessage("清空日志中...", 'loading', 0);
        elements.clearLogBtn.disabled = true;
        try {
            const data = await apiRequest(API_ENDPOINTS.clearLogs, { method: 'POST' });
            showMessage(data.message || "日志已清空", 'success');
            elements.orderLog.value = ''; // Clear frontend immediately
        } catch (error) {
           // Error handled by apiRequest
        } finally {
            elements.clearLogBtn.disabled = false;
            elements.messageArea.innerHTML = '';
        }
    }

    // Implement handlers for other buttons similarly...
    async function handleGenericAction(button, endpoint, confirmationMessage) {
         if (confirmationMessage && !confirm(confirmationMessage)) return;

         button.disabled = true;
         const originalText = button.textContent;
         button.textContent = "处理中...";
         showMessage("正在执行操作...", 'loading', 0);

         try {
             const data = await apiRequest(endpoint, { method: 'POST' });
             showMessage(data.message || "操作成功", 'success');
             // Optionally refresh data after action
             if (endpoint === API_ENDPOINTS.clearCurrentData || endpoint === API_ENDPOINTS.clearBuySellData || endpoint === API_ENDPOINTS.initHoldings) {
                 await fetchHoldings(); // Refresh holdings if data related to them was cleared/initialized
             }
             if (endpoint === API_ENDPOINTS.importSavedData) {
                 await fetchAllData(); // Refresh everything after import
             }
         } catch (error) {
             // Error message shown by apiRequest
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
             // Refresh relevant data
             await fetchHoldings();
             await fetchLogs();
             await fetchStatus(); // Update balance etc.
         } catch (error) {
             // Error message shown by apiRequest
         } finally {
             elements.executeBuyBtn.disabled = false;
              elements.messageArea.innerHTML = '';
         }
    }

    // --- Polling ---
    function startPolling() {
        if (pollingIntervalId) return; // Already polling
        console.log("Starting data polling...");
        // Poll immediately first time
        pollData();
        pollingIntervalId = setInterval(pollData, POLLING_INTERVAL);
    }

    function stopPolling() {
        if (!pollingIntervalId) return; // Not polling
        console.log("Stopping data polling.");
        clearInterval(pollingIntervalId);
        pollingIntervalId = null;
    }

    async function pollData() {
        console.log("Polling for data updates...");
        // Fetch data that needs regular updates
        // Use Promise.allSettled to fetch concurrently and handle individual failures
        await Promise.allSettled([
            fetchStatus(), // Status includes account info
            fetchHoldings(),
            fetchLogs()
        ]);
         console.log("Polling cycle finished.");
    }

     // --- Event Listeners ---
     elements.toggleMonitorBtn.addEventListener('click', handleToggleMonitor);
     elements.saveConfigBtn.addEventListener('click', handleSaveConfig);
     elements.clearLogBtn.addEventListener('click', handleClearLogs);
     elements.executeBuyBtn.addEventListener('click', handleExecuteBuy);

     // Add listeners for other action buttons using the generic handler
     elements.clearCurrentDataBtn.addEventListener('click', () => handleGenericAction(
         elements.clearCurrentDataBtn,
         API_ENDPOINTS.clearCurrentData,
         "确定要清空当前数据吗？" // Define what "current data" means and adjust message
     ));
     elements.clearBuySellDataBtn.addEventListener('click', () => handleGenericAction(
         elements.clearBuySellDataBtn,
         API_ENDPOINTS.clearBuySellData,
         "确定要清空买入/卖出数据吗？" // Define what this data is and adjust message
     ));
     elements.importDataBtn.addEventListener('click', () => handleGenericAction(
         elements.importDataBtn,
         API_ENDPOINTS.importSavedData,
         "确定要导入已保存的数据吗？当前设置和持仓将被覆盖。"
     ));
     elements.initHoldingsBtn.addEventListener('click', () => handleGenericAction(
         elements.initHoldingsBtn,
         API_ENDPOINTS.initHoldings,
         "确定要初始化持仓数据吗？这可能基于当前实际持仓进行同步。"
     ));

     // Listener for "Select All" checkbox in holdings table
     elements.selectAllHoldings.addEventListener('change', (event) => {
        const isChecked = event.target.checked;
        const checkboxes = elements.holdingsTableBody.querySelectorAll('.holding-checkbox');
        checkboxes.forEach(cb => cb.checked = isChecked);
     });


    // --- Initial Data Load ---
    async function fetchAllData() {
        showMessage("正在加载初始数据...", 'loading', 0);
        await Promise.allSettled([
            fetchConfig(),
            fetchStatus(), // Fetches status and account info
            fetchHoldings(),
            fetchLogs()
        ]);
        showMessage("数据加载完成", 'success', 2000); // Short success message
        // Polling will start automatically if fetchStatus finds monitoring is active
    }

    console.log("Adding event listeners and fetching initial data...");
    fetchAllData(); // Load initial data when the script runs

});

console.log("Script loaded");