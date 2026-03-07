// ============================================================
//  STATE
// ============================================================

let allProducts      = [];
let currentSort      = { key: 'risk_score', dir: 'desc' };
let showAll          = false;
const TABLE_LIMIT    = 10;

// Store data so charts can be re-drawn on theme switch
let storedTrendData  = null;
let storedThemeData  = null;

let sentimentChart, volumeChart, themesChart, revenueChart;

// ============================================================
//  BOOT
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    setGreeting();

    const hasSummarySection = !!(document.getElementById('kpi-products') || document.getElementById('alerts-section'));
    const hasProductTable = !!document.getElementById('products-tbody');
    const hasTrendCharts = !!(document.getElementById('sentiment-chart') && document.getElementById('volume-chart'));

    if (hasSummarySection) loadDashboard();
    if (hasProductTable) loadProducts();
    if (hasTrendCharts) loadTrends();

    setupEventListeners();
    setupHeaderScroll();
});

// ============================================================
//  GREETING & DATE
// ============================================================

function setGreeting() {
    const now = new Date();
    const hours = now.getHours();
    
    // Determine greeting based on time
    let greeting;
    if (hours >= 2 && hours < 12) {
        greeting = 'Good Morning';
    } else if (hours >= 12 && hours < 17.5) { // 5:30 PM = 17.5 hours
        greeting = 'Good Afternoon';
    } else {
        greeting = 'Good Evening';
    }
    
    // Get day name
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const dayName = days[now.getDay()];
    
    // Get month name
    const months = ['January', 'February', 'March', 'April', 'May', 'June', 
                    'July', 'August', 'September', 'October', 'November', 'December'];
    const monthName = months[now.getMonth()];
    
    // Get day with ordinal suffix (1st, 2nd, 3rd, 4th, etc.)
    const day = now.getDate();
    const ordinal = getOrdinalSuffix(day);
    
    // Get year
    const year = now.getFullYear();
    
    // Format: "Tuesday, March 4th, 2026"
    const dateString = `${dayName}, ${monthName} ${day}${ordinal}, ${year}`;
    
    // Update the DOM
    const greetingTextEl = document.getElementById('greetingText');
    const greetingDateEl = document.getElementById('greetingDate');
    const greetingNameEl = document.getElementById('greetingName');
    
    if (greetingTextEl && greetingNameEl) {
        const userName = greetingNameEl.textContent;
        greetingTextEl.innerHTML = `${greeting}, <span id="greetingName">${userName}</span>`;
    }
    
    if (greetingDateEl) {
        greetingDateEl.textContent = dateString;
    }
}

function getOrdinalSuffix(day) {
    if (day > 3 && day < 21) return 'th';
    switch (day % 10) {
        case 1: return 'st';
        case 2: return 'nd';
        case 3: return 'rd';
        default: return 'th';
    }
}

// ============================================================
//  HEADER SCROLL BEHAVIOR
// ============================================================

let lastScrollTop = 0;

function setupHeaderScroll() {
    const header = document.querySelector('.header');
    if (!header) return;
    
    // Header now stays visible at all times (sticky behavior)
    // Auto-hide on scroll disabled for better visibility
    window.addEventListener('scroll', () => {
        // Header remains visible - no hide/show logic
        header.classList.remove('header-hide');
    });
}

