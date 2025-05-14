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
        getPositionsAll: `/api/positions-all`, // 获取所有持仓数据
        getTradeRecords: `/api/trade-records`, // 获取交易记录
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

    // 轮询设置
    let POLLING_INTERVAL = 5000; // 默认5秒
    const ACTIVE_POLLING_INTERVAL = 5000; // 活跃状态：5秒
    const INACTIVE_POLLING_INTERVAL = 15000; // 非活跃状态：15秒
    let pollingIntervalId = null;
    let isMonitoring = false; // 监控状态
    let isPageActive = true; // 页面活跃状态
    
    // SSE连接
    let sseConnection = null;
    
    // 数据版本号跟踪
    let currentDataVersions = {
        holdings: 0,
        logs: 0,
        status: 0
    };

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

    // --- 监听页面可见性变化 ---
    document.addEventListener('visibilitychange', () => {
        isPageActive = !document.hidden;
        
        // 如果轮询已启动，重新调整轮询间隔
        if (pollingIntervalId) {
            stopPolling();
            startPolling();
        }
    });

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

    // 显示刷新状态
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

    // 显示更新指示器
    function showUpdatedIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'fixed top-2 left-2 bg-green-100 text-green-800 px-2 py-1 rounded text-xs z-50';
        indicator.textContent = '数据已更新';
        document.body.appendChild(indicator);
        
        setTimeout(() => {
            indicator.style.opacity = '0';
            indicator.style.transition = 'opacity 0.5s';
            setTimeout(() => {
                if (indicator.parentNode) {
                    indicator.parentNode.removeChild(indicator);
                }
            }, 500);
        }, 1000);
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

    // API请求函数
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

    // 轻量级账户信息更新，用于SSE
    function updateQuickAccountInfo(accountInfo) {
        if (accountInfo.available !== undefined) {
            elements.availableBalance.textContent = parseFloat(accountInfo.available).toFixed(2);
            // 添加闪烁效果
            elements.availableBalance.classList.add('highlight-update');
            setTimeout(() => {
                elements.availableBalance.classList.remove('highlight-update');
            }, 1000);
        }
    }

    // 判断持仓数据是否需要更新
    function shouldUpdateRow(oldData, newData) {
        // 检查关键字段是否有变化
        const keysToCheck = ['current_price', 'market_value', 'profit_ratio', 'available', 'volume'];
        return keysToCheck.some(key => {
            // 对于数值，考虑舍入误差
            if (typeof oldData[key] === 'number' && typeof newData[key] === 'number') {
                return Math.abs(oldData[key] - newData[key]) > 0.001;
            }
            return oldData[key] !== newData[key];
        });
    }

    // 更新现有持仓行
    function updateExistingRow(row, stock) {
        // 更新各个单元格的值
        const cells = row.querySelectorAll('td');
        
        // 确保保留复选框
        
        // 更新基本信息
        cells[1].textContent = stock.stock_code || '--';
        cells[2].textContent = stock.stock_name || stock.name || '--';
        
        // 更新涨跌幅，包括类名
        const changePercentage = parseFloat(stock.change_percentage || 0);
        cells[3].textContent = `${changePercentage.toFixed(2)}%`;
        cells[3].className = `border p-2 ${changePercentage >= 0 ? 'text-red-600' : 'text-green-600'}`;
        
        // 更新价格、成本和盈亏
        cells[4].textContent = parseFloat(stock.current_price || 0).toFixed(2);
        cells[5].textContent = parseFloat(stock.cost_price || 0).toFixed(2);
        
        const profitRatio = parseFloat(stock.profit_ratio || 0);
        cells[6].textContent = `${profitRatio.toFixed(2)}%`;
        cells[6].className = `border p-2 ${profitRatio >= 0 ? 'text-red-600' : 'text-green-600'}`;
        
        // 更新持仓信息
        cells[7].textContent = stock.market_value || '--';
        cells[8].textContent = stock.available || 0;
        cells[9].textContent = stock.volume || 0;
        
        // 更新止盈标志
        cells[10].innerHTML = `<input type="checkbox" ${stock.profit_triggered ? 'checked' : ''} disabled>`;
        
        // 更新其他数据
        cells[11].textContent = parseFloat(stock.highest_price || 0).toFixed(2);
        cells[12].textContent = parseFloat(stock.stop_loss_price || 0).toFixed(2);
        cells[13].textContent = (stock.open_date || '').split(' ')[0];
        cells[14].textContent = parseFloat(stock.base_cost_price || stock.cost_price || 0).toFixed(2);
        
        // 高亮闪烁更新的单元格
        cells[4].classList.add('highlight-update');
        setTimeout(() => {
            cells[4].classList.remove('highlight-update');
        }, 1000);
    }

    // 创建新的持仓行
    function createStockRow(stock) {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50 even:bg-gray-100';
        row.dataset.stockCode = stock.stock_code; // 添加标识属性
        
        // 计算关键值
        const changePercentage = parseFloat(stock.change_percentage || 0);
        const profitRatio = parseFloat(stock.profit_ratio || 0);
        
        // 构建行内容
        row.innerHTML = `
            <td class="border p-2"><input type="checkbox" class="holding-checkbox" data-id="${stock.id || stock.stock_code}"></td>
            <td class="border p-2">${stock.stock_code || '--'}</td>
            <td class="border p-2">${stock.stock_name || stock.name || '--'}</td>                
            <td class="border p-2 ${changePercentage >= 0 ? 'text-red-600' : 'text-green-600'}">${changePercentage.toFixed(2)}%</td>
            <td class="border p-2">${parseFloat(stock.current_price || 0).toFixed(2)}</td>
            <td class="border p-2">${parseFloat(stock.cost_price || 0).toFixed(2)}</td>
            <td class="border p-2 ${profitRatio >= 0 ? 'text-red-600' : 'text-green-600'}">${profitRatio.toFixed(2)}%</td>
            <td class="border p-2">${stock.market_value || '--'}</td>
            <td class="border p-2">${stock.available || 0}</td>       
            <td class="border p-2">${stock.volume || 0}</td>         
            <td class="border p-2 text-center"><input type="checkbox" ${stock.profit_triggered ? 'checked' : ''} disabled></td>
            <td class="border p-2">${parseFloat(stock.highest_price || 0).toFixed(2)}</td>                
            <td class="border p-2">${parseFloat(stock.stop_loss_price || 0).toFixed(2)}</td> 
            <td class="border p-2 whitespace-nowrap">${(stock.open_date || '').split(' ')[0]}</td>                               
            <td class="border p-2">${parseFloat(stock.base_cost_price || stock.cost_price || 0).toFixed(2)}</td>
        `;
        
        return row;
    }

    // 更新持仓表格（增量更新版本）
    function updateHoldingsTable(holdings) {
        console.log("Updating holdings table:", holdings);
        elements.holdingsLoading.classList.add('hidden');
        elements.holdingsError.classList.add('hidden');

        if (!Array.isArray(holdings) || holdings.length === 0) {
            elements.holdingsTableBody.innerHTML = '<tr><td colspan="15" class="text-center p-4 text-gray-500">无持仓数据</td></tr>';
            return;
        }

        // 获取现有行
        const existingRows = {};
        const existingRowElements = elements.holdingsTableBody.querySelectorAll('tr[data-stock-code]');
        existingRowElements.forEach(row => {
            existingRows[row.dataset.stockCode] = row;
        });

        // 临时文档片段，减少DOM重绘
        const fragment = document.createDocumentFragment();
        
        // 记录处理过的股票代码
        const processedStocks = new Set();

        holdings.forEach(stock => {
            processedStocks.add(stock.stock_code);
            
            // 检查是否已存在此股票行
            if (existingRows[stock.stock_code]) {
                // 获取现有数据
                const oldData = existingRows[stock.stock_code].data || {};
                
                // 检查是否需要更新
                if (shouldUpdateRow(oldData, stock)) {
                    updateExistingRow(existingRows[stock.stock_code], stock);
                }
                
                // 更新存储的数据
                existingRows[stock.stock_code].data = {...stock};
            } else {
                // 创建新行
                const row = createStockRow(stock);
                // 存储数据引用
                row.data = {...stock};
                fragment.appendChild(row);
            }
        });

        // 添加新行
        elements.holdingsTableBody.appendChild(fragment);
        
        // 移除不再存在的行
        existingRowElements.forEach(row => {
            if (!processedStocks.has(row.dataset.stockCode)) {
                row.remove();
            }
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
    
        // 格式化日志内容
        if (Array.isArray(logEntries)) {
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
            elements.orderLog.value = "无可识别的日志数据";
            console.error("未知的日志数据格式:", logEntries);
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

    async function fetchHoldings() {
        // 使用延迟显示加载状态，避免短暂操作造成闪烁
        let loadingTimer = null;
        
        // 仅在加载时间超过300ms时才显示加载提示
        if (!elements.holdingsLoading.classList.contains('shown')) {
            loadingTimer = setTimeout(() => {
                elements.holdingsLoading.classList.remove('hidden');
                elements.holdingsLoading.classList.add('shown');
            }, 300);
        }
        
        try {            
            const data = await apiRequest(API_ENDPOINTS.getPositionsAll);
            
            // 取消加载提示定时器
            if (loadingTimer) clearTimeout(loadingTimer);
            
            // 检查版本是否变化
            if (data.data_version && data.data_version <= currentDataVersions.holdings) {
                console.log('Holdings data not changed, skipping update');
                elements.holdingsLoading.classList.add('hidden');
                elements.holdingsLoading.classList.remove('shown');
                return;
            }
            
            // 更新版本号
            if (data.data_version) {
                currentDataVersions.holdings = data.data_version;
            }
            
            if (data.status === 'success' && Array.isArray(data.data)) {
                updateHoldingsTable(data.data);
            } else {
                throw new Error(data.message || '数据格式错误');
            }
            
            // 2秒后隐藏加载提示，给用户足够的视觉反馈
            setTimeout(() => {
                elements.holdingsLoading.classList.add('hidden');
                elements.holdingsLoading.classList.remove('shown');
            }, 2000);
        } catch (error) {
            // 取消加载提示定时器
            if (loadingTimer) clearTimeout(loadingTimer);
            
            elements.holdingsLoading.classList.add('hidden');
            elements.holdingsLoading.classList.remove('shown');
            
            // 显示错误信息
            elements.holdingsError.classList.remove('hidden');
            elements.holdingsError.textContent = `加载失败: ${error.message}`;
            
            // 5秒后自动隐藏错误信息
            setTimeout(() => {
                elements.holdingsError.classList.add('hidden');
            }, 5000);
            
            showMessage("加载持仓数据失败", 'error');
        }
    }

    async function fetchLogs() {  
        // 使用延迟显示加载状态
        let loadingTimer = null;
        
        // 仅在加载时间超过300ms时才显示加载提示
        if (!elements.logLoading.classList.contains('shown')) {
            loadingTimer = setTimeout(() => {
                elements.logLoading.classList.remove('hidden');
                elements.logLoading.classList.add('shown');
            }, 300);
        }
        
        try {
            const data = await apiRequest(API_ENDPOINTS.getTradeRecords);
            
            // 取消加载提示定时器
            if (loadingTimer) clearTimeout(loadingTimer);
            
            if (data.status === 'success' && Array.isArray(data.data)) {
                // 更新日志内容
                updateLogs(data.data);
            } else {
                throw new Error(data.message || '数据格式错误');
            }
            
            // 2秒后隐藏加载提示
            setTimeout(() => {
                elements.logLoading.classList.add('hidden');
                elements.logLoading.classList.remove('shown');
            }, 2000);
        } catch (error) {
            // 取消加载提示定时器
            if (loadingTimer) clearTimeout(loadingTimer);
            
            elements.logLoading.classList.add('hidden');
            elements.logLoading.classList.remove('shown');
            
            // 显示错误信息
            elements.logError.classList.remove('hidden');
            elements.logError.textContent = `加载失败: ${error.message}`;
            
            // 5秒后自动隐藏错误信息
            setTimeout(() => {
                elements.logError.classList.add('hidden');
            }, 5000);
            
            showMessage("加载交易记录失败", 'error');
        }
    }

    // --- 连接状态检测 ---
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

    // 初始化持仓数据函数
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

    // --- 轮询机制 ---
    function startPolling() {
        if (pollingIntervalId) {
            clearInterval(pollingIntervalId);
        }
        
        // 设置适当的轮询间隔
        POLLING_INTERVAL = isPageActive ? ACTIVE_POLLING_INTERVAL : INACTIVE_POLLING_INTERVAL;
        
        console.log(`Starting data polling with interval: ${POLLING_INTERVAL}ms`);
        
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
        
        // 添加微妙的刷新指示，而不是明显的加载提示
        document.body.classList.add('api-refreshing');
        
        // 不再显示闪烁的加载提示
        // elements.holdingsLoading.classList.remove('hidden');
        // elements.logLoading.classList.remove('hidden');
        
        // 显示刷新状态
        showRefreshStatus();

        try {
            // 并行获取数据
            await Promise.allSettled([
                fetchStatus(), // 包含账户信息的状态
                fetchHoldings(), // 持仓数据
                fetchLogs() // 日志数据
            ]);
        } finally {
            // 移除刷新状态
            document.body.classList.remove('api-refreshing');
        }
        
        console.log("Polling cycle finished.");
    }

    // --- 浏览器性能检测 ---
    function checkBrowserPerformance() {
        // 检测帧率
        let lastTime = performance.now();
        let frames = 0;
        let fps = 0;
        
        function checkFrame() {
            frames++;
            const time = performance.now();
            
            if (time > lastTime + 1000) {
                fps = Math.round((frames * 1000) / (time - lastTime));
                console.log(`Current FPS: ${fps}`);
                
                // 根据帧率调整UI更新策略
                if (fps < 30) {
                    // 低性能模式
                    document.body.classList.add('low-performance-mode');
                    // 减少动画和视觉效果
                    POLLING_INTERVAL = Math.max(POLLING_INTERVAL, 10000); // 降低轮询频率
                    if (pollingIntervalId) {
                        stopPolling();
                        startPolling();
                    }
                } else {
                    document.body.classList.remove('low-performance-mode');
                }
                
                frames = 0;
                lastTime = time;
            }
            
            requestAnimationFrame(checkFrame);
        }
        
        requestAnimationFrame(checkFrame);
    }

    // --- SSE连接 ---
    function initSSE() {
        if (sseConnection) {
            sseConnection.close();
        }
        
        const sseURL = `${API_BASE_URL}/api/sse`;
        sseConnection = new EventSource(sseURL);
        
        sseConnection.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                console.log('SSE update received:', data);
                
                // 更新关键UI元素而不刷新整个页面
                if (data.account_info) {
                    updateQuickAccountInfo(data.account_info);
                }
                
                // 显示轻微的更新提示
                showUpdatedIndicator();
            } catch (e) {
                console.error('SSE data parse error:', e);
            }
        };
        
        sseConnection.onerror = function(error) {
            console.error('SSE connection error:', error);
            // 60秒后重试
            setTimeout(() => {
                initSSE();
            }, 60000);
        };
    }

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

        // 启动SSE
        initSSE();
        
        // 检测浏览器性能
        setTimeout(checkBrowserPerformance, 5000);
        
        // 开始API连接检查
        setTimeout(checkApiConnection, 1000);
    }

    console.log("Adding event listeners and fetching initial data...");
    fetchAllData(); // 脚本运行时加载初始数据
});

console.log("Script loaded");