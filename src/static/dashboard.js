
// ============================================================
//  STATE
// ============================================================

let allProducts      = [];
let currentSort      = { key: 'risk_score', dir: 'desc' };
let showAll          = false;
let tableLimit       = 10;
let alertPreviewLimit = 5;
let riskThresholds   = { critical: 75, high: 50, moderate: 25 };

// Store data so charts can be re-drawn on theme switch
let storedTrendData  = null;
let storedThemeData  = null;

let sentimentChart, volumeChart, themesChart, revenueChart;
let isSendingChat = false;
const CHAT_TYPING_ID = 'chatbot-typing-indicator';
let chatConversationStarted = false;

// ====== GLOBAL for alert modal ======
let dashboardAlerts = [];
let currentAlertIndex = 0;

// ============================================================
//  DASHBOARD LOADING
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    setGreeting();

    const hasSummarySection = !!(document.getElementById('kpi-products') || document.getElementById('alerts-section'));
    const hasProductTable = !!document.getElementById('products-tbody');
    const hasTrendCharts = !!(document.getElementById('sentiment-chart') && document.getElementById('volume-chart'));

    if (hasSummarySection) loadDashboard();
    setupAlertModal();
    if (hasProductTable) loadProducts();
    if (hasTrendCharts) loadTrends();

    setupEventListeners();
    setupHeaderScroll();
    setupChatbotPopup();
});
// ================= CHATBOT POPUP LOGIC ===================
function setupChatbotPopup() {
    const floatBtn = document.getElementById('chatbot-float-btn');
    const popup = document.getElementById('chatbot-popup');
    const closeBtn = document.getElementById('chatbot-popup-close');
    const expandBtn = document.getElementById('chatbot-popup-expand');
    if (!floatBtn || !popup || !closeBtn || !expandBtn) return;

    floatBtn.addEventListener('click', () => {
        popup.classList.remove('chat-hidden');
        floatBtn.style.display = 'none';
    });

    closeBtn.addEventListener('click', () => {
        popup.classList.add('chat-hidden');
        floatBtn.style.display = 'flex';
        popup.classList.remove('expanded');
        expandBtn.innerHTML = '⤢';
    });

    expandBtn.addEventListener('click', () => {
        popup.classList.toggle('expanded');
        if (popup.classList.contains('expanded')) {
            expandBtn.innerHTML = '⤡'; // collapse icon
        } else {
            expandBtn.innerHTML = '⤢'; // expand icon
        }
    });

    // Optional: close popup if user clicks outside
    document.addEventListener('mousedown', (e) => {
        if (!popup.classList.contains('chat-hidden') && !popup.contains(e.target) && e.target !== floatBtn) {
            popup.classList.add('chat-hidden');
            floatBtn.style.display = 'flex';
            popup.classList.remove('expanded');
            expandBtn.innerHTML = '⤢';
        }
    });
}

// ================= ALERT MODAL FOR KPI CRITICAL CARD ===================
function setupAlertModal() {
    // Open modal on KPI card click
    const kpiCritical = document.querySelector('.kpi-card.kpi-critical');
    if (kpiCritical) {
        kpiCritical.addEventListener('click', () => {
            if (dashboardAlerts.length > 0) {
                currentAlertIndex = 0;
                showAlertModal(currentAlertIndex);
            }
        });
    }
    // Modal close
    const alertModal = document.getElementById('alert-modal');
    const alertModalClose = document.getElementById('alert-modal-close');
    if (alertModalClose) {
        alertModalClose.addEventListener('click', () => {
            alertModal.style.display = 'none';
        });
    }
    // Prev/Next
    const prevBtn = document.getElementById('alert-modal-prev');
    const nextBtn = document.getElementById('alert-modal-next');
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (dashboardAlerts.length > 0) {
                currentAlertIndex = (currentAlertIndex - 1 + dashboardAlerts.length) % dashboardAlerts.length;
                showAlertModal(currentAlertIndex);
            }
        });
    }
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            if (dashboardAlerts.length > 0) {
                currentAlertIndex = (currentAlertIndex + 1) % dashboardAlerts.length;
                showAlertModal(currentAlertIndex);
            }
        });
    }
}


// Shared modal rendering for both product and alert modals
async function renderProductDetailModal(asin, modalId, titleId, bodyId) {
    const modalTitle = document.getElementById(titleId);
    const modalBody = document.getElementById(bodyId);
    const modal = document.getElementById(modalId);
    if (!modalTitle || !modalBody || !modal) return;

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
            const barColor = scoreColor(v);
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

        modal.style.display = 'flex';
    } catch (e) { console.error('renderProductDetailModal:', e); }
}

