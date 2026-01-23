from flask import Flask, request, redirect, render_template_string, jsonify
import requests
import json
import os
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)

# Configuration
CLIENT_ID = os.environ.get('BULLHORN_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('BULLHORN_CLIENT_SECRET', '')
REDIRECT_URI = 'https://bullhorn-oauth.onrender.com/oauth/callback'
TOKEN_FILE = 'token_store.json'

# Auto-refresh configuration
REFRESH_INTERVAL_MINUTES = 5  # Refresh every 5 minutes
scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# HTML Template (same as before)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bullhorn OAuth - Production</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gradient-to-br from-blue-50 to-indigo-100 min-h-screen p-6">
    <div class="max-w-4xl mx-auto">
        <div class="bg-white rounded-lg shadow-xl p-8">
            <div class="flex items-center gap-3 mb-6">
                <svg class="w-8 h-8 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
                </svg>
                <h1 class="text-3xl font-bold text-gray-800">Bullhorn OAuth (Production)</h1>
            </div>

            {% if message %}
            <div class="mb-4 p-4 {% if error %}bg-red-50 border-red-200{% else %}bg-green-50 border-green-200{% endif %} border rounded-lg">
                <p class="{% if error %}text-red-800{% else %}text-green-800{% endif %}">{{ message }}</p>
            </div>
            {% endif %}

            {% if tokens %}
            <div class="mb-6 p-6 bg-green-50 border border-green-200 rounded-lg">
                <h3 class="text-lg font-semibold text-green-800 mb-3">✅ Active Session</h3>
                <div class="space-y-3 text-sm">
                    <div>
                        <span class="font-medium text-gray-700">Status:</span>
                        <p class="text-green-600 font-semibold">{{ session_status }}</p>
                    </div>
                    <div>
                        <span class="font-medium text-gray-700">Last Refresh:</span>
                        <p class="text-gray-600">{{ tokens.last_refresh if tokens.last_refresh else 'Never' }}</p>
                    </div>
                    <div>
                        <span class="font-medium text-gray-700">REST URL:</span>
                        <p class="text-gray-600 break-all font-mono text-xs mt-1">{{ tokens.rest_url }}</p>
                    </div>
                    <div>
                        <span class="font-medium text-gray-700">Auto-Refresh:</span>
                        <p class="text-gray-600">Enabled (every {{ refresh_interval }} minutes)</p>
                    </div>
                </div>
            </div>

            <div class="flex gap-3 mb-6 flex-wrap">
                <a href="/analytics" class="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors inline-flex items-center gap-2">
                    <span>📊</span>
                    Analytics Dashboard
                </a>
                <a href="/test" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                    Test Connection
                </a>
                <a href="/api/submissions?year=2026&month=1" class="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors" target="_blank">
                    Test API (Jan 2026)
                </a>
                <a href="/logout" class="px-6 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors">
                    Clear Tokens
                </a>
            </div>
            {% else %}
            <div class="mb-6">
                <p class="text-gray-700 mb-4">Click the button below to authenticate with Bullhorn.</p>
                <a href="/login" class="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                    </svg>
                    Start OAuth Flow
                </a>
            </div>
            {% endif %}

            <div class="mt-8 p-6 bg-gray-50 rounded-lg">
                <h3 class="text-lg font-semibold text-gray-800 mb-3">API Endpoints</h3>
                <div class="space-y-2 text-sm text-gray-700 font-mono">
                    <div class="bg-white p-2 rounded">GET /api/tokens - Get current tokens</div>
                    <div class="bg-white p-2 rounded">GET /api/submissions?year=YYYY&month=M - Fetch submissions</div>
                    <div class="bg-white p-2 rounded">GET /api/placements?year=YYYY&month=M - Fetch placements</div>
                    <div class="bg-white p-2 rounded">POST /api/refresh - Manually refresh tokens</div>
                    <div class="bg-white p-2 rounded">GET /api/status - Check session status</div>
                </div>
            </div>

            <div class="mt-6 p-6 bg-blue-50 rounded-lg">
                <h3 class="text-lg font-semibold text-gray-800 mb-3">Production Features</h3>
                <ul class="list-disc list-inside space-y-2 text-gray-700">
                    <li>✅ Auto-refresh tokens every 5 minutes</li>
                    <li>✅ Automatic BhRestToken exchange on callback</li>
                    <li>✅ RESTful API endpoints for data fetching</li>
                    <li>✅ Session persistence across restarts</li>
                    <li>✅ No manual "Test Connection" needed</li>
                </ul>
            </div>
        </div>
    </div>
</body>
</html>
'''

ANALYTICS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analytics Dashboard - Bullhorn OAuth</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/react-is@18/umd/react-is.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://unpkg.com/recharts@2.10.0/umd/Recharts.min.js"></script>
</head>
<body class="bg-gradient-to-br from-blue-50 to-indigo-100 min-h-screen p-6">
    <div id="root">
        <div class="p-6 text-center">
            <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
            <p class="mt-4 text-gray-600">Loading dashboard...</p>
        </div>
    </div>
    
    <script type="text/babel">
        const { useState, useEffect, useMemo } = React;
        const { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } = window.Recharts;

        function AnalyticsDashboard() {
            const [submissions, setSubmissions] = useState([]);
            const [placements, setPlacements] = useState([]);
            const [loading, setLoading] = useState(true);
            const [error, setError] = useState(null);
            
            // Filters
            const [year, setYear] = useState(new Date().getFullYear());
            const [month, setMonth] = useState(new Date().getMonth() + 1);
            const [viewMode, setViewMode] = useState('By Recruiter');
            const [selectedRecruiter, setSelectedRecruiter] = useState('All');
            
            // Fetch data
            const fetchData = async () => {
                setLoading(true);
                setError(null);
                try {
                    console.log(`Fetching data for ${year}-${month}...`);
                    const [subsRes, placeRes] = await Promise.all([
                        fetch(`/api/submissions?year=${year}&month=${month}`),
                        fetch(`/api/placements?year=${year}&month=${month}`)
                    ]);
                    
                    console.log('Submissions response:', subsRes.status, subsRes.ok);
                    console.log('Placements response:', placeRes.status, placeRes.ok);
                    
                    if (!subsRes.ok) {
                        const errorText = await subsRes.text();
                        console.error('Submissions error:', errorText);
                        throw new Error(`Submissions API error: ${subsRes.status} - ${errorText.substring(0, 100)}`);
                    }
                    
                    if (!placeRes.ok) {
                        const errorText = await placeRes.text();
                        console.error('Placements error:', errorText);
                        throw new Error(`Placements API error: ${placeRes.status} - ${errorText.substring(0, 100)}`);
                    }
                    
                    const subsData = await subsRes.json();
                    const placeData = await placeRes.json();
                    
                    console.log('Submissions data:', subsData.count || 0, 'items');
                    console.log('Placements data:', placeData.count || 0, 'items');
                    
                    setSubmissions(subsData.data || []);
                    setPlacements(placeData.data || []);
                } catch (err) {
                    console.error('Fetch error:', err);
                    setError(err.message || 'Failed to fetch data');
                } finally {
                    setLoading(false);
                }
            };
            
            useEffect(() => {
                fetchData();
                // eslint-disable-next-line react-hooks/exhaustive-deps
            }, [year, month]);
            
            // Helper function to get recruiter name from jobOrder.owner
            const getRecruiterName = (item) => {
                if (item.jobOrder && item.jobOrder.owner && item.jobOrder.owner.firstName && item.jobOrder.owner.lastName) {
                    return `${item.jobOrder.owner.firstName} ${item.jobOrder.owner.lastName}`;
                }
                return null;
            };
            
            // Get unique recruiters
            const recruiters = useMemo(() => {
                const recruiterSet = new Set();
                [...submissions, ...placements].forEach(item => {
                    const name = getRecruiterName(item);
                    if (name) recruiterSet.add(name);
                });
                return Array.from(recruiterSet).sort();
            }, [submissions, placements]);
            
            // Filter data by recruiter
            const filteredSubmissions = useMemo(() => {
                if (selectedRecruiter === 'All') return submissions;
                return submissions.filter(sub => {
                    const name = getRecruiterName(sub);
                    return name === selectedRecruiter;
                });
            }, [submissions, selectedRecruiter]);
            
            const filteredPlacements = useMemo(() => {
                if (selectedRecruiter === 'All') return placements;
                return placements.filter(place => {
                    const name = getRecruiterName(place);
                    return name === selectedRecruiter;
                });
            }, [placements, selectedRecruiter]);
            
            // Calculate stats
            const stats = useMemo(() => {
                const totalSubmissions = filteredSubmissions.length;
                const totalPlacements = filteredPlacements.length;
                const conversionRate = totalSubmissions > 0 ? (totalPlacements / totalSubmissions * 100).toFixed(1) : 0;
                const uniqueRecruiters = new Set();
                [...filteredSubmissions, ...filteredPlacements].forEach(item => {
                    const name = getRecruiterName(item);
                    if (name) uniqueRecruiters.add(name);
                });
                
                return {
                    totalSubmissions,
                    totalPlacements,
                    conversionRate: parseFloat(conversionRate),
                    numRecruiters: uniqueRecruiters.size
                };
            }, [filteredSubmissions, filteredPlacements]);
            
            // Group data for charts
            const chartData = useMemo(() => {
                if (viewMode === 'By Recruiter') {
                    const recruiterMap = new Map();
                    
                    filteredSubmissions.forEach(sub => {
                        const name = getRecruiterName(sub) || 'Unknown';
                        if (!recruiterMap.has(name)) {
                            recruiterMap.set(name, { name, submissions: 0, placements: 0 });
                        }
                        recruiterMap.get(name).submissions++;
                    });
                    
                    filteredPlacements.forEach(place => {
                        const name = getRecruiterName(place) || 'Unknown';
                        if (!recruiterMap.has(name)) {
                            recruiterMap.set(name, { name, submissions: 0, placements: 0 });
                        }
                        recruiterMap.get(name).placements++;
                    });
                    
                    return Array.from(recruiterMap.values()).sort((a, b) => b.submissions - a.submissions);
                } else {
                    // By Week
                    const weekMap = new Map();
                    
                    const getWeekNumber = (dateMs) => {
                        const date = new Date(dateMs);
                        const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
                        const dayNum = d.getUTCDay() || 7;
                        d.setUTCDate(d.getUTCDate() + 4 - dayNum);
                        const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
                        return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
                    };
                    
                    filteredSubmissions.forEach(sub => {
                        if (!sub.dateAdded) return;
                        const week = getWeekNumber(sub.dateAdded);
                        const key = `Week ${week}`;
                        if (!weekMap.has(key)) {
                            weekMap.set(key, { name: key, submissions: 0, placements: 0 });
                        }
                        weekMap.get(key).submissions++;
                    });
                    
                    filteredPlacements.forEach(place => {
                        if (!place.dateAdded) return;
                        const week = getWeekNumber(place.dateAdded);
                        const key = `Week ${week}`;
                        if (!weekMap.has(key)) {
                            weekMap.set(key, { name: key, submissions: 0, placements: 0 });
                        }
                        weekMap.get(key).placements++;
                    });
                    
                    return Array.from(weekMap.values()).sort((a, b) => {
                        const weekA = parseInt(a.name.replace('Week ', ''));
                        const weekB = parseInt(b.name.replace('Week ', ''));
                        return weekA - weekB;
                    });
                }
            }, [filteredSubmissions, filteredPlacements, viewMode]);
            
            // Pie chart data (submissions by recruiter)
            const pieData = useMemo(() => {
                const recruiterMap = new Map();
                filteredSubmissions.forEach(sub => {
                    const name = getRecruiterName(sub) || 'Unknown';
                    recruiterMap.set(name, (recruiterMap.get(name) || 0) + 1);
                });
                
                return Array.from(recruiterMap.entries())
                    .map(([name, value]) => ({ name, value }))
                    .sort((a, b) => b.value - a.value);
            }, [filteredSubmissions]);
            
            // Top performers
            const topPerformers = useMemo(() => {
                const recruiterMap = new Map();
                
                filteredSubmissions.forEach(sub => {
                    const name = getRecruiterName(sub) || 'Unknown';
                    if (!recruiterMap.has(name)) {
                        recruiterMap.set(name, { recruiter: name, submissions: 0, placements: 0 });
                    }
                    recruiterMap.get(name).submissions++;
                });
                
                filteredPlacements.forEach(place => {
                    const name = getRecruiterName(place) || 'Unknown';
                    if (!recruiterMap.has(name)) {
                        recruiterMap.set(name, { recruiter: name, submissions: 0, placements: 0 });
                    }
                    recruiterMap.get(name).placements++;
                });
                
                return Array.from(recruiterMap.values())
                    .map(perf => ({
                        ...perf,
                        conversionRate: perf.submissions > 0 ? (perf.placements / perf.submissions * 100).toFixed(1) : 0
                    }))
                    .sort((a, b) => b.submissions - a.submissions)
                    .slice(0, 10);
            }, [filteredSubmissions, filteredPlacements]);
            
            // Export CSV
            const exportCSV = () => {
                const rows = [
                    ['Recruiter', 'Submissions', 'Placements', 'Conversion Rate %']
                ];
                
                topPerformers.forEach(perf => {
                    rows.push([
                        perf.recruiter,
                        perf.submissions,
                        perf.placements,
                        perf.conversionRate
                    ]);
                });
                
                const csv = rows.map(row => row.join(',')).join('\\n');
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `analytics_${year}_${month}.csv`;
                a.click();
                window.URL.revokeObjectURL(url);
            };
            
            // Color for conversion rate
            const getConversionColor = (rate) => {
                if (rate >= 20) return 'text-green-600 font-semibold';
                if (rate >= 10) return 'text-yellow-600 font-semibold';
                return 'text-red-600 font-semibold';
            };
            
            // Pie chart colors
            const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1'];
            
            return (
                <div className="max-w-7xl mx-auto">
                    <div className="bg-white rounded-lg shadow-xl p-6 mb-6">
                        <div className="flex items-center justify-between mb-6">
                            <div className="flex items-center gap-3">
                                <span className="text-3xl">📊</span>
                                <h1 className="text-3xl font-bold text-gray-800">Analytics Dashboard</h1>
                            </div>
                            <a href="/" className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors">
                                ← Back to OAuth
                            </a>
                        </div>
                        
                        {/* Filters */}
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
                                <select
                                    value={year}
                                    onChange={(e) => setYear(parseInt(e.target.value))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                                >
                                    {[2024, 2025, 2026, 2027].map(y => (
                                        <option key={y} value={y}>{y}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Month</label>
                                <select
                                    value={month}
                                    onChange={(e) => setMonth(parseInt(e.target.value))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                                >
                                    {Array.from({ length: 12 }, (_, i) => i + 1).map(m => (
                                        <option key={m} value={m}>{new Date(2024, m - 1).toLocaleString('default', { month: 'long' })}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">View Mode</label>
                                <select
                                    value={viewMode}
                                    onChange={(e) => setViewMode(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                                >
                                    <option>By Recruiter</option>
                                    <option>By Week</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Recruiter</label>
                                <select
                                    value={selectedRecruiter}
                                    onChange={(e) => setSelectedRecruiter(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                                >
                                    <option>All</option>
                                    {recruiters.map(r => (
                                        <option key={r} value={r}>{r}</option>
                                    ))}
                                </select>
                            </div>
                        </div>
                        
                        {/* Action Buttons */}
                        <div className="flex gap-3 mb-6">
                            <button
                                onClick={fetchData}
                                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                            >
                                🔄 Refresh
                            </button>
                            <button
                                onClick={exportCSV}
                                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                            >
                                📥 Export CSV
                            </button>
                        </div>
                        
                        {error && (
                            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                                <p className="text-red-800">Error: {error}</p>
                            </div>
                        )}
                        
                        {loading ? (
                            <div className="text-center py-12">
                                <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
                                <p className="mt-4 text-gray-600">Loading data...</p>
                            </div>
                        ) : (
                            <>
                                {/* Stat Cards */}
                                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                                        <div className="text-sm text-gray-600 mb-1">Total Submissions</div>
                                        <div className="text-3xl font-bold text-blue-600">{stats.totalSubmissions}</div>
                                    </div>
                                    <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                                        <div className="text-sm text-gray-600 mb-1">Total Placements</div>
                                        <div className="text-3xl font-bold text-green-600">{stats.totalPlacements}</div>
                                    </div>
                                    <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                                        <div className="text-sm text-gray-600 mb-1">Conversion Rate</div>
                                        <div className={`text-3xl font-bold ${getConversionColor(stats.conversionRate)}`}>
                                            {stats.conversionRate}%
                                        </div>
                                    </div>
                                    <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                                        <div className="text-sm text-gray-600 mb-1">Number of Recruiters</div>
                                        <div className="text-3xl font-bold text-orange-600">{stats.numRecruiters}</div>
                                    </div>
                                </div>
                                
                                {/* Charts */}
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                                    {/* Bar Chart */}
                                    <div className="bg-white border border-gray-200 rounded-lg p-4">
                                        <h3 className="text-lg font-semibold text-gray-800 mb-4">Submissions vs Placements</h3>
                                        <ResponsiveContainer width="100%" height={300}>
                                            <BarChart data={chartData}>
                                                <CartesianGrid strokeDasharray="3 3" />
                                                <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
                                                <YAxis />
                                                <Tooltip />
                                                <Legend />
                                                <Bar dataKey="submissions" fill="#3b82f6" name="Submissions" />
                                                <Bar dataKey="placements" fill="#10b981" name="Placements" />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                    
                                    {/* Pie Chart */}
                                    <div className="bg-white border border-gray-200 rounded-lg p-4">
                                        <h3 className="text-lg font-semibold text-gray-800 mb-4">Submissions by Recruiter</h3>
                                        <ResponsiveContainer width="100%" height={300}>
                                            <PieChart>
                                                <Pie
                                                    data={pieData}
                                                    cx="50%"
                                                    cy="50%"
                                                    labelLine={false}
                                                    label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                                                    outerRadius={100}
                                                    fill="#8884d8"
                                                    dataKey="value"
                                                >
                                                    {pieData.map((entry, index) => (
                                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                                    ))}
                                                </Pie>
                                                <Tooltip />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                                
                                {/* Top Performers Table */}
                                <div className="bg-white border border-gray-200 rounded-lg p-4">
                                    <h3 className="text-lg font-semibold text-gray-800 mb-4">Top Performers</h3>
                                    <div className="overflow-x-auto">
                                        <table className="w-full">
                                            <thead>
                                                <tr className="border-b border-gray-200">
                                                    <th className="text-left py-2 px-4 font-semibold text-gray-700">Recruiter</th>
                                                    <th className="text-right py-2 px-4 font-semibold text-gray-700">Submissions</th>
                                                    <th className="text-right py-2 px-4 font-semibold text-gray-700">Placements</th>
                                                    <th className="text-right py-2 px-4 font-semibold text-gray-700">Conversion %</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {topPerformers.length === 0 ? (
                                                    <tr>
                                                        <td colSpan="4" className="text-center py-8 text-gray-500">No data available</td>
                                                    </tr>
                                                ) : (
                                                    topPerformers.map((perf, idx) => (
                                                        <tr key={idx} className="border-b border-gray-100 hover:bg-gray-50">
                                                            <td className="py-2 px-4 text-gray-800">{perf.recruiter}</td>
                                                            <td className="py-2 px-4 text-right text-gray-700">{perf.submissions}</td>
                                                            <td className="py-2 px-4 text-right text-gray-700">{perf.placements}</td>
                                                            <td className={`py-2 px-4 text-right ${getConversionColor(parseFloat(perf.conversionRate))}`}>
                                                                {perf.conversionRate}%
                                                            </td>
                                                        </tr>
                                                    ))
                                                )}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            );
        }

        // Wait for DOM and libraries to be ready
        function initApp() {
            const rootEl = document.getElementById('root');
            if (!rootEl) {
                console.error('Root element not found');
                return;
            }
            
            if (typeof React === 'undefined') {
                rootEl.innerHTML = '<div class="p-6 text-center bg-red-50 border border-red-200 rounded-lg"><p class="text-red-600 font-semibold">Error: React is not loaded</p></div>';
                return;
            }
            
            if (typeof ReactDOM === 'undefined') {
                rootEl.innerHTML = '<div class="p-6 text-center bg-red-50 border border-red-200 rounded-lg"><p class="text-red-600 font-semibold">Error: ReactDOM is not loaded</p></div>';
                return;
            }
            
            if (typeof window.Recharts === 'undefined') {
                rootEl.innerHTML = '<div class="p-6 text-center bg-red-50 border border-red-200 rounded-lg"><p class="text-red-600 font-semibold">Error: Recharts is not loaded</p></div>';
                return;
            }
            
            console.log('Rendering AnalyticsDashboard...');
            try {
                if (ReactDOM.createRoot) {
                    ReactDOM.createRoot(rootEl).render(<AnalyticsDashboard />);
                } else {
                    ReactDOM.render(<AnalyticsDashboard />, rootEl);
                }
                console.log('Component rendered successfully');
            } catch (err) {
                console.error('Render error:', err);
                rootEl.innerHTML = '<div class="p-6 text-center bg-red-50 border border-red-200 rounded-lg"><p class="text-red-600 font-semibold">Error rendering component</p><p class="text-red-500 text-sm mt-2">' + err.message + '</p></div>';
            }
        }
        
        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initApp);
        } else {
            // DOM already loaded, wait a bit for scripts
            setTimeout(initApp, 100);
        }
    </script>
</body>
</html>
'''

def load_tokens():
    """Load tokens from file"""
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading tokens: {e}")
    return None

def save_tokens(tokens):
    """Save tokens to file"""
    try:
        tokens['saved_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(TOKEN_FILE, 'w') as f:
            json.dump(tokens, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving tokens: {e}")
        return False

def exchange_for_bh_rest_token(access_token, rest_url=None):
    """Exchange OAuth access token for BhRestToken"""
    login_urls = []
    
    if rest_url:
        if not rest_url.endswith('/'):
            rest_url += '/'
        login_urls.append(f"{rest_url}login")
    
    login_urls.append('https://rest.bullhornstaffing.com/rest-services/login')
    
    for login_url in login_urls:
        try:
            response = requests.post(
                login_url,
                params={'version': '*', 'access_token': access_token},
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10
            )
            
            if response.ok:
                data = response.json()
                bh_rest_token = data.get('BhRestToken')
                new_rest_url = data.get('restUrl')
                
                if bh_rest_token:
                    print(f"✅ BhRestToken obtained successfully")
                    return bh_rest_token, new_rest_url
        except Exception as e:
            print(f"Error with {login_url}: {e}")
            continue
    
    return None, None

def refresh_session():
    """Background task to refresh BhRestToken"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running token refresh...")
    
    tokens = load_tokens()
    if not tokens or not tokens.get('access_token'):
        print("⚠️ No tokens to refresh")
        return
    
    try:
        # Re-exchange access_token for new BhRestToken
        access_token = tokens.get('access_token')
        rest_url = tokens.get('rest_url')
        
        bh_rest_token, new_rest_url = exchange_for_bh_rest_token(access_token, rest_url)
        
        if bh_rest_token:
            tokens['bh_rest_token'] = bh_rest_token
            if new_rest_url:
                tokens['rest_url'] = new_rest_url
            tokens['last_refresh'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            save_tokens(tokens)
            print(f"✅ Session refreshed successfully at {tokens['last_refresh']}")
        else:
            print("⚠️ Failed to refresh BhRestToken")
    except Exception as e:
        print(f"❌ Refresh error: {e}")

# Schedule auto-refresh
scheduler.add_job(
    func=refresh_session,
    trigger="interval",
    minutes=REFRESH_INTERVAL_MINUTES,
    id='token_refresh',
    name='Refresh BhRestToken',
    replace_existing=True
)

@app.route('/')
def home():
    """Home page - show status"""
    tokens = load_tokens()
    session_status = "Active" if tokens and tokens.get('bh_rest_token') else "Not authenticated"
    return render_template_string(
        HTML_TEMPLATE, 
        tokens=tokens, 
        session_status=session_status,
        refresh_interval=REFRESH_INTERVAL_MINUTES
    )

@app.route('/analytics')
def analytics():
    """Analytics dashboard page"""
    return render_template_string(ANALYTICS_TEMPLATE)

@app.route('/login')
def login():
    """Redirect to Bullhorn OAuth"""
    if not CLIENT_ID:
        return render_template_string(HTML_TEMPLATE, 
            error=True, 
            message="CLIENT_ID not configured. Set environment variable BULLHORN_CLIENT_ID")
    
    auth_url = f"https://auth.bullhornstaffing.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}"
    return redirect(auth_url)

@app.route('/oauth/callback')
def callback():
    """Handle OAuth callback - AUTOMATICALLY exchanges for BhRestToken"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return render_template_string(HTML_TEMPLATE, 
            error=True, 
            message=f"OAuth error: {error}")
    
    if not code:
        return render_template_string(HTML_TEMPLATE, 
            error=True, 
            message="No authorization code received")
    
    try:
        # Step 1: Exchange code for OAuth tokens
        token_url = 'https://auth.bullhornstaffing.com/oauth/token'
        params = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI
        }
        
        response = requests.post(token_url, params=params)
        data = response.json()
        
        if not response.ok or 'access_token' not in data:
            return render_template_string(HTML_TEMPLATE, 
                error=True, 
                message=f"Token exchange failed: {data.get('error_description', data)}")
        
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        rest_url = data.get('restUrl')
        
        # Step 2: AUTOMATICALLY exchange for BhRestToken
        print("Automatically exchanging for BhRestToken...")
        bh_rest_token, new_rest_url = exchange_for_bh_rest_token(access_token, rest_url)
        
        if new_rest_url:
            rest_url = new_rest_url
        
        # Step 3: Save everything
        tokens = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'rest_url': rest_url,
            'bh_rest_token': bh_rest_token,
            'expires_in': data.get('expires_in'),
            'last_refresh': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        save_tokens(tokens)
        
        if bh_rest_token:
            return render_template_string(HTML_TEMPLATE, 
                tokens=tokens,
                session_status="Active",
                refresh_interval=REFRESH_INTERVAL_MINUTES,
                message="✅ Authentication complete! BhRestToken obtained automatically. Auto-refresh enabled.")
        else:
            return render_template_string(HTML_TEMPLATE, 
                tokens=tokens,
                session_status="Partial",
                refresh_interval=REFRESH_INTERVAL_MINUTES,
                error=True,
                message="⚠️ OAuth tokens saved but BhRestToken exchange failed. Click 'Test Connection' to retry.")
    
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, 
            error=True, 
            message=f"Error: {str(e)}")