function setupEventListeners() {
    // Search / filter — reset pagination on change
    const searchInput = document.getElementById('search-input');
    const filterAlert = document.getElementById('filter-alert');
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            showAll = false;
            filterAndRenderTable();
        });
    }
    if (filterAlert) {
        filterAlert.addEventListener('change', () => {
            showAll = false;
            filterAndRenderTable();
        });
    }

    // Sortable column headers
    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const key = th.dataset.sort;
            currentSort = (currentSort.key === key)
                ? { key, dir: currentSort.dir === 'desc' ? 'asc' : 'desc' }
                : { key, dir: 'desc' };
            document.querySelectorAll('th').forEach(h => h.classList.remove('active-sort'));
            th.classList.add('active-sort');
            filterAndRenderTable();
        });
    });

    // Modal close
    const modalClose = document.getElementById('modal-close');
    const productModal = document.getElementById('product-modal');
    if (modalClose) {
        modalClose.addEventListener('click', closeModal);
    }
    if (productModal) {
        productModal.addEventListener('click', e => {
            if (e.target === e.currentTarget) closeModal();
        });
    }

    // Profile dropdown
    const profileButton = document.getElementById('profileButton');
    const editProfileBtn = document.getElementById('editProfileBtn');
    if (profileButton) {
        profileButton.addEventListener('click', toggleProfileMenu);
    }
    if (editProfileBtn) {
        editProfileBtn.addEventListener('click', (e) => {
            e.preventDefault();
            openProfileEditModal();
        });
    }
    
    // Profile modal
    const profileModalClose = document.getElementById('profile-modal-close');
    const cancelEditBtn = document.getElementById('cancelEditBtn');
    const profileEditForm = document.getElementById('profileEditForm');
    const profileModal = document.getElementById('profile-modal');
    if (profileModalClose) profileModalClose.addEventListener('click', closeProfileModal);
    if (cancelEditBtn) cancelEditBtn.addEventListener('click', closeProfileModal);
    if (profileEditForm) profileEditForm.addEventListener('submit', saveProfile);
    if (profileModal) {
        profileModal.addEventListener('click', e => {
            if (e.target === e.currentTarget) closeProfileModal();
        });
    }
    
    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        const dropdown = document.querySelector('.profile-dropdown');
        if (dropdown && !dropdown.contains(e.target)) {
            document.getElementById('profileMenu').classList.remove('show');
            document.getElementById('profileButton').classList.remove('active');
        }
    });

    // AI Assistant - Enable/Disable button based on input
    const aiInput = document.getElementById('chatbot-input');
    const aiBtn = document.getElementById('chatbot-btn');
    
    if (aiInput && aiBtn) {
        aiInput.addEventListener('input', () => {
            aiBtn.disabled = aiInput.value.trim() === '';
        });
    }

    // Show-more / show-less
    const showMoreBtn = document.getElementById('show-more-btn');
    if (showMoreBtn) {
        showMoreBtn.addEventListener('click', () => {
            showAll = !showAll;
            filterAndRenderTable();
        });
    }

    // Theme toggle
    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) themeToggleBtn.addEventListener('click', toggleTheme);

    // Side drawer
    const hamburgerBtn = document.getElementById('hamburgerBtn');
    const sideDrawer = document.getElementById('sideDrawer');
    const drawerBackdrop = document.getElementById('drawerBackdrop');

    if (hamburgerBtn && sideDrawer && drawerBackdrop) {
        hamburgerBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = sideDrawer.classList.toggle('open');
            hamburgerBtn.classList.toggle('active', isOpen);
            drawerBackdrop.classList.toggle('show', isOpen);
            sideDrawer.setAttribute('aria-hidden', String(!isOpen));
        });

        drawerBackdrop.addEventListener('click', closeSideDrawer);
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeSideDrawer();
        }
    });
}

function closeSideDrawer() {
    const hamburgerBtn = document.getElementById('hamburgerBtn');
    const sideDrawer = document.getElementById('sideDrawer');
    const drawerBackdrop = document.getElementById('drawerBackdrop');
    if (!hamburgerBtn || !sideDrawer || !drawerBackdrop) return;

    sideDrawer.classList.remove('open');
    hamburgerBtn.classList.remove('active');
    drawerBackdrop.classList.remove('show');
    sideDrawer.setAttribute('aria-hidden', 'true');
}

// ============================================================
//  THEME  (dark/light)
// ============================================================

function initTheme() {
    const saved = localStorage.getItem('fusiontech-theme');
    if (saved === 'light') {
        document.body.classList.add('light-mode');
    }
    syncThemeButton();
}

function toggleTheme() {
    document.body.classList.toggle('light-mode');
    const isLight = document.body.classList.contains('light-mode');
    localStorage.setItem('fusiontech-theme', isLight ? 'light' : 'dark');
    syncThemeButton();

    // Re-draw all charts with the updated colour palette
    if (storedTrendData)  { renderSentimentChart(storedTrendData); renderVolumeChart(storedTrendData); }
    if (storedThemeData)  { renderThemesChart(storedThemeData); }
    filterAndRenderTable(); // also re-draws the revenue chart
}

