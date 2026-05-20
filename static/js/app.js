// API Base URL
const API_BASE = '';

// Session Management
let currentSession = {
    token: localStorage.getItem('session_token'),
    user: JSON.parse(localStorage.getItem('user_data') || 'null'),
    role: localStorage.getItem('user_role')
};

// Utility: Set auth header for all requests
function getHeaders() {
    return {
        'Content-Type': 'application/json',
        'X-Session-Token': currentSession.token || ''
    };
}

// Utility: API call wrapper
async function apiCall(url, method = 'GET', body = null) {
    const options = {
        method,
        headers: getHeaders()
    };
    
    if (body) {
        options.body = JSON.stringify(body);
    }
    
    const response = await fetch(API_BASE + url, options);
    const data = await response.json();
    
    if (!response.ok) {
        throw new Error(data.error || 'Request failed');
    }
    
    return data;
}

// Check authentication state
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

// Login Handler
async function handleLogin(event) {
    event.preventDefault();
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const role = document.getElementById('role').value;
    
    try {
        const data = await apiCall('/api/login', 'POST', { email, password });
        
        // Store session
        currentSession.token = data.token;
        currentSession.user = data.user;
        currentSession.role = data.user.role;
        
        localStorage.setItem('session_token', data.token);
        localStorage.setItem('user_data', JSON.stringify(data.user));
        localStorage.setItem('user_role', data.user.role);
        
        // Check role matches selection
        if (data.user.role !== role) {
            throw new Error(`You are registered as ${data.user.role}, not ${role}`);
        }
        
        // Redirect based on role
        if (role === 'citizen') {
            window.location.href = '/submit';
        } else if (role === 'technician') {
            window.location.href = '/dashboard';
        } else if (role === 'manager') {
            window.location.href = '/analytics';
        }
    } catch (error) {
        document.getElementById('login-error').textContent = error.message;
        document.getElementById('login-error').style.display = 'block';
    }
}

// Registration Handler
async function handleRegister(event) {
    event.preventDefault();
    
    const formData = {
        name: document.getElementById('name').value,
        email: document.getElementById('email').value,
        national_id: document.getElementById('national_id').value,
        phone: document.getElementById('phone').value,
        area_id: document.getElementById('area_id').value,
        area_name: document.getElementById('area_name').value,
        password: document.getElementById('password').value,
        username: document.getElementById('name').value
    };
    
    try {
        const data = await apiCall('/api/register', 'POST', formData);
        
        // Auto-login after registration
        currentSession.token = data.token;
        localStorage.setItem('session_token', data.token);
        localStorage.setItem('user_role', 'citizen');
        
        window.location.href = '/submit';
    } catch (error) {
        document.getElementById('register-error').textContent = error.message;
        document.getElementById('register-error').style.display = 'block';
    }
}

// Submit Report Handler
async function handleSubmitReport(event) {
    event.preventDefault();
    
    if (!checkAuth('citizen')) return;
    
    const formData = {
        category: document.getElementById('category').value,
        subCategory: document.getElementById('sub_category').value,
        description: document.getElementById('description').value,
        areaId: document.getElementById('area_id').value,
        areaName: document.getElementById('area_name').value,
        lat: parseFloat(document.getElementById('lat').value) || 0,
        lng: parseFloat(document.getElementById('lng').value) || 0,
        photoUrls: []
    };
    
    try {
        const data = await apiCall('/api/requests', 'POST', formData);
        
        document.getElementById('submit-error').style.display = 'none';
        document.getElementById('submit-success').style.display = 'block';
        document.getElementById('submit-success').textContent = 
            `Report submitted successfully! ID: ${data.request_id}`;
        
        // Reset form
        event.target.reset();
        
        // Load recent requests
        loadRecentRequests();
    } catch (error) {
        document.getElementById('submit-error').textContent = error.message;
        document.getElementById('submit-error').style.display = 'block';
        document.getElementById('submit-success').style.display = 'none';
    }
}

