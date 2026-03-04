let currentOffset = 0;
let currentLimit = 100;
let currentTable = '';
let currentTotal = 0;
let currentColumns = [];
let activeFilters = {};
let currentRows = []; // Store current rows for modal access

// Table display name mapping
const TABLE_DISPLAY_NAMES = {
    "online_reviews": "Online Reviews"
};

// Column type definitions for smart filtering
const COLUMN_TYPES = {
    'rating': 'range',
    'average_rating': 'number',
    'rating_number': 'number',
    'helpful_vote': 'number',
    'num_reviews': 'number',
    'price': 'number',
    'avg_helpful_votes': 'number',
    'timestamp': 'number',
    'id': 'number',
    'title_x': 'text',
    'text': 'text',
    'asin': 'text',
    'user_id': 'text',
    'main_category': 'text',
    'title_y': 'text',
    'features': 'text',
    'store': 'text',
    'categories': 'text',
    'bought_together': 'text',
    'subtitle': 'text',
    'author': 'text',
    'os': 'text',
    'color': 'text',
    'brand': 'text'
};

function getTableDisplayName(tableName) {
    return TABLE_DISPLAY_NAMES[tableName] || tableName;
}

document.addEventListener('DOMContentLoaded', () => {
    setupDrawer();
    setupControls();
    setupModal();
    loadTables();
});

function setupDrawer() {
    const hamburgerBtn = document.getElementById('hamburgerBtn');
    const sideDrawer = document.getElementById('sideDrawer');
    const drawerBackdrop = document.getElementById('drawerBackdrop');

    hamburgerBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = sideDrawer.classList.toggle('open');
        hamburgerBtn.classList.toggle('active', isOpen);
        drawerBackdrop.classList.toggle('show', isOpen);
        sideDrawer.setAttribute('aria-hidden', String(!isOpen));
    });

    drawerBackdrop.addEventListener('click', closeDrawer);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeDrawer();
    });
}

function closeDrawer() {
    const hamburgerBtn = document.getElementById('hamburgerBtn');
    const sideDrawer = document.getElementById('sideDrawer');
    const drawerBackdrop = document.getElementById('drawerBackdrop');

    sideDrawer.classList.remove('open');
    hamburgerBtn.classList.remove('active');
    drawerBackdrop.classList.remove('show');
    sideDrawer.setAttribute('aria-hidden', 'true');
}

function setupControls() {
    document.getElementById('refreshBtn').addEventListener('click', () => {
        currentOffset = 0;
        loadTableData();
    });

    document.getElementById('tableSelect').addEventListener('change', (e) => {
        currentTable = e.target.value;
        currentOffset = 0;
        activeFilters = {};
        renderActiveFilters();
        loadTableData();
    });

    document.getElementById('rowLimit').addEventListener('change', (e) => {
        currentLimit = parseInt(e.target.value, 10);
        currentOffset = 0;
        loadTableData();
    });

    // Filter column selection
    document.getElementById('filterColumn').addEventListener('change', (e) => {
        updateFilterControls(e.target.value);
    });

    // Range sliders for rating
    document.getElementById('filterRangeMin').addEventListener('input', updateRangeDisplay);
    document.getElementById('filterRangeMax').addEventListener('input', updateRangeDisplay);

    // Apply filter button
    document.getElementById('applyFilterBtn').addEventListener('click', applyFilter);

    // Clear all filters button
    document.getElementById('clearFilterBtn').addEventListener('click', clearAllFilters);

    // Pagination
    document.getElementById('prevBtn').addEventListener('click', () => {
        if (currentOffset === 0) return;
        currentOffset = Math.max(0, currentOffset - currentLimit);
        loadTableData();
    });

    document.getElementById('nextBtn').addEventListener('click', () => {
        if (currentOffset + currentLimit >= currentTotal) return;
        currentOffset += currentLimit;
        loadTableData();
    });
}

function updateFilterControls(column) {
    const operatorGroup = document.getElementById('filterOperatorGroup');
    const valueGroup = document.getElementById('filterValueGroup');
    const rangeGroup = document.getElementById('filterRangeGroup');

    // Hide all by default
    operatorGroup.style.display = 'none';
    valueGroup.style.display = 'none';
    rangeGroup.style.display = 'none';

    if (!column) return;

    const columnType = COLUMN_TYPES[column] || 'text';

    if (columnType === 'range') {
        // Show range slider for rating
        rangeGroup.style.display = 'block';
        updateRangeDisplay();
    } else if (columnType === 'number') {
        // Show operator and number input
        operatorGroup.style.display = 'block';
        valueGroup.style.display = 'block';
        document.getElementById('filterValue').type = 'number';
        document.getElementById('filterValue').placeholder = 'Enter number...';
    } else {
        // Text search
        valueGroup.style.display = 'block';
        document.getElementById('filterValue').type = 'text';
        document.getElementById('filterValue').placeholder = 'Enter text to search...';
    }
}