function syncThemeButton() {
    const isLight = document.body.classList.contains('light-mode');
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    btn.innerHTML = isLight ? '&#127769; Dark Mode' : '&#9728;&#65039; Light Mode';
    btn.title     = isLight ? 'Switch to dark mode' : 'Switch to light mode';
}

// Helper: returns chart-friendly colours for the current theme
function chartColors() {
    const light = document.body.classList.contains('light-mode');
    return {
        text:   light ? '#64748b' : '#78909c',
        legend: light ? '#334155' : '#b0bec5',
        grid:   light ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.05)',
    };
}

// ============================================================
//  PROFILE MANAGEMENT
// ============================================================

function toggleProfileMenu() {
    const menu = document.getElementById('profileMenu');
    const button = document.getElementById('profileButton');
    if (!menu || !button) return;
    menu.classList.toggle('show');
    button.classList.toggle('active');
}

async function openProfileEditModal() {
    const profileMenu = document.getElementById('profileMenu');
    const profileButton = document.getElementById('profileButton');
    const profileModal = document.getElementById('profile-modal');
    if (!profileMenu || !profileButton || !profileModal) return;

    // Close dropdown
    profileMenu.classList.remove('show');
    profileButton.classList.remove('active');
    
    // Clear password fields
    const editNewPassword = document.getElementById('editNewPassword');
    const editConfirmPassword = document.getElementById('editConfirmPassword');
    const editCurrentPassword = document.getElementById('editCurrentPassword');
    const editNewPasswordError = document.getElementById('editNewPasswordError');
    const editConfirmPasswordError = document.getElementById('editConfirmPasswordError');
    const editCurrentPasswordError = document.getElementById('editCurrentPasswordError');

    if (editNewPassword) editNewPassword.value = '';
    if (editConfirmPassword) editConfirmPassword.value = '';
    if (editCurrentPassword) editCurrentPassword.value = '';
    if (editNewPasswordError) editNewPasswordError.style.display = 'none';
    if (editConfirmPasswordError) editConfirmPasswordError.style.display = 'none';
    if (editCurrentPasswordError) editCurrentPasswordError.style.display = 'none';
    
    // Load departments
    try {
        const response = await fetch('/api/departments');
        const data = await response.json();
        
        if (data.status === 'success') {
            const select = document.getElementById('editDepartment');
            if (!select) return;
            select.innerHTML = '<option value="">Select Department</option>';
            const enabledDepartments = ['Engineering & IT', 'Marketing', 'Sales'];
            
            data.departments.forEach(dept => {
                const option = document.createElement('option');
                option.value = dept.department_code;
                
                const isEnabled = enabledDepartments.includes(dept.department_name);
                
                if (isEnabled) {
                    option.textContent = dept.department_name;
                } else {
                    option.textContent = dept.department_name + ' (beta)';
                    option.disabled = true;
                }
                
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Failed to load departments:', error);
    }
    
    // Load current user profile
    try {
        const response = await fetch('/api/profile');
        const data = await response.json();
        
        if (data.status === 'success') {
            const user = data.user;
            const editFirstName = document.getElementById('editFirstName');
            const editLastName = document.getElementById('editLastName');
            const editDepartment = document.getElementById('editDepartment');
            const editLocation = document.getElementById('editLocation');

            if (editFirstName) editFirstName.value = user.first_name || '';
            if (editLastName) editLastName.value = user.last_name || '';
            if (editDepartment) editDepartment.value = user.department || '';
            if (editLocation) editLocation.value = user.location || '';
        }
    } catch (error) {
        console.error('Failed to load profile:', error);
    }
    
    // Show modal
    profileModal.style.display = 'flex';
}

function closeProfileModal() {
    const profileModal = document.getElementById('profile-modal');
    if (!profileModal) return;
    profileModal.style.display = 'none';
    // Clear password fields
    const editNewPassword = document.getElementById('editNewPassword');
    const editConfirmPassword = document.getElementById('editConfirmPassword');
    const editCurrentPassword = document.getElementById('editCurrentPassword');
    const editNewPasswordError = document.getElementById('editNewPasswordError');
    const editConfirmPasswordError = document.getElementById('editConfirmPasswordError');
    const editCurrentPasswordError = document.getElementById('editCurrentPasswordError');

    if (editNewPassword) editNewPassword.value = '';
    if (editConfirmPassword) editConfirmPassword.value = '';
    if (editCurrentPassword) editCurrentPassword.value = '';
    if (editNewPasswordError) editNewPasswordError.style.display = 'none';
    if (editConfirmPasswordError) editConfirmPasswordError.style.display = 'none';
    if (editCurrentPasswordError) editCurrentPasswordError.style.display = 'none';
}

async function saveProfile(e) {
    e.preventDefault();
    
    // Get form values
    const formData = {
        first_name: document.getElementById('editFirstName').value.trim(),
        last_name: document.getElementById('editLastName').value.trim(),
        department: document.getElementById('editDepartment').value,
        location: document.getElementById('editLocation').value.trim() || null,
    };
    
    // Get password change fields
    const newPassword = document.getElementById('editNewPassword').value;
    const confirmPassword = document.getElementById('editConfirmPassword').value;
    const currentPassword = document.getElementById('editCurrentPassword').value;
    
    // Clear previous errors
    document.getElementById('editNewPasswordError').style.display = 'none';
    document.getElementById('editConfirmPasswordError').style.display = 'none';
    document.getElementById('editCurrentPasswordError').style.display = 'none';
    
    // Validate password change if new password is provided
    let hasPasswordError = false;
    if (newPassword || confirmPassword || currentPassword) {
        if (!newPassword) {
            showPasswordError('editNewPassword', 'New password is required');
            hasPasswordError = true;
        } else if (newPassword.length < 8) {
            showPasswordError('editNewPassword', 'Password must be at least 8 characters');
            hasPasswordError = true;
        }
        
        if (!confirmPassword) {
            showPasswordError('editConfirmPassword', 'Please confirm new password');
            hasPasswordError = true;
        } else if (newPassword !== confirmPassword) {
            showPasswordError('editConfirmPassword', 'Passwords do not match');
            hasPasswordError = true;
        }
        
        if (!currentPassword) {
            showPasswordError('editCurrentPassword', 'Current password is required to change password');
            hasPasswordError = true;
        }
        
        if (hasPasswordError) return;
        
        // Add password change to form data
        formData.new_password = newPassword;
        formData.current_password = currentPassword;
    }
    
    try {
        const response = await fetch('/api/profile', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            // Update UI
            document.getElementById('profileName').textContent = formData.first_name;
            document.getElementById('menuUserName').textContent = `${formData.first_name} ${formData.last_name}`;
            document.getElementById('menuUserDept').textContent = formData.department;
            
            closeProfileModal();
            alert('Profile updated successfully!');
        } else {
            // Show errors
            if (data.message === 'Invalid current password') {
                showPasswordError('editCurrentPassword', 'Current password is incorrect');
            } else if (data.message && data.message.includes('password')) {
                showPasswordError('editNewPassword', data.message);
            } else {
                alert(data.message || 'Failed to update profile');
            }
        }
    } catch (error) {
        console.error('Failed to save profile:', error);
        alert('Connection error. Please try again.');
    }
}

function showPasswordError(fieldId, message) {
    const errorDiv = document.getElementById(fieldId + 'Error');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }
}

// ============================================================
//  DATA LOADING
// ============================================================

async function loadDashboard() {
    try {
        const data = await fetchJSON('/api/dashboard');
        if (!data || data.status !== 'success') return;

        const s = data.summary;
        setText('kpi-products', s.products_scored);
        setText('kpi-critical', s.critical_alerts + s.high_alerts);
        setText('kpi-revenue',  s.total_monthly_revenue_at_risk_formatted);
        setText('kpi-reviews',  s.total_reviews_analyzed.toLocaleString());

        const alertsSection = document.getElementById('alerts-section');
        const alertsContainer = document.getElementById('alerts-container');
        if (alertsSection && alertsContainer && data.alerts && data.alerts.length > 0) {
            alertsSection.style.display = 'block';
            alertsContainer.innerHTML = data.alerts.slice(0, 5).map(a => `
                <div class="alert-item ${a.alert_level}">
                    <span class="alert-badge badge-${a.alert_level}">${a.alert_level}</span>
                    <span>
                        <strong>${esc(a.product_name.substring(0, 65))}</strong> &mdash;
                        Risk Score: <strong>${a.risk_score}</strong> &nbsp;|&nbsp;
                        Issues: ${a.top_themes.join(', ') || 'N/A'}
                    </span>
                </div>
            `).join('');
        }
    } catch (e) { console.error('loadDashboard:', e); }
}

async function loadProducts() {
    try {
        const data = await fetchJSON('/api/products');
        if (!data || data.status !== 'success') return;
        allProducts = data.products;
        filterAndRenderTable();
    } catch (e) { console.error('loadProducts:', e); }
}

async function loadTrends() {
    try {
        const data = await fetchJSON('/api/trends');
        if (!data || data.status !== 'success') return;
        storedTrendData = data.trends.sentiment_over_time;
        storedThemeData = data.trends.global_themes;
        renderSentimentChart(storedTrendData);
        renderVolumeChart(storedTrendData);
        renderThemesChart(storedThemeData);
    } catch (e) { console.error('loadTrends:', e); }
}

// ============================================================
//  TABLE  (with show-more pagination)
// ============================================================

function filterAndRenderTable() {
    const searchInput = document.getElementById('search-input');
    const filterAlertSelect = document.getElementById('filter-alert');
    const productsTbody = document.getElementById('products-tbody');
    const showMoreButton = document.getElementById('show-more-btn');
    const tableCount = document.getElementById('table-count');
    if (!searchInput || !filterAlertSelect || !productsTbody || !showMoreButton || !tableCount) return;

    const search = searchInput.value.toLowerCase();
    const alertFilter = filterAlertSelect.value;

    let filtered = allProducts.filter(p => {
        const nameMatch  = !search || p.product_name.toLowerCase().includes(search) || p.asin.toLowerCase().includes(search);
        const levelMatch = alertFilter === 'all' || p.alert_level === alertFilter;
        return nameMatch && levelMatch;
    });

    // Sort
    filtered.sort((a, b) => {
        let va = a[currentSort.key];
        let vb = b[currentSort.key];
        if (currentSort.key === 'revenue') {
            va = (a.revenue_impact || {}).monthly_revenue_at_risk || 0;
            vb = (b.revenue_impact || {}).monthly_revenue_at_risk || 0;
        }
        if (va == null) va = -Infinity;
        if (vb == null) vb = -Infinity;
        return typeof va === 'string'
            ? (currentSort.dir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va))
            : (currentSort.dir === 'asc' ? va - vb : vb - va);
    });

    // Paginate
    const visible = showAll ? filtered : filtered.slice(0, TABLE_LIMIT);

    productsTbody.innerHTML = visible.map((p, i) => {
        const score   = p.risk_score != null ? p.risk_score : '--';
        const color   = scoreColor(p.risk_score);
        const themes  = (p.top_themes || []).map(t => `<span class="theme-tag">${titleCase(t)}</span>`).join('');
        const revenue = p.revenue_impact ? fmtCurrency(p.revenue_impact.monthly_revenue_at_risk) : '--';
        const rating  = p.average_rating != null ? Number(p.average_rating).toFixed(1) + ' &#9733;' : '--';
        const name    = esc(p.product_name);
        const shortName = p.product_name.length > 54
            ? esc(p.product_name.substring(0, 54)) + '&hellip;'
            : name;

        return `
            <tr onclick="openProductDetail('${p.asin}')">
                <td style="color:var(--text-muted);font-size:0.82rem">${i + 1}</td>
                <td title="${name}" style="font-weight:500">${shortName}</td>
                <td class="risk-score-cell" style="color:${color}">${score}</td>
                <td><span class="alert-badge badge-${p.alert_level}">${p.alert_level}</span></td>
                <td>${themes || '<span style="color:var(--text-muted)">&#8212;</span>'}</td>
                <td style="color:var(--text-muted)">${p.review_count}</td>
                <td style="color:var(--text-muted)">${rating}</td>
                <td style="color:#fb8c00;font-weight:700">${revenue}</td>
            </tr>`;
    }).join('');

    // Show-more button
    const btn        = showMoreButton;
    const countLabel = tableCount;
    const total      = filtered.length;

    if (total <= TABLE_LIMIT) {
        btn.style.display = 'none';
    } else {
        btn.style.display = 'inline-block';
        btn.textContent   = showAll
            ? '&#8593; Show Less'
            : `Show ${total - TABLE_LIMIT} More Products \u2193`;
    }
    countLabel.textContent = `Showing ${visible.length} of ${total} products`;

    // Revenue chart always uses the full filtered set (not just visible rows)
    const top10 = filtered.filter(p => p.risk_score != null).slice(0, 10);
    renderRevenueChart(top10);
}

// ============================================================
//  PRODUCT DETAIL MODAL
// ============================================================

async function openProductDetail(asin) {
    const modalTitle = document.getElementById('modal-title');
    const modalBody = document.getElementById('modal-body');
    const productModal = document.getElementById('product-modal');
    if (!modalTitle || !modalBody || !productModal) return;

    try {
        const data = await fetchJSON(`/api/products/${asin}`);
        if (!data || data.status !== 'success') return;

        const p      = data.product;
        const impact = p.revenue_impact || {};
        const color  = scoreColor(p.risk_score);

        modalTitle.textContent = p.product_name;

        // Sub-score friendly names
        const subNames = {
            negative_sentiment_ratio: 'Negative Reviews',
            sentiment_velocity:       'Mood Getting Worse',
            rating_decline:           'Star Rating Dropping',
            low_rating_spike:         '1-Star Review Spike',
            complaint_concentration:  'Repeated Same Complaint',
            community_validated:      'Many People Agree',
        };

        const subBars = Object.entries(p.sub_scores || {}).map(([k, v]) => {
            const barColor = v >= 75 ? '#ef5350' : v >= 50 ? '#fb8c00' : v >= 25 ? '#f9a825' : '#43a047';
            return `
                <div class="sub-score-bar">
                    <span class="sub-score-label">${subNames[k] || k}</span>
                    <div class="sub-score-track">
                        <div class="sub-score-fill" style="width:${v}%;background:${barColor}"></div>
                    </div>
                    <span class="sub-score-value">${v}</span>
                </div>`;
        }).join('');

        // Rating distribution
        const dist    = p.rating_distribution || {};
        const maxVal  = Math.max(...Object.values(dist).map(Number), 1);
        const ratingBars = [5,4,3,2,1].map(r => {
            const count    = dist[String(r)] || 0;
            const barColor = r >= 4 ? '#43a047' : r === 3 ? '#f9a825' : '#ef5350';
            return `
                <div class="sub-score-bar">
                    <span class="sub-score-label" style="width:55px">${r} star</span>
                    <div class="sub-score-track">
                        <div class="sub-score-fill" style="width:${(count/maxVal)*100}%;background:${barColor}"></div>
                    </div>
                    <span class="sub-score-value">${count}</span>
                </div>`;
        }).join('');

        // Complaint themes
        const themeTags = (p.top_themes || []).map(t =>
            `<span class="theme-tag" style="font-size:0.83rem;padding:0.3rem 0.8rem">
                ${titleCase(t.theme)} &mdash; ${(t.frequency * 100).toFixed(0)}% of reviews
             </span>`
        ).join(' ') || '<span style="color:var(--text-muted)">No complaint themes detected</span>';

        // Recent negative reviews
        const negHtml = (p.recent_negative_reviews || []).map(r => `
            <div class="neg-review-item">
                <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:0.4rem;margin-bottom:0.2rem">
                    <strong style="color:#ef5350">${esc(r.title || 'Untitled')}</strong>
                    <span style="color:var(--text-muted);font-size:0.78rem">
                        ${r.date} &nbsp;|&nbsp; ${r.rating} &#9733; &nbsp;|&nbsp; ${r.helpful_votes} found helpful
                    </span>
                </div>
            </div>`
        ).join('') || '<p style="color:var(--text-muted)">No recent negative reviews found.</p>';

        modalBody.innerHTML = `
            <!-- Header row: score + summary -->
            <div style="display:flex;align-items:flex-start;gap:1.5rem;margin:1rem 0 0;flex-wrap:wrap">
                <div style="text-align:center;min-width:90px">
                    <div style="font-size:2.8rem;font-weight:900;color:${color};line-height:1">
                        ${p.risk_score ?? '--'}
                    </div>
                    <div style="font-size:0.68rem;color:var(--text-muted);margin:0.15rem 0">out of 100</div>
                    <span class="alert-badge badge-${p.alert_level}">${p.alert_level}</span>
                </div>
                <div style="flex:1;min-width:200px">
                    <p style="font-size:0.88rem;margin-bottom:0.4rem">
                        <strong>${p.review_count}</strong> reviews &nbsp;|&nbsp;
                        Avg rating: <strong>${p.average_rating ?? '--'} &#9733;</strong> &nbsp;|&nbsp;
                        Price: <strong>${p.price ? '$' + p.price : 'N/A'}</strong>
                    </p>
                    <p style="color:#fb8c00;font-size:0.88rem">
                        &#128176; Monthly revenue at risk: <strong>${fmtCurrency(impact.monthly_revenue_at_risk || 0)}</strong>
                        &nbsp;&nbsp; Annual: <strong>${fmtCurrency(impact.annualized_revenue_at_risk || 0)}</strong>
                    </p>
                </div>
            </div>

            <div class="detail-grid">
                <div class="detail-card">
                    <h4>&#128300; What is driving the risk score?</h4>
                    ${subBars}
                </div>
                <div class="detail-card">
                    <h4>&#11088; Star rating breakdown</h4>
                    ${ratingBars}
                </div>
            </div>

            <div class="detail-card" style="margin-top:1rem">
                <h4>&#128172; Main complaint topics</h4>
                <div style="margin-top:0.5rem;line-height:1.9">${themeTags}</div>
            </div>

            <div class="detail-card" style="margin-top:1rem">
                <h4>&#128203; Recent negative reviews</h4>
                ${negHtml}
            </div>`;

        productModal.style.display = 'flex';
    } catch (e) { console.error('openProductDetail:', e); }
}

function closeModal() {
    const productModal = document.getElementById('product-modal');
    if (productModal) productModal.style.display = 'none';
}

// ============================================================
//  CHARTS
// ============================================================

function baseOptions(yAxisLabel) {
    const c = chartColors();
    return {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: { labels: { color: c.legend, font: { size: 11 }, padding: 14 } },
        },
        scales: {
            x: {
                ticks: { color: c.text, font: { size: 10 }, maxRotation: 40 },
                grid:  { color: c.grid },
            },
            y: {
                ticks: { color: c.text, font: { size: 10 } },
                grid:  { color: c.grid },
                title: {
                    display: !!yAxisLabel,
                    text: yAxisLabel || '',
                    color: c.text,
                    font: { size: 10 },
                },
            },
        },
    };
}