// Load Recent Requests for Citizen
async function loadRecentRequests() {
    if (!checkAuth('citizen')) return;
    
    try {
        const data = await apiCall('/api/my-requests', 'GET');
        const recentList = document.getElementById('recent-requests');
        
        if (data.requests && data.requests.length > 0) {
            recentList.innerHTML = data.requests.slice(0, 5).map(req => `
                <tr>
                    <td>${req._id}</td>
                    <td>${req.category}</td>
                    <td><span class="badge badge-${req.priority}">${req.priority}</span></td>
                    <td><span class="badge badge-${req.status}">${req.status}</span></td>
                </tr>
            `).join('');
        } else {
            recentList.innerHTML = '<tr><td colspan="4">No requests yet</td></tr>';
        }
    } catch (error) {
        console.error('Failed to load recent requests:', error);
    }
}

// Load Technician Dashboard
async function loadTechnicianDashboard() {
    if (!checkAuth('technician')) return;
    
    try {
        // Get categories first to know department
        const categories = await apiCall('/api/categories', 'GET');
        
        // Load requests for each category
        const requestsContainer = document.getElementById('department-requests');
        requestsContainer.innerHTML = '<div class="loading">Loading requests...</div>';
        
        // For demo, we'll fetch similar requests or use a mock endpoint
        const nearbyRequests = await apiCall('/api/requests/nearby?lat=0&lng=0&distance=100000', 'GET');
        
        if (nearbyRequests.requests && nearbyRequests.requests.length > 0) {
            // Sort by priority (high first)
            const sorted = nearbyRequests.requests.sort((a, b) => {
                const priorityOrder = { high: 3, medium: 2, low: 1 };
                return priorityOrder[b.priority] - priorityOrder[a.priority];
            });
            
            requestsContainer.innerHTML = sorted.slice(0, 10).map(req => `
                <div class="card">
                    <div style="display: flex; justify-content: space-between; align-items: start;">
                        <div>
                            <h3 style="font-size: 1rem; margin-bottom: 0.5rem;">
                                ${req.description.substring(0, 100)}...
                            </h3>
                            <div style="font-size: 0.875rem; color: #636e72; margin-bottom: 0.5rem;">
                                ${req.category} - ${req.subCategory || 'N/A'}
                            </div>
                            <div style="font-size: 0.875rem; color: #636e72;">
                                Area: ${req.areaName} | Reported by: ${req.citizenName || 'Unknown'}
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <span class="badge badge-${req.priority}">${req.priority}</span>
                            <br>
                            <span class="badge badge-${req.status}" style="margin-top: 0.25rem; display: inline-block;">
                                ${req.status}
                            </span>
                        </div>
                    </div>
                    ${req.status !== 'resolved' ? `
                        <div style="margin-top: 1rem;">
                            <select onchange="updateRequestStatus('${req._id}', this.value)" 
                                    style="padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 4px;">
                                <option value="">Update Status</option>
                                <option value="assigned">Assigned</option>
                                <option value="in_progress">In Progress</option>
                                <option value="resolved">Resolved</option>
                            </select>
                        </div>
                    ` : ''}
                </div>
            `).join('');
        } else {
            requestsContainer.innerHTML = '<p>No requests available for your department.</p>';
        }
    } catch (error) {
        console.error('Failed to load dashboard:', error);
        document.getElementById('department-requests').innerHTML = 
            '<div class="error-message">Failed to load requests</div>';
    }
}

// Update Request Status (Technician)
async function updateRequestStatus(requestId, newStatus) {
    if (!newStatus) return;
    
    try {
        await apiCall(`/api/requests/${requestId}/status`, 'PATCH', { status: newStatus });
        loadTechnicianDashboard(); // Refresh
    } catch (error) {
        alert('Failed to update status: ' + error.message);
    }
}

