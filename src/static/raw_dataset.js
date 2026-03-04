let currentOffset = 0;
let currentLimit = 100;
let currentTable = '';
let currentTotal = 0;
let currentColumns = [];
let activeFilters = {};

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

    body.innerHTML = rows.map((row) => {
        const cells = columns.map((col) => {
            const value = row[col];
            const displayValue = value === null || value === undefined ? '' : String(value);
            const className = col === 'date_time' ? ' class="datetime-column"' : '';
            return `<td${className} title="${escapeHtml(displayValue)}">${escapeHtml(displayValue)}</td>`;
        }).join('');
        return `<tr>${cells}</tr>`;
    }).join('');
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