function updateRangeDisplay() {
    const min = document.getElementById('filterRangeMin').value;
    const max = document.getElementById('filterRangeMax').value;
    document.getElementById('rangeValue').textContent = `${min} - ${max}`;
}

function applyFilter() {
    const column = document.getElementById('filterColumn').value;
    if (!column) return;

    const columnType = COLUMN_TYPES[column] || 'text';
    let filterValue;

    if (columnType === 'range') {
        const min = document.getElementById('filterRangeMin').value;
        const max = document.getElementById('filterRangeMax').value;
        filterValue = { min, max, type: 'range' };
    } else if (columnType === 'number') {
        const operator = document.getElementById('filterOperator').value;
        const value = document.getElementById('filterValue').value;
        if (!value) return;
        filterValue = { operator, value, type: 'number' };
    } else {
        const value = document.getElementById('filterValue').value.trim();
        if (!value) return;
        filterValue = { value, type: 'text' };
    }

    activeFilters[column] = filterValue;
    renderActiveFilters();
    currentOffset = 0;
    loadTableData();
}

function clearAllFilters() {
    activeFilters = {};
    renderActiveFilters();
    document.getElementById('filterColumn').value = '';
    updateFilterControls('');
    currentOffset = 0;
    loadTableData();
}

function removeFilter(column) {
    delete activeFilters[column];
    renderActiveFilters();
    currentOffset = 0;
    loadTableData();
}

function renderActiveFilters() {
    const container = document.getElementById('activeFilters');
    if (Object.keys(activeFilters).length === 0) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = Object.entries(activeFilters).map(([column, filter]) => {
        let displayText;
        if (filter.type === 'range') {
            displayText = `${column}: ${filter.min}-${filter.max}`;
        } else if (filter.type === 'number') {
            displayText = `${column} ${filter.operator} ${filter.value}`;
        } else {
            displayText = `${column}: "${filter.value}"`;
        }
        return `<span class="filter-chip">${escapeHtml(displayText)}<span class="filter-chip-remove" onclick="removeFilter('${escapeHtml(column)}')">×</span></span>`;
    }).join('');
}

async function loadTables() {
    let data;
    try {
        const res = await fetch('/api/raw-dataset/tables');
        data = await res.json();
    } catch (error) {
        renderTable(['status'], [{ status: 'Unable to reach dataset service.' }]);
        return;
    }

    if (data.status !== 'success') {
        renderTable(['status'], [{ status: data.message || 'Failed to load tables.' }]);
        return;
    }

    const tableSelect = document.getElementById('tableSelect');
    tableSelect.innerHTML = '';

    data.tables.forEach((tableName) => {
        const option = document.createElement('option');
        option.value = tableName;
        option.textContent = getTableDisplayName(tableName);
        tableSelect.appendChild(option);
    });

    if (data.tables.length > 0) {
        currentTable = data.tables[0];
        tableSelect.value = currentTable;
        await loadTableData();
    } else {
        tableSelect.innerHTML = '<option value="">No data table found</option>';
        document.getElementById('tableNameBadge').textContent = 'Table: --';
        document.getElementById('rowStats').textContent = 'Rows: 0 / 0';
        renderTable(['status'], [{ status: 'Online reviews dataset is not available yet.' }]);
    }
}