// Chart 1 — Customer happiness over time
function renderSentimentChart(data) {
    const canvas = document.getElementById('sentiment-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (sentimentChart) sentimentChart.destroy();
    const c   = chartColors();
    const opt = baseOptions(null);

    sentimentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.month),
            datasets: [
                {
                    label: 'Happiness Score',
                    data:  data.map(d => +d.avg_sentiment.toFixed(3)),
                    borderColor: '#42a5f5',
                    backgroundColor: 'rgba(66,165,245,0.1)',
                    fill: true, tension: 0.35, pointRadius: 3,
                },
                {
                    label: 'Unhappy Reviews %',
                    data:  data.map(d => +(d.negative_ratio * 100).toFixed(1)),
                    borderColor: '#ef5350',
                    backgroundColor: 'rgba(239,83,80,0.08)',
                    fill: true, tension: 0.35, pointRadius: 3,
                    yAxisID: 'y2',
                },
            ],
        },
        options: {
            ...opt,
            plugins: {
                legend: { labels: { color: c.legend, font: { size: 11 }, padding: 14 } },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            if (ctx.dataset.label === 'Happiness Score') {
                                const v = ctx.raw;
                                const mood = v > 0.2 ? 'Mostly positive' : v > -0.2 ? 'Mixed' : 'Mostly negative';
                                return ` Happiness: ${v} (${mood})`;
                            }
                            return ` Unhappy Reviews: ${ctx.raw}%`;
                        },
                    },
                },
            },
            scales: {
                ...opt.scales,
                y:  { ...opt.scales.y, title: { display: true, text: 'Happiness Score', color: c.text, font: { size: 10 } } },
                y2: {
                    position: 'right',
                    ticks: { color: c.text, font: { size: 10 }, callback: v => v + '%' },
                    grid: { drawOnChartArea: false },
                    title: { display: true, text: 'Unhappy Reviews %', color: c.text, font: { size: 10 } },
                },
            },
        },
    });
}

