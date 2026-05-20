/* ---------------------------------------------------------------------------
   SmartCity Platform — Frontend JS (plain JavaScript, no framework)
   --------------------------------------------------------------------------- */

const API_BASE = '';

// ── Session state (stored in localStorage) ─────────────────────────────────
let currentSession = {
    token: localStorage.getItem('session_token'),
    user:  JSON.parse(localStorage.getItem('user_data') || 'null'),
    role:  localStorage.getItem('user_role'),
};

// Areas used in the Citizen registration form (matches seed_all.py)
const AREAS = [
    { id: 'dist_1', name: 'Old City' },
    { id: 'dist_2', name: 'Commercial Center' },
    { id: 'dist_3', name: 'University Zone' },
    { id: 'dist_4', name: 'Northern Suburbs' },
    { id: 'dist_5', name: 'Industrial Area' },
    { id: 'dist_6', name: 'Residential East' },
    { id: 'dist_7', name: 'Residential West' },
    { id: 'dist_8', name: 'Southern Zone' },
];

// ── Helpers ────────────────────────────────────────────────────────────────

function getHeaders() {
    return {
        'Content-Type':    'application/json',
        'X-Session-Token': currentSession.token || '',
    };
}

async function apiCall(url, method = 'GET', body = null) {
    const options = { method, headers: getHeaders() };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(API_BASE + url, options);
    const data     = await response.json();

    if (!response.ok) {
        throw new Error(data.error || 'Request failed');
    }
    return data;
}

function checkAuth(requiredRole = null) {
    if (!currentSession.token) {
        window.location.href = '/';
        return false;
    }
    if (requiredRole && currentSession.role !== requiredRole) {
        window.location.href = '/';
        return false;
    }
    return true;
}

// Map status string to a CSS-friendly class (in_progress -> in-progress)
function statusClass(status) {
    return (status || '').replace(/_/g, '-');
}

// ── Login ──────────────────────────────────────────────────────────────────

async function handleLogin(event) {
    event.preventDefault();

    const email    = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const role     = document.getElementById('role').value;

    try {
        const data = await apiCall('/api/login', 'POST', { email, password });

        // Store session
        currentSession.token = data.token;
        currentSession.user  = data.user;
        currentSession.role  = data.user.role;

        localStorage.setItem('session_token', data.token);
        localStorage.setItem('user_data',     JSON.stringify(data.user));
        localStorage.setItem('user_role',     data.user.role);

        if (data.user.role !== role) {
            throw new Error(`You are registered as ${data.user.role}, not ${role}`);
        }

        // Role-based redirect
        if (role === 'citizen')         window.location.href = '/submit';
        else if (role === 'technician') window.location.href = '/dashboard';
        else if (role === 'manager')    window.location.href = '/analytics';
    } catch (error) {
        const err = document.getElementById('login-error');
        err.textContent  = error.message;
        err.style.display = 'block';
    }
}

// ── Register ───────────────────────────────────────────────────────────────

async function handleRegister(event) {
    event.preventDefault();

    const areaIdValue = document.getElementById('area_id').value;
    const area = AREAS.find(a => a.id === areaIdValue) || { id: areaIdValue, name: '' };

    const formData = {
        name:        document.getElementById('name').value,
        email:       document.getElementById('reg-email').value,
        national_id: document.getElementById('national_id').value,
        phone:       document.getElementById('phone').value,
        area_id:     area.id,
        area_name:   area.name,
        password:    document.getElementById('reg-password').value,
        username:    document.getElementById('name').value,
    };

    try {
        const data = await apiCall('/api/register', 'POST', formData);

        // Auto-login after registration
        currentSession.token = data.token;
        currentSession.role  = 'citizen';
        localStorage.setItem('session_token', data.token);
        localStorage.setItem('user_role',     'citizen');

        window.location.href = '/submit';
    } catch (error) {
        const err = document.getElementById('register-error');
        err.textContent  = error.message;
        err.style.display = 'block';
    }
}

// Populate the Area <select> on the registration page
function populateAreaSelect(selectId) {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    AREAS.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.id;
        opt.textContent = `${a.name} (${a.id})`;
        sel.appendChild(opt);
    });
}

// ── Submit Report ──────────────────────────────────────────────────────────