// Update: showAlertModal now uses the shared renderer for alert modal
function showAlertModal(idx) {
    const alert = dashboardAlerts[idx];
    if (!alert) return;
    renderProductDetailModal(alert.asin, 'alert-modal', 'alert-modal-title', 'alert-modal-body');
}

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
            aiBtn.disabled = aiInput.value.trim() === '' || isSendingChat;
        });

        aiBtn.addEventListener('click', sendChatMessage);
        aiInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendChatMessage();
            }
        });

        document.querySelectorAll('.chat-starter-item').forEach((starter) => {
            starter.addEventListener('click', () => {
                aiInput.value = starter.textContent.trim();
                aiBtn.disabled = aiInput.value.trim() === '' || isSendingChat;
                sendChatMessage();
            });
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
            
            data.departments.forEach(dept => {
                const option = document.createElement('option');
                option.value = dept.department_code;
                
                const isEnabled = dept.is_enabled !== false;
                
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

        const ui = data.ui_defaults || {};
        const thresholds = data.risk_thresholds || {};
        tableLimit = Number(ui.dashboard_table_limit) || 10;
        alertPreviewLimit = Number(ui.dashboard_alert_preview_limit) || 5;
        riskThresholds = {
            critical: Number(thresholds.critical) || 75,
            high: Number(thresholds.high) || 50,
            moderate: Number(thresholds.moderate) || 25,
        };

        const s = data.summary;

        setText('kpi-products', s.products_scored);
        const alertCount = s.critical_alerts + s.high_alerts;
        setText('kpi-critical', alertCount);
        setText('kpi-revenue',  s.total_monthly_revenue_at_risk_formatted);
        setText('kpi-reviews',  s.total_reviews_analyzed.toLocaleString());

        // Flash the critical card if alertCount > 0
        const criticalCard = document.querySelector('.kpi-card.kpi-critical');
        if (criticalCard) {
            if (alertCount > 0) {
                criticalCard.classList.add('flashing-red');
            } else {
                criticalCard.classList.remove('flashing-red');
            }
        }

        if (data.alerts && data.alerts.length > 0) {
            dashboardAlerts = data.alerts.slice(0, alertPreviewLimit);
        } else {
            dashboardAlerts = [];
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
    const visible = showAll ? filtered : filtered.slice(0, tableLimit);

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

    if (total <= tableLimit) {
        btn.style.display = 'none';
    } else {
        btn.style.display = 'inline-block';
        btn.textContent   = showAll
            ? '&#8593; Show Less'
            : `Show ${total - tableLimit} More Products \u2193`;
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
            const barColor = scoreColor(v);
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
    return {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: { labels: { color: '#fff', font: { size: 13, weight: 'bold' }, padding: 16 } },
        },
        scales: {
            x: {
                ticks: { color: '#fff', font: { size: 12, weight: 'bold' }, maxRotation: 40 },
                grid:  { color: 'rgba(255,255,255,0.08)' },
            },
            y: {
                ticks: { color: '#fff', font: { size: 12, weight: 'bold' } },
                grid:  { color: 'rgba(255,255,255,0.08)' },
                title: {
                    display: !!yAxisLabel,
                    text: yAxisLabel || '',
                    color: '#fff',
                    font: { size: 12, weight: 'bold' },
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

    // Filter out data points with missing values
    const filtered = data.filter(d => d.avg_sentiment_3mo != null && d.negative_ratio_3mo != null);
    // Apply a moving average to smooth the lines
    function movingAverage(arr, windowSize) {
        if (arr.length < windowSize) return arr;
        let result = [];
        for (let i = 0; i < arr.length; i++) {
            let start = Math.max(0, i - Math.floor(windowSize / 2));
            let end = Math.min(arr.length, i + Math.ceil(windowSize / 2));
            let window = arr.slice(start, end);
            let avg = window.reduce((a, b) => a + b, 0) / window.length;
            result.push(+avg.toFixed(2));
        }
        return result;
    }

    const happinessRaw = filtered.map(d => +(d.avg_sentiment_3mo * 100));
    const unhappyRaw   = filtered.map(d => +(d.negative_ratio_3mo * 100));
    // You can adjust the window size for more/less smoothing
    const SMOOTH_WINDOW = 5;
    const happinessSmooth = movingAverage(happinessRaw, SMOOTH_WINDOW);
    const unhappySmooth   = movingAverage(unhappyRaw, SMOOTH_WINDOW);

    console.log('Filtered and smoothed trend data for plotting:', happinessSmooth, unhappySmooth);

    // Set last two x-axis labels to 'Present Day'
    let labels = filtered.map(d => d.month);
    if (labels.length > 1) {
        labels[labels.length - 1] = 'Present Day';
        labels[labels.length - 2] = 'Present Day';
    } else if (labels.length === 1) {
        labels[0] = 'Present Day';
    }

    // Find the first 'Present Day' index
    const presentDayIndex = labels.findIndex(l => l === 'Present Day');
    sentimentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Happiness Score',
                    data:  happinessSmooth,
                    borderColor: '#42a5f5',
                    backgroundColor: 'rgba(66,165,245,0.1)',
                    fill: true, tension: 0.5, pointRadius: 2,
                },
                {
                    label: 'Unhappy Reviews %',
                    data:  unhappySmooth,
                    borderColor: '#ef5350',
                    backgroundColor: 'rgba(239,83,80,0.08)',
                    fill: true, tension: 0.5, pointRadius: 2,
                    yAxisID: 'y2',
                },
            ],
        },
        options: {
            ...opt,
            plugins: {
                legend: { labels: { color: '#fff', font: { size: 13, weight: 'bold' }, padding: 16 } },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            if (ctx.dataset.label === 'Happiness Score') {
                                const v = ctx.raw;
                                const mood = v > 20 ? 'Mostly positive' : v > -20 ? 'Mixed' : 'Mostly negative';
                                return ` Happiness: ${v}% (${mood})`;
                            }
                            return ` Unhappy Reviews: ${ctx.raw}%`;
                        },
                    },
                },
                annotation: presentDayIndex !== -1 ? {
                    annotations: {
                        presentDayLine: {
                            type: 'line',
                            xMin: presentDayIndex - 0.5,
                            xMax: presentDayIndex + 0.5,
                            borderColor: '#ef5350',
                            borderWidth: 3,
                            borderDash: [6, 4],
                            label: {
                                display: false
                            }
                        }
                    }
                } : undefined,
            },
            scales: {
                ...opt.scales,
                x: {
                    ...opt.scales.x,
                    ticks: {
                        ...opt.scales.x?.ticks,
                        color: function(context) {
                            return context.tick.label === 'Present Day' ? '#ef5350' : '#fff';
                        },
                        font: { size: 12, weight: 'bold' },
                        maxRotation: 40,
                    },
                },
                y:  { ...opt.scales.y, title: { display: true, text: 'Happiness %', color: '#fff', font: { size: 12, weight: 'bold' } }, ticks: { color: '#fff', font: { size: 12, weight: 'bold' } }, grid: { color: 'rgba(255,255,255,0.08)' } },
                y2: {
                    position: 'right',
                    ticks: { color: '#fff', font: { size: 12, weight: 'bold' }, callback: v => v + '%' },
                    grid: { drawOnChartArea: false, color: 'rgba(255,255,255,0.08)' },
                    title: { display: true, text: 'Unhappy Reviews %', color: '#fff', font: { size: 12, weight: 'bold' } },
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

    // Set last two x-axis labels to 'Present Day', squeeze if needed
    let labels = data.map(d => d.month);
    if (labels.length > 1) {
        labels[labels.length - 1] = 'Present Day';
        labels[labels.length - 2] = 'Present Day';
    } else if (labels.length === 1) {
        labels[0] = 'Present Day';
    }
    // Find the first 'Present Day' index
    const presentDayIndex = labels.findIndex(l => l === 'Present Day');
    volumeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Reviews That Month',
                data:  data.map(d => d.review_count),
                backgroundColor: function(context) {
                    const ctx = context.chart.ctx;
                    const gradient = ctx.createLinearGradient(0, 0, 0, context.chart.height);
                    gradient.addColorStop(0, 'rgba(66,165,245,0.85)');
                    gradient.addColorStop(1, 'rgba(66,165,245,0.35)');
                    return gradient;
                },
                borderColor: '#1976d2',
                borderWidth: 2,
                borderRadius: 8,
                barPercentage: 1.25, // 125% width
                categoryPercentage: 1.25, // 125% width
                hoverBackgroundColor: 'rgba(33,150,243,0.95)',
                hoverBorderColor: '#0d47a1',
                shadowOffsetX: 2,
                shadowOffsetY: 4,
                shadowBlur: 8,
                shadowColor: 'rgba(33,150,243,0.18)',
            }],
        },
        options: {
            ...baseOptions('Number of Reviews'),
            layout: { padding: { right: 40 } }, // Extra right padding for label
            plugins: {
                legend: { labels: { color: c.legend, font: { size: 11 }, padding: 14 } },
                tooltip: { callbacks: { label: ctx => ` ${ctx.raw} reviews received that month` } },
                annotation: presentDayIndex !== -1 ? {
                    annotations: {
                        presentDayLine: {
                            type: 'line',
                            xMin: presentDayIndex - 0.5,
                            xMax: presentDayIndex + 0.5,
                            borderColor: '#ef5350',
                            borderWidth: 3,
                            borderDash: [6, 4],
                            label: {
                                display: false
                            }
                        }
                    }
                } : undefined,
            },
            scales: {
                ...baseOptions('Number of Reviews').scales,
                x: {
                    ...baseOptions('Number of Reviews').scales.x,
                    offset: false,
                    ticks: {
                        ...baseOptions('Number of Reviews').scales.x?.ticks,
                        color: function(context) {
                            return context.tick.label === 'Present Day' ? '#ef5350' : '#fff';
                        },
                        font: { size: 12, weight: 'bold' },
                        maxRotation: 40,
                    },
                },
            },
            elements: {
                bar: {
                    borderRadius: 8,
                },
            },
            hover: {
                mode: 'nearest',
                intersect: true,
                animationDuration: 300,
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
                barThickness: 22,
                maxBarThickness: 28,
                minBarLength: 2,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: ctx => ` ${ctx.raw} negative reviews mention this` } },
            },
            layout: { padding: { top: 10, bottom: 10, left: 10, right: 10 } },
            scales: {
                x: {
                    ticks: { color: '#fff', font: { size: 10 } },
                    grid:  { color: c.grid },
                    title: { display: true, text: 'Number of Mentions', color: '#fff', font: { size: 10 } },
                },
                y: {
                    ticks: { color: '#fff', font: { size: 10 } },
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
    if (score >= riskThresholds.critical) return '#ef5350';
    if (score >= riskThresholds.high) return '#fb8c00';
    if (score >= riskThresholds.moderate) return '#f9a825';
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

function appendChatMessage(role, text) {
    const history = document.getElementById('chatbot-messages');
    if (!history) return;

    if (!chatConversationStarted) {
        enterConversationMode();
    }

    const row = document.createElement('div');
    row.className = `chat-row ${role}`;

    if (role === 'assistant') {
        const avatar = document.createElement('div');
        avatar.className = 'chat-avatar';
        avatar.textContent = 'AI';
        row.appendChild(avatar);
    }

    const message = document.createElement('div');
    message.className = `chatbot-message ${role}`;
    message.textContent = text;
    row.appendChild(message);

    history.appendChild(row);
    history.scrollTop = history.scrollHeight;
}

function enterConversationMode() {
    const startScreen = document.getElementById('chat-start-screen');
    const history = document.getElementById('chatbot-messages');
    if (startScreen) startScreen.classList.add('chat-hidden');
    if (history) history.classList.remove('chat-hidden');
    chatConversationStarted = true;
}

function showTypingIndicator() {
    const history = document.getElementById('chatbot-messages');
    if (!history || document.getElementById(CHAT_TYPING_ID)) return;

    const row = document.createElement('div');
    row.id = CHAT_TYPING_ID;
    row.className = 'chat-row assistant';

    const avatar = document.createElement('div');
    avatar.className = 'chat-avatar';
    avatar.textContent = 'AI';

    const bubble = document.createElement('div');
    bubble.className = 'chatbot-message assistant typing';
    bubble.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';

    row.appendChild(avatar);
    row.appendChild(bubble);

    history.appendChild(row);
    history.scrollTop = history.scrollHeight;
}

function hideTypingIndicator() {
    const existing = document.getElementById(CHAT_TYPING_ID);
    if (existing) existing.remove();
}

async function sendChatMessage() {
    const aiInput = document.getElementById('chatbot-input');
    const aiBtn = document.getElementById('chatbot-btn');
    if (!aiInput || !aiBtn || isSendingChat) return;

    const text = aiInput.value.trim();
    if (!text) return;

    appendChatMessage('user', text);
    aiInput.value = '';
    aiBtn.disabled = true;
    isSendingChat = true;
    showTypingIndicator();

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text }),
        });

        let data = {};
        try {
            data = await res.json();
        } catch (_) {
            data = {};
        }

        if (res.status === 401 || data.error === 'session_expired') {
            hideTypingIndicator();
            appendChatMessage('assistant', 'Your session has expired. Please <a href="/login" style="color:#6ec6ff">log back in</a> to continue.');
            return;
        }

        const reply = (data && typeof data.response === 'string' && data.response.trim())
            ? data.response.trim()
            : 'Sorry, I could not process that right now.';

        hideTypingIndicator();
        appendChatMessage('assistant', reply);
    } catch (error) {
        hideTypingIndicator();
        appendChatMessage('assistant', 'Sorry, I could not reach the chatbot service right now.');
    } finally {
        hideTypingIndicator();
        isSendingChat = false;
        aiBtn.disabled = aiInput.value.trim() === '';
        aiInput.focus();
    }
}