@app.route('/test')
def test():
    """Test API connection and refresh if needed"""
    tokens = load_tokens()
    
    if not tokens or not tokens.get('access_token'):
        return render_template_string(HTML_TEMPLATE, 
            error=True, 
            message="No tokens found. Please authenticate first.")
    
    try:
        rest_url = tokens.get('rest_url')
        bh_rest_token = tokens.get('bh_rest_token')
        
        # If no BhRestToken, try to get one
        if not bh_rest_token:
            access_token = tokens.get('access_token')
            bh_rest_token, new_rest_url = exchange_for_bh_rest_token(access_token, rest_url)
            
            if bh_rest_token:
                tokens['bh_rest_token'] = bh_rest_token
                if new_rest_url:
                    tokens['rest_url'] = new_rest_url
                    rest_url = new_rest_url
                tokens['last_refresh'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                save_tokens(tokens)
            else:
                return render_template_string(HTML_TEMPLATE, 
                    tokens=tokens,
                    session_status="Failed",
                    refresh_interval=REFRESH_INTERVAL_MINUTES,
                    error=True, 
                    message="Failed to obtain BhRestToken. Please re-authenticate.")
        
        # Test connection with ping
        if not rest_url.endswith('/'):
            rest_url += '/'
        
        ping_url = f"{rest_url}ping"
        response = requests.get(ping_url, params={'BhRestToken': bh_rest_token})
        
        if response.ok:
            data = response.json()
            expires = datetime.fromtimestamp(data['sessionExpires']/1000).strftime('%Y-%m-%d %H:%M:%S')
            return render_template_string(HTML_TEMPLATE, 
                tokens=tokens,
                session_status="Active",
                refresh_interval=REFRESH_INTERVAL_MINUTES,
                message=f"✅ Connection successful! Session expires: {expires}")
        else:
            return render_template_string(HTML_TEMPLATE, 
                tokens=tokens,
                session_status="Error",
                refresh_interval=REFRESH_INTERVAL_MINUTES,
                error=True, 
                message=f"Connection test failed: {response.text}")
    
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, 
            tokens=tokens,
            session_status="Error",
            refresh_interval=REFRESH_INTERVAL_MINUTES,
            error=True, 
            message=f"Error: {str(e)}")