async function loadCategoriesIntoForm() {
    try {
        const cats = await apiCall('/api/categories', 'GET');
        const catSelect = document.getElementById('category');
        const subSelect = document.getElementById('sub_category');
        if (!catSelect) return;

        // Wipe existing options (kept the placeholder one)
        catSelect.innerHTML = '<option value="">Select category</option>';
        Object.keys(cats).forEach(c => {
            const opt = document.createElement('option');
            opt.value = c;
            opt.textContent = c.charAt(0).toUpperCase() + c.slice(1);
            catSelect.appendChild(opt);
        });

        // When category changes, refresh sub-category options
        catSelect.addEventListener('change', () => {
            if (!subSelect) return;
            subSelect.innerHTML = '<option value="">Select sub-category</option>';
            const subs = cats[catSelect.value] || [];
            subs.forEach(s => {
                const o = document.createElement('option');
                o.value = s;
                o.textContent = s;
                subSelect.appendChild(o);
            });
        });
    } catch (err) {
        console.error('Failed to load categories:', err);
    }
}

async function handleSubmitReport(event) {
    event.preventDefault();
    if (!checkAuth('citizen')) return;

    const areaIdValue = document.getElementById('area_id').value;
    const area = AREAS.find(a => a.id === areaIdValue) || { id: areaIdValue, name: '' };

    const formData = {
        category:    document.getElementById('category').value,
        subCategory: document.getElementById('sub_category').value,
        description: document.getElementById('description').value,
        areaId:      area.id,
        areaName:    area.name,
        lat:         parseFloat(document.getElementById('lat').value) || 0,
        lng:         parseFloat(document.getElementById('lng').value) || 0,
        photoUrls:   [],
    };

    try {
        const data = await apiCall('/api/requests', 'POST', formData);

        document.getElementById('submit-error').style.display   = 'none';
        const ok = document.getElementById('submit-success');
        ok.style.display = 'block';
        ok.textContent   =
            `Report submitted! ID: ${data.request_id} | Priority: ${data.priority}` +
            (data.similarity_boosted ? ' (boosted: similar reports exist)' : '');

        event.target.reset();
        loadRecentRequests();
    } catch (error) {
        const err = document.getElementById('submit-error');
        err.textContent  = error.message;
        err.style.display = 'block';
        document.getElementById('submit-success').style.display = 'none';
    }
}