// Load Analytics Dashboard (City Manager)
async function loadAnalyticsDashboard() {
    if (!checkAuth('manager')) return;
    
    try {
        // Load overview stats
        const overview = await apiCall('/api/analytics/overview', 'GET');
        displayOverviewStats(overview);
        
        // Load top issues
        const topIssues = await apiCall('/api/analytics/top-issues?days=30&limit=5', 'GET');
        displayTopIssues(topIssues.top_issues);
        
        // Load area breakdown
        const areaData = await apiCall('/api/analytics/by-area?days=30', 'GET');
        displayAreaBreakdown(areaData.areas);
        
        // Load response time
        const responseTime = await apiCall('/api/analytics/response-time', 'GET');
        displayResponseTime(responseTime.departments);
        
        // Load leaderboard
        const leaderboard = await apiCall('/api/analytics/leaderboard', 'GET');
        displayLeaderboard(leaderboard);
        
        // Load graph stats
        const graphStats = await apiCall('/api/graph/stats', 'GET');
        displayGraphStats(graphStats);
        
    } catch (error) {
        console.error('Failed to load analytics:', error);
    }
}

function displayOverviewStats(data) {
    document.getElementById('total-requests').textContent = data.totalRequests || 0;
    document.getElementById('open-requests').textContent = data.openRequests || 0;
    document.getElementById('avg-resolution-time').textContent = 
        (data.avgResolutionHours || 0).toFixed(1) + 'h';
    document.getElementById('citizens-count').textContent = data.totalCitizens || 0;
}

function displayTopIssues(issues) {
    const container = document.getElementById('top-issues');
    if (!issues || issues.length === 0) {
        container.innerHTML = '<p>No data available</p>';
        return;
    }
    
    container.innerHTML = issues.map(issue => `
        <div class="chart-bar">
            <div class="chart-bar-label">${issue._id}</div>
            <div class="chart-bar-track">
                <div class="chart-bar-fill" style="width: ${(issue.count / issues[0].count) * 100}%">
                    ${issue.count}
                </div>
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
    
    container.innerHTML = areas.slice(0, 8).map(area => `
        <div class="chart-bar">
            <div class="chart-bar-label">${area._id}</div>
            <div class="chart-bar-track">
                <div class="chart-bar-fill" style="width: ${(area.count / areas[0].count) * 100}%">
                    ${area.count}
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
    
    container.innerHTML = departments.map(dept => `
        <div class="chart-bar">
            <div class="chart-bar-label">${dept._id}</div>
            <div class="chart-bar-track">
                <div class="chart-bar-fill" style="width: ${Math.min((dept.avgHours / 48) * 100, 100)}%">
                    ${dept.avgHours.toFixed(1)}h
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
                <tr>
                    <th>Rank</th>
                    <th>Citizen ID</th>
                    <th>Civic Score</th>
                </tr>
            </thead>
            <tbody>
                ${citizens.slice(0, 5).map((citizen, index) => `
                    <tr>
                        <td>${index + 1}</td>
                        <td>${citizen.user_id}</td>
                        <td>${citizen.civic_score}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function displayGraphStats(data) {
    const container = document.getElementById('graph-stats');
    if (!data) {
        container.innerHTML = '<p>No graph data available</p>';
        return;
    }
    
    container.innerHTML = `
        <div class="stat">
            <div class="stat-value">${data.nodeCount || 0}</div>
            <div class="stat-label">Graph Nodes</div>
        </div>
        <div class="stat">
            <div class="stat-value">${data.relationshipCount || 0}</div>
            <div class="stat-label">Relationships</div>
        </div>
    `;
}

// Logout
function logout() {
    localStorage.clear();
    currentSession = { token: null, user: null, role: null };
    window.location.href = '/';
}

// Initialize page-specific logic
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on login page
    if (document.getElementById('login-form')) {
        document.getElementById('login-form').addEventListener('submit', handleLogin);
        
        const registerForm = document.getElementById('register-form');
        if (registerForm) {
            registerForm.addEventListener('submit', handleRegister);
        }
    }
    
    // Check if we're on submit page
    if (document.getElementById('report-form')) {
        loadRecentRequests();
        document.getElementById('report-form').addEventListener('submit', handleSubmitReport);
    }
    
    // Check if we're on dashboard page
    if (document.getElementById('department-requests')) {
        loadTechnicianDashboard();
    }
    
    // Check if we're on analytics page
    if (document.getElementById('analytics-dashboard')) {
        loadAnalyticsDashboard();
    }
});