@app.route('/logout')
def logout():
    """Clear tokens"""
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        return render_template_string(HTML_TEMPLATE, 
            message="Tokens cleared successfully")
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, 
            error=True, 
            message=f"Error clearing tokens: {str(e)}")

# ==================== API ENDPOINTS ====================

@app.route('/api/tokens')
def api_tokens():
    """API endpoint to get current tokens"""
    tokens = load_tokens()
    if tokens:
        # Don't expose sensitive tokens in API
        safe_tokens = {
            'rest_url': tokens.get('rest_url'),
            'last_refresh': tokens.get('last_refresh'),
            'saved_at': tokens.get('saved_at'),
            'has_bh_rest_token': bool(tokens.get('bh_rest_token'))
        }
        return jsonify(safe_tokens)
    return jsonify({'error': 'No tokens found'}), 404

@app.route('/api/status')
def api_status():
    """Check session status"""
    tokens = load_tokens()
    
    if not tokens or not tokens.get('bh_rest_token'):
        return jsonify({
            'status': 'not_authenticated',
            'message': 'No active session'
        }), 401
    
    try:
        rest_url = tokens.get('rest_url')
        if not rest_url.endswith('/'):
            rest_url += '/'
        
        ping_url = f"{rest_url}ping"
        response = requests.get(
            ping_url,
            params={'BhRestToken': tokens.get('bh_rest_token')},
            timeout=5
        )
        
        if response.ok:
            data = response.json()
            expires = datetime.fromtimestamp(data['sessionExpires']/1000)
            return jsonify({
                'status': 'active',
                'session_expires': expires.strftime('%Y-%m-%d %H:%M:%S'),
                'last_refresh': tokens.get('last_refresh'),
                'auto_refresh_enabled': True,
                'refresh_interval_minutes': REFRESH_INTERVAL_MINUTES
            })
        else:
            return jsonify({
                'status': 'expired',
                'message': 'Session expired, attempting refresh...'
            }), 401
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    """Manually trigger token refresh"""
    refresh_session()
    tokens = load_tokens()
    
    if tokens and tokens.get('bh_rest_token'):
        return jsonify({
            'status': 'success',
            'last_refresh': tokens.get('last_refresh'),
            'message': 'Tokens refreshed successfully'
        })
    else:
        return jsonify({
            'status': 'failed',
            'message': 'Token refresh failed'
        }), 500