// Chart 2 — Review volume
function renderVolumeChart(data) {
    const canvas = document.getElementById('volume-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (volumeChart) volumeChart.destroy();
    const c = chartColors();

    volumeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.month),
            datasets: [{
                label: 'Reviews That Month',
                data:  data.map(d => d.review_count),
                backgroundColor: 'rgba(66,165,245,0.55)',
                borderColor: '#42a5f5',
                borderWidth: 1,
                borderRadius: 4,
            }],
        },
        options: {
            ...baseOptions('Number of Reviews'),
            plugins: {
                legend: { labels: { color: c.legend, font: { size: 11 }, padding: 14 } },
                tooltip: { callbacks: { label: ctx => ` ${ctx.raw} reviews received that month` } },
            },
        },
    });
}

// Chart 3 — Top complaint themes (horizontal)
function renderThemesChart(themes) {
    const canvas = document.getElementById('themes-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (themesChart) themesChart.destroy();
    const c = chartColors();

    const entries = Object.entries(themes).slice(0, 10);
    const palette = ['#ef5350','#fb8c00','#f9a825','#43a047','#42a5f5','#ab47bc','#ec407a','#26c6da','#8d6e63','#78909c'];

    themesChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: entries.map(e => titleCase(e[0])),
            datasets: [{
                label: 'Number of Mentions',
                data:  entries.map(e => e[1]),
                backgroundColor: entries.map((_, i) => palette[i % palette.length]),
                borderRadius: 4,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: ctx => ` ${ctx.raw} negative reviews mention this` } },
            },
            scales: {
                x: {
                    ticks: { color: c.text, font: { size: 10 } },
                    grid:  { color: c.grid },
                    title: { display: true, text: 'Number of Mentions', color: c.text, font: { size: 10 } },
                },
                y: {
                    ticks: { color: c.text, font: { size: 10 } },
                    grid:  { color: c.grid },
                },
            },
        },
    });
}