async function loadTableData() {
    if (!currentTable) return;

    const params = new URLSearchParams({
        table: currentTable,
        limit: String(currentLimit),
        offset: String(currentOffset),
    });

    // Add column-specific filters
    Object.entries(activeFilters).forEach(([column, filter]) => {
        if (filter.type === 'range') {
            params.append(`filter_${column}_min`, filter.min);
            params.append(`filter_${column}_max`, filter.max);
        } else if (filter.type === 'number') {
            params.append(`filter_${column}_op`, filter.operator);
            params.append(`filter_${column}`, filter.value);
        } else {
            params.append(`filter_${column}`, filter.value);
        }
    });

    let data;
    try {
        const res = await fetch(`/api/raw-dataset/data?${params.toString()}`);
        const contentType = res.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            const responseText = await res.text();
            renderTable(['status'], [{ status: `Unexpected server response (${res.status}).` }]);
            console.error('Non-JSON response from /api/raw-dataset/data:', responseText);
            return;
        }

        data = await res.json();

        if (!res.ok) {
            renderTable(['status'], [{ status: data.message || `Request failed (${res.status}).` }]);
            return;
        }
    } catch (error) {
        renderTable(['status'], [{ status: `Failed to fetch table rows: ${error.message || 'unknown error'}` }]);
        console.error('Failed to fetch table rows:', error);
        return;
    }

    if (data.status !== 'success') {
        renderTable(['status'], [{ status: data.message || 'Failed to load data' }]);
        return;
    }

    currentTotal = data.total_rows;
    currentColumns = data.columns;
    
    // Populate filter column dropdown (only on first load or table change)
    const filterColumnSelect = document.getElementById('filterColumn');
    if (filterColumnSelect.options.length <= 1) {
        filterColumnSelect.innerHTML = '<option value="">-- Select Column --</option>';
        data.columns.forEach(col => {
            if (col !== 'timestamp') { // Exclude timestamp from manual filtering
                const option = document.createElement('option');
                option.value = col;
                option.textContent = col;
                filterColumnSelect.appendChild(option);
            }
        });
    }

    // Add Date/Time column and format timestamp
    const processedColumns = ['date_time', ...data.columns.filter(c => c !== 'timestamp')];
    const processedRows = data.rows.map(row => {
        const newRow = { ...row };
        if (row.timestamp) {
            const date = new Date(parseInt(row.timestamp));
            newRow.date_time = date.toLocaleString('en-US', { 
                year: 'numeric', 
                month: 'short', 
                day: 'numeric', 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        } else {
            newRow.date_time = '';
        }
        return newRow;
    });

    renderMeta(data);
    renderTable(processedColumns, processedRows);
    updatePagination();
}

function renderMeta(data) {
    document.getElementById('tableNameBadge').textContent = `Table: ${getTableDisplayName(data.table)}`;
    document.getElementById('rowStats').textContent = `Rows: ${data.returned_rows} / ${data.total_rows}`;
}

function renderTable(columns, rows) {
    const head = document.getElementById('datasetHead');
    const body = document.getElementById('datasetBody');

    if (!columns || columns.length === 0) {
        head.innerHTML = '';
        body.innerHTML = '<tr><td>No columns found.</td></tr>';
        return;
    }

    head.innerHTML = `<tr>${columns.map((col) => {
        const className = col === 'date_time' ? ' class="datetime-column"' : '';
        return `<th${className} title="${escapeHtml(col)}">${escapeHtml(col)}</th>`;
    }).join('')}</tr>`;

    if (!rows || rows.length === 0) {
        body.innerHTML = `<tr><td colspan="${columns.length}">No rows found for this filter.</td></tr>`;
        return;
    }

    // Store rows for modal access
    currentRows = rows;

    body.innerHTML = rows.map((row, index) => {
        const cells = columns.map((col) => {
            const value = row[col];
            const displayValue = value === null || value === undefined ? '' : String(value);
            const className = col === 'date_time' ? ' class="datetime-column"' : '';
            return `<td${className} title="${escapeHtml(displayValue)}">${escapeHtml(displayValue)}</td>`;
        }).join('');
        return `<tr data-row-index="${index}">${cells}</tr>`;
    }).join('');

    // Add click event listeners to rows
    const tableRows = body.querySelectorAll('tr[data-row-index]');
    tableRows.forEach(row => {
        row.addEventListener('click', () => {
            const rowIndex = parseInt(row.getAttribute('data-row-index'));
            openReviewModal(currentRows[rowIndex]);
        });
    });
}

function updatePagination() {
    const page = Math.floor(currentOffset / currentLimit) + 1;
    const totalPages = Math.max(1, Math.ceil(currentTotal / currentLimit));
    document.getElementById('pageInfo').textContent = `Page ${page} / ${totalPages}`;

    document.getElementById('prevBtn').disabled = currentOffset === 0;
    document.getElementById('nextBtn').disabled = currentOffset + currentLimit >= currentTotal;
}

function escapeHtml(text) {
    return text
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

// ============================================================
//  MODAL FUNCTIONS
// ============================================================

function openReviewModal(rowData) {
    const modal = document.getElementById('reviewModal');
    const modalBody = document.getElementById('modalBody');
    
    if (!rowData) return;

    // Generate modal content
    const detailsHtml = generateModalContent(rowData);
    modalBody.innerHTML = detailsHtml;
    
    // Show modal
    modal.classList.add('show');
    
    // Prevent body scroll
    document.body.style.overflow = 'hidden';
}

function closeReviewModal() {
    const modal = document.getElementById('reviewModal');
    modal.classList.remove('show');
    document.body.style.overflow = '';
}

function generateModalContent(data) {
    const grid = document.createElement('div');
    grid.className = 'detail-grid';
    
    // Iterate through all columns and create detail items
    Object.entries(data).forEach(([key, value]) => {
        // Skip null/undefined values or add them with "N/A"
        const displayValue = value === null || value === undefined ? 'N/A' : value;
        
        const item = document.createElement('div');
        item.className = 'detail-item';
        
        const label = document.createElement('span');
        label.className = 'detail-label';
        label.textContent = key.replace(/_/g, ' ').toUpperCase();
        
        const valueSpan = document.createElement('span');
        valueSpan.className = 'detail-value';
        
        // Special handling for different data types
        if (key === 'rating' || key === 'average_rating') {
            const rating = parseFloat(displayValue);
            valueSpan.className = 'detail-value rating';
            const badge = getRatingBadge(rating);
            valueSpan.innerHTML = `${rating} ${badge}`;
        } else if (key === 'date_time') {
            valueSpan.className = 'detail-value datetime-value';
            valueSpan.textContent = displayValue;
        } else if (key === 'text' || key === 'title_x' || key === 'title_y' || key === 'features') {
            // Long text fields
            const textDiv = document.createElement('div');
            textDiv.className = 'long-text';
            textDiv.textContent = displayValue;
            valueSpan.appendChild(textDiv);
        } else if (typeof displayValue === 'number' || !isNaN(displayValue)) {
            // Numbers
            valueSpan.className = 'detail-value number';
            valueSpan.textContent = displayValue;
        } else {
            // Regular text
            valueSpan.textContent = displayValue;
        }
        
        item.appendChild(label);
        item.appendChild(valueSpan);
        
        // Add copy button for ASIN, User ID, and other IDs
        if (key === 'asin' || key === 'user_id' || key === 'id') {
            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-btn';
            copyBtn.textContent = 'Copy';
            copyBtn.onclick = () => copyToClipboard(displayValue, copyBtn);
            valueSpan.appendChild(copyBtn);
        }
        
        grid.appendChild(item);
    });
    
    return grid.outerHTML;
}

function getRatingBadge(rating) {
    if (rating >= 4.5) {
        return '<span class="rating-badge excellent">Excellent</span>';
    } else if (rating >= 3.5) {
        return '<span class="rating-badge good">Good</span>';
    } else if (rating >= 2.5) {
        return '<span class="rating-badge average">Average</span>';
    } else if (rating >= 1.5) {
        return '<span class="rating-badge poor">Poor</span>';
    } else {
        return '<span class="rating-badge bad">Bad</span>';
    }
}

async function copyToClipboard(text, button) {
    const value = text === null || text === undefined ? '' : String(text);
    const originalText = button.textContent;

    const showButtonState = (label, className = '', timeout = 1600) => {
        button.textContent = label;
        if (className) {
            button.classList.add(className);
        }
        setTimeout(() => {
            button.textContent = originalText;
            button.classList.remove('copied');
        }, timeout);
    };

    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(value);
            showButtonState('Copied!', 'copied');
            return;
        }

        const tempTextArea = document.createElement('textarea');
        tempTextArea.value = value;
        tempTextArea.setAttribute('readonly', '');
        tempTextArea.style.position = 'fixed';
        tempTextArea.style.opacity = '0';
        tempTextArea.style.pointerEvents = 'none';
        document.body.appendChild(tempTextArea);
        tempTextArea.focus();
        tempTextArea.select();

        const copied = document.execCommand('copy');
        document.body.removeChild(tempTextArea);

        if (copied) {
            showButtonState('Copied!', 'copied');
        } else {
            showButtonState('Failed');
        }
    } catch (err) {
        console.error('Failed to copy:', err);
        showButtonState('Failed');
    }
}

// Setup modal event listeners
function setupModal() {
    const modal = document.getElementById('reviewModal');
    const closeBtn = document.getElementById('closeModal');
    
    // Close on button click
    if (closeBtn) {
        closeBtn.addEventListener('click', closeReviewModal);
    }
    
    // Close on backdrop click
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeReviewModal();
            }
        });
    }
    
    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal && modal.classList.contains('show')) {
            closeReviewModal();
        }
    });
}