@app.route('/api/submissions')
def api_submissions():
    """Fetch submissions from Bullhorn"""
    tokens = load_tokens()
    
    if not tokens or not tokens.get('bh_rest_token'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Get parameters
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', 1, type=int)
    
    # Calculate date range
    start_date = f"{year}-{month:02d}-01"
    
    # Get last day of month
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day}"
    
    # Convert to milliseconds
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    
    # Query Bullhorn
    try:
        rest_url = tokens['rest_url']
        if not rest_url.endswith('/'):
            rest_url += '/'
        
        url = f"{rest_url}query/JobSubmission"
        
        fields = [
            'id', 'dateAdded', 'dateLastModified', 'status',
            'candidate(id,firstName,lastName,email,phone)',
            'jobOrder(id,title,clientCorporation(id,name),owner(id,firstName,lastName))',
            'source', 'isDeleted'
        ]
        
        params = {
            'BhRestToken': tokens['bh_rest_token'],
            'where': f"dateAdded>={start_ms} AND dateAdded<={end_ms}",
            'fields': ','.join(fields),
            'orderBy': '-dateAdded',
            'count': 500
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        submissions = data.get('data', [])
        
        return jsonify({
            'success': True,
            'count': len(submissions),
            'year': year,
            'month': month,
            'data': submissions
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/placements')
def api_placements():
    """Fetch placements from Bullhorn"""
    tokens = load_tokens()
    
    if not tokens or not tokens.get('bh_rest_token'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Get parameters
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', 1, type=int)
    
    # Calculate date range
    start_date = f"{year}-{month:02d}-01"
    
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day}"
    
    # Convert to milliseconds
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    
    # Query Bullhorn
    try:
        rest_url = tokens['rest_url']
        if not rest_url.endswith('/'):
            rest_url += '/'
        
        url = f"{rest_url}query/Placement"
        
        fields = [
            'id', 'dateAdded', 'dateBegin', 'dateEnd',
            'dateLastModified', 'status', 'payRate', 'billRate',
            'candidate(id,firstName,lastName,email,phone)',
            'jobOrder(id,title,clientCorporation(id,name),owner(id,firstName,lastName))'
        ]
        
        params = {
            'BhRestToken': tokens['bh_rest_token'],
            'where': f"dateAdded>={start_ms} AND dateAdded<={end_ms}",
            'fields': ','.join(fields),
            'orderBy': '-dateAdded',
            'count': 500
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        placements = data.get('data', [])
        
        return jsonify({
            'success': True,
            'count': len(placements),
            'year': year,
            'month': month,
            'data': placements
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"Starting Bullhorn OAuth server on port {port}")
    print(f"Auto-refresh enabled: every {REFRESH_INTERVAL_MINUTES} minutes")
    app.run(host='0.0.0.0', port=port, debug=False)