// Chart 4 — Revenue at risk (horizontal, top 10)
function renderRevenueChart(products) {
    const canvas = document.getElementById('revenue-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (revenueChart) revenueChart.destroy();
    const c = chartColors();

    const items = products
        .filter(p => p.revenue_impact && p.revenue_impact.monthly_revenue_at_risk > 0)
        .slice(0, 10);

    revenueChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: items.map(p => p.product_name.length > 28
                ? p.product_name.substring(0, 28) + '\u2026'
                : p.product_name),
            datasets: [{
                label: 'Monthly Revenue at Risk',
                data:  items.map(p => p.revenue_impact.monthly_revenue_at_risk),
                backgroundColor: 'rgba(251,140,0,0.65)',
                borderColor: '#fb8c00',
                borderWidth: 1,
                borderRadius: 4,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: ctx => ` ${fmtCurrency(ctx.raw)} at risk this month` } },
            },
            scales: {
                x: {
                    ticks: { color: c.text, font: { size: 10 }, callback: v => fmtCurrency(v) },
                    grid:  { color: c.grid },
                },
                y: {
                    ticks: { color: c.text, font: { size: 9 } },
                    grid:  { color: c.grid },
                },
            },
        },
    });
}

// ============================================================
//  HELPERS
// ============================================================

async function fetchJSON(url) {
    const res = await fetch(url);
    return res.json();
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function esc(str) {
    return String(str)
        .replace(/&/g,'&amp;')
        .replace(/</g,'&lt;')
        .replace(/>/g,'&gt;')
        .replace(/"/g,'&quot;');
}

function titleCase(str) {
    return String(str).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function scoreColor(score) {
    if (score == null) return 'var(--text-muted)';
    if (score >= 75) return '#ef5350';
    if (score >= 50) return '#fb8c00';
    if (score >= 25) return '#f9a825';
    return '#43a047';
}

function alertColor(level) {
    return { CRITICAL:'#ef5350', HIGH:'#fb8c00', MODERATE:'#f9a825', LOW:'#43a047' }[level] || 'var(--accent)';
}

function fmtCurrency(amount) {
    if (!amount) return '$0';
    if (Math.abs(amount) >= 1e6) return `$${(amount / 1e6).toFixed(1)}M`;
    if (Math.abs(amount) >= 1e3) return `$${(amount / 1e3).toFixed(0)}K`;
    return `$${amount.toFixed(0)}`;
}
