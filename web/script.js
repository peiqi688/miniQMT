// script.js

document.addEventListener('DOMContentLoaded', () => {
    const positionsTableBody = document.querySelector('#positionsTable tbody');
    const loadingIndicator = document.getElementById('loadingIndicator');

    // Function to fetch and display positions
    const fetchAndDisplayPositions = async () => {
        try {
            if (loadingIndicator) {
                loadingIndicator.style.display = 'block'; // Show loading indicator
            }
            const response = await fetch('/api/positions-all');

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Data received from /api/positions-all:', data); // Inspect the data

            if (data.status === 'success') {
                positionsTableBody.innerHTML = ''; // Clear existing rows
                if (Array.isArray(data.data)) {
                    data.data.forEach(position => {
                        const row = createPositionRow(position);
                        positionsTableBody.appendChild(row);
                    });
                } else {
                    console.error('API returned data is not an array:', data.data);
                    displayErrorMessage('API returned data is not an array.');
                }
            } else {
                console.error('API returned an error:', data.message);
                displayErrorMessage(data.message);
            }
        } catch (error) {
            console.error('Error fetching or processing data:', error);
            displayErrorMessage('Failed to load data.');
        } finally {
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none'; // Hide loading indicator
            }
        }
    };

    // Function to create a table row for a position
    const createPositionRow = (position) => {
        const row = document.createElement('tr');

        const stockCodeCell = document.createElement('td');
        stockCodeCell.textContent = position.stock_code;
        row.appendChild(stockCodeCell);

        const volumeCell = document.createElement('td');
        volumeCell.textContent = position.volume;
        row.appendChild(volumeCell);

        const availableCell = document.createElement('td');
        availableCell.textContent = position.available;
        row.appendChild(availableCell);

        const costPriceCell = document.createElement('td');
        costPriceCell.textContent = position.cost_price;
        row.appendChild(costPriceCell);

        const currentPriceCell = document.createElement('td');
        currentPriceCell.textContent = position.current_price;
        row.appendChild(currentPriceCell);

        const marketValueCell = document.createElement('td');
        marketValueCell.textContent = position.market_value;
        row.appendChild(marketValueCell);

        const profitRateCell = document.createElement('td');
        profitRateCell.textContent = position.profit_ratio;
        row.appendChild(profitRateCell);

        const lastUpdateCell = document.createElement('td');
        lastUpdateCell.textContent = position.last_update;
        row.appendChild(lastUpdateCell);

        const openDateCell = document.createElement('td');
        openDateCell.textContent = position.open_date;
        row.appendChild(openDateCell);

        const takeProfitTriggerCell = document.createElement('td');
        takeProfitTriggerCell.textContent = position.profit_triggered ? '是' : '否'; // Corrected
        row.appendChild(takeProfitTriggerCell);

        const highestPriceCell = document.createElement('td');
        highestPriceCell.textContent = position.highest_price;
        row.appendChild(highestPriceCell);

        const stopLossPriceCell = document.createElement('td');
        stopLossPriceCell.textContent = isNaN(position.stop_loss_price) ? 'N/A' : position.stop_loss_price; // Handle nan
        row.appendChild(stopLossPriceCell);

        return row;
    };

    // Function to display error messages
    const displayErrorMessage = (message) => {
        const errorRow = document.createElement('tr');
        const errorCell = document.createElement('td');
        errorCell.colSpan = 12; // Span all columns
        errorCell.textContent = message;
        errorRow.appendChild(errorCell);
        positionsTableBody.appendChild(errorRow);
    };

    // Initial fetch and display
    fetchAndDisplayPositions();

    // Set up periodic updates (e.g., every 2 seconds)
    setInterval(fetchAndDisplayPositions, 2000); // Add this line
});