// Citizen's recent requests table
async function loadRecentRequests() {
    if (!checkAuth('citizen')) return;
    try {
        const data = await apiCall('/api/my-requests', 'GET');
        const tbody = document.getElementById('recent-requests');

        if (data.requests && data.requests.length > 0) {
            tbody.innerHTML = data.requests.slice(0, 5).map(r => `
                <tr>
                    <td>${r._id.slice(-6)}</td>
                    <td>${r.category}</td>
                    <td><span class="badge badge-${r.priority}">${r.priority}</span></td>
                    <td><span class="badge badge-${statusClass(r.status)}">${r.status}</span></td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="4">No requests yet</td></tr>';
        }
    } catch (error) {
        console.error('Failed to load recent requests:', error);
    }
}

// ── Technician Dashboard ───────────────────────────────────────────────────

async function loadTechnicianDashboard() {
    if (!checkAuth('technician')) return;

    const container = document.getElementById('department-requests');
    container.innerHTML = '<div class="loading">Loading requests...</div>';

    try {
        // Wide nearby query (huge radius) to show all current requests
        const resp = await apiCall('/api/requests/nearby?lat=31.9&lng=35.2&distance=100000', 'GET');

        if (!resp.requests || resp.requests.length === 0) {
            container.innerHTML = '<p>No open requests right now.</p>';
            return;
        }

        // Sort by priority (high first)
        const order  = { high: 3, medium: 2, low: 1 };
        const sorted = resp.requests.sort((a, b) => order[b.priority] - order[a.priority]);

        container.innerHTML = sorted.slice(0, 20).map(r => `
            <div class="card">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;">
                    <div style="flex:1;">
                        <h3 style="font-size:1rem;margin-bottom:0.5rem;">
                            ${(r.description || '').substring(0, 120)}
                        </h3>
                        <div style="font-size:0.875rem;color:#636e72;margin-bottom:0.25rem;">
                            ${r.category} — ${r.subCategory || 'N/A'}
                        </div>
                        <div style="font-size:0.875rem;color:#636e72;">
                            Area: ${r.location?.areaName || ''}
                            | Reported by: ${r.citizen?.citizenName || 'Unknown'}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <span class="badge badge-${r.priority}">${r.priority}</span><br><br>
                        <span class="badge badge-${statusClass(r.status)}">${r.status}</span>
                    </div>
                </div>
                ${r.status !== 'resolved' ? `
                    <div style="margin-top:1rem;">
                        <select onchange="updateRequestStatus('${r._id}', this.value)"
                                style="padding:0.5rem;border:1px solid #d1d5db;border-radius:4px;">
                            <option value="">Update Status</option>
                            <option value="assigned">Assigned</option>
                            <option value="in_progress">In Progress</option>
                            <option value="resolved">Resolved</option>
                        </select>
                    </div>` : ''}
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load dashboard:', error);
        container.innerHTML = '<div class="error-message">Failed to load requests</div>';
    }
}

async function updateRequestStatus(requestId, newStatus) {
    if (!newStatus) return;
    try {
        await apiCall(`/api/requests/${requestId}/status`, 'PATCH', { status: newStatus });
        loadTechnicianDashboard();
    } catch (error) {
        alert('Failed to update status: ' + error.message);
    }
}

// ── Analytics Dashboard (City Manager) ─────────────────────────────────────

async function loadAnalyticsDashboard() {
    if (!checkAuth('manager')) return;

    try {
        const overview = await apiCall('/api/analytics/overview', 'GET');
        displayOverviewStats(overview);

        const topIssues = await apiCall('/api/analytics/top-issues?days=30&limit=5', 'GET');
        displayTopIssues(topIssues.top_issues);

        const areaData = await apiCall('/api/analytics/by-area?days=30', 'GET');
        displayAreaBreakdown(areaData.areas);

        const responseTime = await apiCall('/api/analytics/response-time', 'GET');
        displayResponseTime(responseTime.departments);

        const leaderboard = await apiCall('/api/analytics/leaderboard', 'GET');
        displayLeaderboard(leaderboard);

        const graphStats = await apiCall('/api/graph/stats', 'GET');
        displayGraphStats(graphStats);
    } catch (error) {
        console.error('Failed to load analytics:', error);
    }
}

function displayOverviewStats(data) {
    document.getElementById('total-requests').textContent  = data.total_requests || 0;
    document.getElementById('open-requests').textContent   = data.open_requests || 0;
    document.getElementById('citizens-count').textContent  = data.citizens || 0;
    // avg-resolution-time is filled by displayResponseTime if needed; default to 0h
    const avg = document.getElementById('avg-resolution-time');
    if (avg && avg.textContent === '0') avg.textContent = '—';
}

function displayTopIssues(issues) {
    const container = document.getElementById('top-issues');
    if (!issues || issues.length === 0) {
        container.innerHTML = '<p>No data available</p>';
        return;
    }
    const max = issues[0].count;
    container.innerHTML = issues.map(i => `
        <div class="chart-bar">
            <div class="chart-bar-label">${i.category}</div>
            <div class="chart-bar-track">
                <div class="chart-bar-fill" style="width:${(i.count / max) * 100}%">${i.count}</div>
            </div>
        </div>
    `).join('');
}

function displayAreaBreakdown(areas) {
    const container = document.getElementById('area-breakdown');
    if (!areas || areas.length === 0) {
        container.innerHTML = '<p>No data available</p>';
        return;
    }
    const max = areas[0].total;
    container.innerHTML = areas.slice(0, 8).map(a => `
        <div class="chart-bar">
            <div class="chart-bar-label">${a.areaName || a.areaId}</div>
            <div class="chart-bar-track">
                <div class="chart-bar-fill" style="width:${(a.total / max) * 100}%">
                    ${a.total} (${a.resolved} resolved)
                </div>
            </div>
        </div>
    `).join('');
}

function displayResponseTime(departments) {
    const container = document.getElementById('response-time');
    if (!departments || departments.length === 0) {
        container.innerHTML = '<p>No data available</p>';
        return;
    }
    // Update the headline avg card with the average of all departments
    const avg = departments.reduce((s, d) => s + (d.avg_hours || 0), 0) / departments.length;
    const avgEl = document.getElementById('avg-resolution-time');
    if (avgEl) avgEl.textContent = avg.toFixed(1) + 'h';

    container.innerHTML = departments.map(d => `
        <div class="chart-bar">
            <div class="chart-bar-label">${d.department || 'Unassigned'}</div>
            <div class="chart-bar-track">
                <div class="chart-bar-fill" style="width:${Math.min((d.avg_hours / 48) * 100, 100)}%">
                    ${d.avg_hours.toFixed(1)}h
                </div>
            </div>
        </div>
    `).join('');
}

function displayLeaderboard(citizens) {
    const container = document.getElementById('leaderboard');
    if (!citizens || citizens.length === 0) {
        container.innerHTML = '<p>No data available</p>';
        return;
    }
    container.innerHTML = `
        <table class="table">
            <thead>
                <tr><th>Rank</th><th>Citizen ID</th><th>Civic Score</th></tr>
            </thead>
            <tbody>
                ${citizens.slice(0, 5).map((c, i) => `
                    <tr>
                        <td>${i + 1}</td>
                        <td>${(c.user_id || '').slice(-6)}</td>
                        <td>${c.civic_score}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function displayGraphStats(data) {
    const container = document.getElementById('graph-stats');
    if (!container) return;
    if (!data || !data.nodes) {
        container.innerHTML = '<p>No graph data available</p>';
        return;
    }
    const totalNodes = Object.values(data.nodes).reduce((s, n) => s + n, 0);
    container.innerHTML = `
        <div class="stat">
            <div class="stat-value">${totalNodes}</div>
            <div class="stat-label">Graph Nodes</div>
        </div>
        <div class="stat">
            <div class="stat-value">${data.relationships || 0}</div>
            <div class="stat-label">Relationships</div>
        </div>
    `;
}

// ── Graph Explorer Page ────────────────────────────────────────────────────

async function loadGraphExplorer() {
    try {
        const stats = await apiCall('/api/graph/stats', 'GET');
        const totalNodes = Object.values(stats.nodes || {}).reduce((s, n) => s + n, 0);
        document.getElementById('node-count').textContent = totalNodes;
        document.getElementById('rel-count').textContent  = stats.relationships || 0;

        const cov = await apiCall('/api/graph/department-coverage', 'GET');
        document.getElementById('department-coverage').innerHTML = `
            <table class="table">
                <thead><tr><th>Department</th><th>Areas Covered</th></tr></thead>
                <tbody>
                    ${(cov.department_coverage || []).map(d => `
                        <tr>
                            <td>${d.department}</td>
                            <td>${(d.areas || []).join(', ')}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        const top = await apiCall('/api/graph/top-technicians?limit=5', 'GET');
        document.getElementById('top-technicians').innerHTML = `
            <table class="table">
                <thead><tr><th>Technician</th><th>Resolved Requests</th></tr></thead>
                <tbody>
                    ${(top.top_technicians || []).map(t => `
                        <tr><td>${t.technician}</td><td>${t.resolved}</td></tr>
                    `).join('') || '<tr><td colspan="2">No resolved requests yet</td></tr>'}
                </tbody>
            </table>
        `;

        const wl = await apiCall('/api/graph/area-workload', 'GET');
        document.getElementById('area-workload').innerHTML = `
            <table class="table">
                <thead><tr><th>Area</th><th>Open Issues</th></tr></thead>
                <tbody>
                    ${(wl.area_workload || []).map(a => `
                        <tr><td>${a.area}</td><td>${a.open_issues}</td></tr>
                    `).join('') || '<tr><td colspan="2">No open issues</td></tr>'}
                </tbody>
            </table>
        `;

        const gaps = await apiCall('/api/graph/collaboration-gaps', 'GET');
        document.getElementById('collaboration-gaps').innerHTML = `
            <table class="table">
                <thead><tr><th>Dept A</th><th>Dept B</th><th>Shared Areas</th></tr></thead>
                <tbody>
                    ${(gaps.collaboration_gaps || []).map(g => `
                        <tr>
                            <td>${g.dept_a}</td>
                            <td>${g.dept_b}</td>
                            <td>${(g.shared_areas || []).join(', ')}</td>
                        </tr>
                    `).join('') || '<tr><td colspan="3">No collaboration gaps</td></tr>'}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Failed to load graph explorer:', error);
    }
}

// ── Logout ─────────────────────────────────────────────────────────────────

function logout() {
    localStorage.clear();
    currentSession = { token: null, user: null, role: null };
    window.location.href = '/';
}

// ── Page bootstrap ─────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
    // Login page
    if (document.getElementById('login-form')) {
        document.getElementById('login-form').addEventListener('submit', handleLogin);

        const reg = document.getElementById('register-form');
        if (reg) {
            reg.addEventListener('submit', handleRegister);
            populateAreaSelect('area_id');
        }
    }

    // Submit page
    if (document.getElementById('report-form')) {
        loadCategoriesIntoForm();
        populateAreaSelect('area_id');
        loadRecentRequests();
        document.getElementById('report-form').addEventListener('submit', handleSubmitReport);
    }

    // Technician dashboard
    if (document.getElementById('department-requests')) {
        loadTechnicianDashboard();
    }

    // Analytics dashboard
    if (document.getElementById('analytics-dashboard')) {
        loadAnalyticsDashboard();
    }

    // Graph explorer
    if (document.getElementById('graph-explorer')) {
        loadGraphExplorer();
    }
});
