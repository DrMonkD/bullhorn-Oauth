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
                    <div class="bg-white p-2 rounded">GET /api/submissions?year=YYYY&month=M - Fetch submissions (basic)</div>
                    <div class="bg-white p-2 rounded">GET /api/submissions/detailed?year=YYYY&month=M - Fetch submissions with full details (candidate, job, client, owner)</div>
                    <div class="bg-white p-2 rounded">GET /api/placements?year=YYYY&month=M - Fetch placements (minimal fields)</div>
                    <div class="bg-white p-2 rounded">GET /api/placements/detailed?year=YYYY&month=M - Fetch placements with full details (candidate, job, client, owner)</div>
                    <div class="bg-white p-2 rounded">GET /api/analytics/weekly?year=YYYY&month=M - Weekly analytics with recruiter breakdown</div>
                    <div class="bg-white p-2 rounded">GET /api/analytics/monthly?year=YYYY&month=M - Monthly analytics with recruiter breakdown</div>
                    <div class="bg-white p-2 rounded">GET /api/analytics/recruiters?year=YYYY&month=M - Recruiter leaderboard</div>
                    <div class="bg-white p-2 rounded">GET /api/meta/JobSubmission - All queryable JobSubmission fields</div>
                    <div class="bg-white p-2 rounded">GET /api/meta/Placement - All queryable Placement fields</div>
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
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
</head>
<body class="bg-gradient-to-br from-blue-50 to-indigo-100 min-h-screen p-6">
    <div id="root">
        <div class="p-6 text-center">
            <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
            <p class="mt-4 text-gray-600">Loading dashboard...</p>
        </div>
    </div>
    
    <script type="text/babel">
        const { useState, useEffect, useMemo, useRef } = React;
        
        // Bar chart via Chart.js (works from CDN)
        function BarChartCanvas({ data, labelsKey, datasets, title, height }) {
            const canvasRef = useRef(null);
            const chartRef = useRef(null);
            const ChartLib = typeof window !== 'undefined' ? window.Chart : (typeof Chart !== 'undefined' ? Chart : null);
            
            useEffect(function() {
                if (!ChartLib || !data || data.length === 0) return;
                var ctx = canvasRef.current && canvasRef.current.getContext('2d');
                if (!ctx) return;
                if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; }
                chartRef.current = new ChartLib(ctx, {
                    type: 'bar',
                    data: {
                        labels: data.map(function(d) { return d[labelsKey]; }),
                        datasets: datasets.map(function(ds) {
                            return { label: ds.label, data: data.map(function(d) { return d[ds.dataKey] || 0; }), backgroundColor: ds.color };
                        })
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { position: 'top' } },
                        scales: { y: { beginAtZero: true } }
                    }
                });
                return function() { if (chartRef.current) chartRef.current.destroy(); };
            }, [data, labelsKey]);
            
            if (!ChartLib) return <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg"><p className="text-yellow-800">Charts unavailable (Chart.js failed to load).</p></div>;
            if (!data || data.length === 0) return null;
            return (
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                    {title && <h3 className="text-lg font-semibold text-gray-800 mb-4">{title}</h3>}
                    <div style={{ "{{" }}"height": (height || 300) + "px"{{ "}}" }}>
                        <canvas ref={canvasRef}></canvas>
                    </div>
                </div>
            );
        }

        function AnalyticsDashboard() {
            const [submissions, setSubmissions] = useState([]);
            const [placements, setPlacements] = useState([]);
            const [loading, setLoading] = useState(true);
            const [error, setError] = useState(null);
            
            // View mode: 'basic', 'recruiter', 'detailed', 'detailed_placements'
            const [viewMode, setViewMode] = useState('basic');
            
            // Detailed submissions data
            const [detailedSubmissions, setDetailedSubmissions] = useState([]);
            
            // Quick filters for Detailed view (client-side)
            const [filterOwner, setFilterOwner] = useState('');
            const [filterStatus, setFilterStatus] = useState('');
            
            // Detailed placements data and filters
            const [detailedPlacements, setDetailedPlacements] = useState([]);
            const [filterPlacementOwner, setFilterPlacementOwner] = useState('');
            const [filterPlacementStatus, setFilterPlacementStatus] = useState('');
            
            // Analytics data
            const [recruitersData, setRecruitersData] = useState([]);
            
            // Date/period: 'week'|'month'|'year'|'custom'
            const [periodType, setPeriodType] = useState('month');
            const [year, setYear] = useState(new Date().getFullYear());
            const [month, setMonth] = useState(new Date().getMonth() + 1);
            const [weekDate, setWeekDate] = useState(function(){
                var d = new Date();
                return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
            });
            const [startDate, setStartDate] = useState(function(){
                var d = new Date();
                return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-01';
            });
            const [endDate, setEndDate] = useState(function(){
                var d = new Date();
                var last = new Date(d.getFullYear(), d.getMonth()+1, 0);
                return last.getFullYear() + '-' + String(last.getMonth()+1).padStart(2,'0') + '-' + String(last.getDate()).padStart(2,'0');
            });
            
            // Compute start/end (YYYY-MM-DD) from period
            const dateRange = useMemo(function(){
                function ym(d){ return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }
                if (periodType === 'week' && weekDate) {
                    var d = new Date(weekDate + 'T12:00:00');
                    var day = d.getDay();
                    var monOff = day === 0 ? -6 : 1 - day;
                    var mon = new Date(d); mon.setDate(mon.getDate() + monOff);
                    var sun = new Date(mon); sun.setDate(sun.getDate() + 6);
                    return { start: ym(mon), end: ym(sun) };
                }
                if (periodType === 'month') {
                    var last = new Date(year, month, 0);
                    return { start: year+'-'+String(month).padStart(2,'0')+'-01', end: year+'-'+String(month).padStart(2,'0')+'-'+String(last.getDate()).padStart(2,'0') };
                }
                if (periodType === 'year') {
                    return { start: year+'-01-01', end: year+'-12-31' };
                }
                return { start: startDate || '2020-01-01', end: endDate || '2030-12-31' };
            }, [periodType, year, month, weekDate, startDate, endDate]);
            
            // Fetch basic data (existing)
            const fetchBasicData = async () => {
                setLoading(true);
                setError(null);
                try {
                    var r = dateRange;
                    console.log('Fetching data for', r.start, 'to', r.end);
                    const [subsRes, placeRes] = await Promise.all([
                        fetch('/api/submissions?start=' + encodeURIComponent(r.start) + '&end=' + encodeURIComponent(r.end)),
                        fetch('/api/placements?start=' + encodeURIComponent(r.start) + '&end=' + encodeURIComponent(r.end))
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
            
            // Fetch analytics data
            const fetchAnalyticsData = async () => {
                setLoading(true);
                setError(null);
                var r = dateRange;
                var q = 'start=' + encodeURIComponent(r.start) + '&end=' + encodeURIComponent(r.end);
                try {
                    if (viewMode === 'recruiter') {
                        const res = await fetch('/api/analytics/recruiters?' + q);
                        if (res.ok) {
                            const data = await res.json();
                            setRecruitersData(data.recruiters || []);
                        } else {
                            throw new Error('Failed to fetch recruiter data');
                        }
                    } else if (viewMode === 'detailed') {
                        const res = await fetch('/api/submissions/detailed?' + q);
                        if (res.ok) {
                            const data = await res.json();
                            setDetailedSubmissions(data.data || []);
                        } else {
                            const errorText = await res.text();
                            throw new Error('Failed to fetch detailed submissions: ' + errorText.substring(0, 100));
                        }
                    } else if (viewMode === 'detailed_placements') {
                        const res = await fetch('/api/placements/detailed?' + q);
                        if (res.ok) {
                            const data = await res.json();
                            setDetailedPlacements(data.data || []);
                        } else {
                            const errorText = await res.text();
                            throw new Error('Failed to fetch detailed placements: ' + errorText.substring(0, 100));
                        }
                    }
                } catch (err) {
                    setError(err.message || 'Failed to fetch analytics data');
                } finally {
                    setLoading(false);
                }
            };
            
            useEffect(function(){
                if (viewMode === 'basic') fetchBasicData();
                else fetchAnalyticsData();
            }, [dateRange.start, dateRange.end, viewMode]);
            
            // Stats (minimal fields: id, dateAdded only)
            const stats = useMemo(() => {
                const totalSubmissions = submissions.length;
                const totalPlacements = placements.length;
                const conversionRate = totalSubmissions > 0 ? (totalPlacements / totalSubmissions * 100).toFixed(1) : 0;
                return {
                    totalSubmissions,
                    totalPlacements,
                    conversionRate: parseFloat(conversionRate)
                };
            }, [submissions, placements]);
            
            // Chart data: By Week only (we have dateAdded)
            const getWeekNumber = (dateMs) => {
                const date = new Date(dateMs);
                const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
                const dayNum = d.getUTCDay() || 7;
                d.setUTCDate(d.getUTCDate() + 4 - dayNum);
                const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
                return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
            };
            
            const chartData = useMemo(() => {
                const weekMap = new Map();
                submissions.forEach(sub => {
                    if (!sub.dateAdded) return;
                    const week = getWeekNumber(sub.dateAdded);
                    const key = `Week ${week}`;
                    if (!weekMap.has(key)) weekMap.set(key, { name: key, submissions: 0, placements: 0 });
                    weekMap.get(key).submissions++;
                });
                placements.forEach(place => {
                    if (!place.dateAdded) return;
                    const week = getWeekNumber(place.dateAdded);
                    const key = `Week ${week}`;
                    if (!weekMap.has(key)) weekMap.set(key, { name: key, submissions: 0, placements: 0 });
                    weekMap.get(key).placements++;
                });
                return Array.from(weekMap.values()).sort((a, b) => {
                    const weekA = parseInt(a.name.replace('Week ', ''), 10);
                    const weekB = parseInt(b.name.replace('Week ', ''), 10);
                    return weekA - weekB;
                });
            }, [submissions, placements]);
            
            // Export CSV (by-week data)
            const exportCSV = () => {
                const rows = [['Week', 'Submissions', 'Placements']];
                chartData.forEach(d => rows.push([d.name, String(d.submissions), String(d.placements)]));
                const csv = rows.map(row => row.join(',')).join('\\n');
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'analytics_' + dateRange.start + '_' + dateRange.end + '.csv';
                a.click();
                window.URL.revokeObjectURL(url);
            };
            
            const getConversionColor = (rate) => {
                if (rate >= 20) return 'text-green-600 font-semibold';
                if (rate >= 10) return 'text-yellow-600 font-semibold';
                return 'text-red-600 font-semibold';
            };
            
            // Detailed: unique owners/statuses and filtered list
            const detailedMeta = useMemo(function(){
                var owners = [], statuses = [];
                detailedSubmissions.forEach(function(s){
                    // #region agent log
                    var oRaw = s.ownerName, tRaw = s.status;
                    if (typeof oRaw !== 'string' || typeof tRaw !== 'string') {
                        fetch('http://127.0.0.1:7242/ingest/17a4d052-773d-4fbd-aff1-ea318feaa11e',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'detailedMeta:nonString',message:'owner or status not string',data:{ownerType:typeof oRaw,ownerVal:oRaw,statusType:typeof tRaw,statusVal:tRaw},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'A'})}).catch(function(){});
                    }
                    // #endregion
                    var o = String(oRaw != null ? oRaw : '').trim();
                    var t = String(tRaw != null ? tRaw : '').trim();
                    if (o && owners.indexOf(o) < 0) owners.push(o);
                    if (t && statuses.indexOf(t) < 0) statuses.push(t);
                });
                owners.sort(); statuses.sort();
                return { owners: owners, statuses: statuses };
            }, [detailedSubmissions]);
            const filteredDetailed = useMemo(function(){
                var l = detailedSubmissions;
                if (filterOwner) l = l.filter(function(s){ return String(s.ownerName != null ? s.ownerName : '').toLowerCase().indexOf(filterOwner.toLowerCase()) >= 0; });
                if (filterStatus) l = l.filter(function(s){ return String(s.status != null ? s.status : '') === filterStatus; });
                return l;
            }, [detailedSubmissions, filterOwner, filterStatus]);
            
            // Detailed placements: unique owners/statuses and filtered list
            const detailedPlacementsMeta = useMemo(function(){
                var owners = [], statuses = [];
                detailedPlacements.forEach(function(p){
                    var o = String(p.ownerName != null ? p.ownerName : '').trim();
                    var t = String(p.status != null ? p.status : '').trim();
                    if (o && owners.indexOf(o) < 0) owners.push(o);
                    if (t && statuses.indexOf(t) < 0) statuses.push(t);
                });
                owners.sort(); statuses.sort();
                return { owners: owners, statuses: statuses };
            }, [detailedPlacements]);
            const filteredDetailedPlacements = useMemo(function(){
                var l = detailedPlacements;
                if (filterPlacementOwner) l = l.filter(function(p){ return String(p.ownerName != null ? p.ownerName : '').toLowerCase().indexOf(filterPlacementOwner.toLowerCase()) >= 0; });
                if (filterPlacementStatus) l = l.filter(function(p){ return String(p.status != null ? p.status : '') === filterPlacementStatus; });
                return l;
            }, [detailedPlacements, filterPlacementOwner, filterPlacementStatus]);
            
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
                        
                        {/* View Mode Toggle */}
                        <div className="mb-4 p-4 bg-indigo-50 border border-indigo-200 rounded-lg">
                            <label className="block text-sm font-medium text-gray-700 mb-2">View Mode</label>
                            <div className="flex gap-2 flex-wrap">
                                <button
                                    onClick={() => setViewMode('basic')}
                                    className={`px-4 py-2 rounded-lg transition-colors ${
                                        viewMode === 'basic' 
                                            ? 'bg-indigo-600 text-white' 
                                            : 'bg-white text-gray-700 hover:bg-gray-100'
                                    }`}
                                >
                                    Basic
                                </button>
                                <button
                                    onClick={() => setViewMode('recruiter')}
                                    className={`px-4 py-2 rounded-lg transition-colors ${
                                        viewMode === 'recruiter' 
                                            ? 'bg-indigo-600 text-white' 
                                            : 'bg-white text-gray-700 hover:bg-gray-100'
                                    }`}
                                >
                                    Recruiter View
                                </button>
                                <button
                                    onClick={() => setViewMode('detailed')}
                                    className={`px-4 py-2 rounded-lg transition-colors ${
                                        viewMode === 'detailed' 
                                            ? 'bg-indigo-600 text-white' 
                                            : 'bg-white text-gray-700 hover:bg-gray-100'
                                    }`}
                                >
                                    📋 Detailed Submissions
                                </button>
                                <button
                                    onClick={() => setViewMode('detailed_placements')}
                                    className={`px-4 py-2 rounded-lg transition-colors ${
                                        viewMode === 'detailed_placements' 
                                            ? 'bg-indigo-600 text-white' 
                                            : 'bg-white text-gray-700 hover:bg-gray-100'
                                    }`}
                                >
                                    📋 Detailed Placements
                                </button>
                            </div>
                        </div>
                        
                        {/* Date / Period */}
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Period</label>
                                <select
                                    value={periodType}
                                    onChange={(e) => setPeriodType(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                                >
                                    <option value="week">Week</option>
                                    <option value="month">Month</option>
                                    <option value="year">Year</option>
                                    <option value="custom">Custom range</option>
                                </select>
                            </div>
                            {periodType === 'week' && (
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Date in week</label>
                                    <input type="date" value={weekDate} onChange={(e) => setWeekDate(e.target.value)}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500" />
                                </div>
                            )}
                            {periodType === 'month' && (
                                <>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
                                        <select value={year} onChange={(e) => setYear(parseInt(e.target.value))}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500">
                                            {[2024, 2025, 2026, 2027].map(function(y){ return <option key={y} value={y}>{y}</option>; })}
                                        </select>
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Month</label>
                                        <select value={month} onChange={(e) => setMonth(parseInt(e.target.value))}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500">
                                            {Array.from({ length: 12 }, function(_, i){ var m = i + 1; return <option key={m} value={m}>{new Date(2024, m - 1).toLocaleString('default', { month: 'long' })}</option>; })}
                                        </select>
                                    </div>
                                </>
                            )}
                            {periodType === 'year' && (
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
                                    <select value={year} onChange={(e) => setYear(parseInt(e.target.value))}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500">
                                        {[2024, 2025, 2026, 2027].map(function(y){ return <option key={y} value={y}>{y}</option>; })}
                                    </select>
                                </div>
                            )}
                            {periodType === 'custom' && (
                                <>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">From</label>
                                        <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500" />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">To</label>
                                        <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500" />
                                    </div>
                                </>
                            )}
                        </div>
                        
                        {/* Action Buttons */}
                        <div className="flex gap-3 mb-6">
                            <button
                                onClick={() => {
                                    if (viewMode === 'basic') fetchBasicData();
                                    else fetchAnalyticsData();
                                }}
                                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                            >
                                🔄 Refresh
                            </button>
                            {viewMode === 'basic' && (
                                <button
                                    onClick={() => {
                                        const rows = [['Week', 'Submissions', 'Placements']];
                                        chartData.forEach(d => rows.push([d.name, String(d.submissions), String(d.placements)]));
                                        const csv = rows.map(row => row.join(',')).join('\\n');
                                        const blob = new Blob([csv], { type: 'text/csv' });
                                        const url = window.URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = 'analytics_' + dateRange.start + '_' + dateRange.end + '.csv';
                                        a.click();
                                        window.URL.revokeObjectURL(url);
                                    }}
                                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                                >
                                    📥 Export CSV
                                </button>
                            )}
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
                                {viewMode === 'basic' && (
                                    <>
                                        {/* Basic View - Existing */}
                                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
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
                                        </div>
                                        
                                        <div className="mb-6">
                                            <BarChartCanvas
                                                data={chartData}
                                                labelsKey="name"
                                                datasets={[
                                                    { dataKey: 'submissions', label: 'Submissions', color: 'rgba(59,130,246,0.8)' },
                                                    { dataKey: 'placements', label: 'Placements', color: 'rgba(16,185,129,0.8)' }
                                                ]}
                                                title="Submissions vs Placements by Week"
                                                height={300}
                                            />
                                        </div>
                                    </>
                                )}
                                
                                {viewMode === 'recruiter' && (
                                    <>
                                        {/* Recruiter Leaderboard */}
                                        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
                                            <h3 className="text-lg font-semibold text-gray-800 mb-4">Recruiter Leaderboard</h3>
                                            <div className="overflow-x-auto">
                                                <table className="w-full">
                                                    <thead>
                                                        <tr className="border-b border-gray-200">
                                                            <th className="text-left py-2 px-4 font-semibold text-gray-700">Recruiter</th>
                                                            <th className="text-right py-2 px-4 font-semibold text-gray-700">Submissions</th>
                                                            <th className="text-right py-2 px-4 font-semibold text-gray-700">Presented</th>
                                                            <th className="text-right py-2 px-4 font-semibold text-gray-700">Placed</th>
                                                            <th className="text-right py-2 px-4 font-semibold text-gray-700">Conversion %</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {recruitersData.length === 0 ? (
                                                            <tr>
                                                                <td colSpan="5" className="text-center py-8 text-gray-500">No recruiter data available</td>
                                                            </tr>
                                                        ) : (
                                                            recruitersData.map((rec, idx) => {
                                                                const conversion = rec.totalSubmissions > 0 
                                                                    ? (rec.totalPlacements / rec.totalSubmissions * 100).toFixed(1) 
                                                                    : 0;
                                                                return (
                                                                    <tr key={idx} className="border-b border-gray-100 hover:bg-gray-50">
                                                                        <td className="py-2 px-4 text-gray-800">{rec.name}</td>
                                                        <td className="py-2 px-4 text-right text-gray-700">{rec.totalSubmissions}</td>
                                                        <td className="py-2 px-4 text-right text-gray-700">
                                                            {(rec.statusBreakdown || {})['Presented'] || 0}
                                                        </td>
                                                        <td className="py-2 px-4 text-right text-gray-700">{rec.totalPlacements}</td>
                                                                        <td className={`py-2 px-4 text-right ${getConversionColor(parseFloat(conversion))}`}>
                                                                            {conversion}%
                                                                        </td>
                                                                    </tr>
                                                                );
                                                            })
                                                        )}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    </>
                                )}
                                
                                {viewMode === 'detailed' && (
                                    <>
                                        {/* Detailed Submissions Table */}
                                        <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                                            <div className="flex items-center justify-between flex-wrap gap-4">
                                                <div>
                                                    <h3 className="text-lg font-semibold text-blue-800">Detailed Submissions</h3>
                                                    <p className="text-sm text-blue-600">Showing all submissions with candidate, job, status, and owner details</p>
                                                </div>
                                                <div className="text-2xl font-bold text-blue-600">{filteredDetailed.length} records</div>
                                            </div>
                                            {/* Quick filters */}
                                            <div className="mt-3 flex flex-wrap gap-3 items-center">
                                                <span className="text-sm font-medium text-gray-700">Quick filters:</span>
                                                <select value={filterOwner} onChange={(e) => setFilterOwner(e.target.value)}
                                                    className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500">
                                                    <option value="">All owners</option>
                                                    {detailedMeta.owners.map(function(o){ return <option key={o} value={o}>{o}</option>; })}
                                                </select>
                                                <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}
                                                    className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500">
                                                    <option value="">All statuses</option>
                                                    {detailedMeta.statuses.map(function(s){ return <option key={s} value={s}>{s}</option>; })}
                                                </select>
                                                {(filterOwner || filterStatus) && (
                                                    <button type="button" onClick={() => { setFilterOwner(''); setFilterStatus(''); }}
                                                        className="text-sm text-indigo-600 hover:underline">Clear filters</button>
                                                )}
                                            </div>
                                        </div>
                                        
                                        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
                                            <div className="overflow-x-auto">
                                                <table className="w-full text-sm">
                                                    <thead>
                                                        <tr className="border-b-2 border-gray-300 bg-gray-50">
                                                            <th className="text-left py-3 px-3 font-semibold text-gray-700">ID</th>
                                                            <th className="text-left py-3 px-3 font-semibold text-gray-700">Date</th>
                                                            <th className="text-left py-3 px-3 font-semibold text-gray-700">Candidate</th>
                                                            <th className="text-left py-3 px-3 font-semibold text-gray-700">Job Title</th>
                                                            <th className="text-left py-3 px-3 font-semibold text-gray-700">Client</th>
                                                            <th className="text-left py-3 px-3 font-semibold text-gray-700">Status</th>
                                                            <th className="text-left py-3 px-3 font-semibold text-gray-700">Owner</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {filteredDetailed.length === 0 ? (
                                                            <tr>
                                                                <td colSpan="7" className="text-center py-12 text-gray-500">
                                                                    <div className="text-4xl mb-2">📭</div>
                                                                    {detailedSubmissions.length === 0 ? 'No submissions found for this period' : 'No rows match the filters'}
                                                                </td>
                                                            </tr>
                                                        ) : (
                                                            filteredDetailed.map((sub, idx) => {
                                                                const statusColor = {
                                                                    'Submitted': 'bg-blue-100 text-blue-800',
                                                                    'Presented': 'bg-yellow-100 text-yellow-800',
                                                                    'Client Review': 'bg-purple-100 text-purple-800',
                                                                    'Interview': 'bg-orange-100 text-orange-800',
                                                                    'Offered': 'bg-green-100 text-green-800',
                                                                    'Placed': 'bg-green-200 text-green-900',
                                                                    'Rejected': 'bg-red-100 text-red-800',
                                                                    'Withdrawn': 'bg-gray-100 text-gray-800'
                                                                }[sub.status] || 'bg-gray-100 text-gray-700';
                                                                
                                                                return (
                                                                    <tr key={sub.id || idx} className="border-b border-gray-100 hover:bg-blue-50 transition-colors">
                                                                        <td className="py-2 px-3 text-gray-600 font-mono text-xs">{sub.id}</td>
                                                                        <td className="py-2 px-3 text-gray-700 whitespace-nowrap">{sub.dateFormatted || 'N/A'}</td>
                                                                        <td className="py-2 px-3 text-gray-800 font-medium">{sub.candidateName}</td>
                                                                        <td className="py-2 px-3 text-gray-700 max-w-xs truncate" title={sub.jobTitle}>{sub.jobTitle}</td>
                                                                        <td className="py-2 px-3 text-gray-600">{sub.clientName}</td>
                                                                        <td className="py-2 px-3">
                                                                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColor}`}>
                                                                                {sub.status}
                                                                            </span>
                                                                        </td>
                                                                        <td className="py-2 px-3 text-gray-700">{sub.ownerName}</td>
                                                                    </tr>
                                                                );
                                                            })
                                                        )}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                        
                                        {/* Export CSV for detailed (exports filtered rows) */}
                                        {detailedSubmissions.length > 0 && (
                                            <button
                                                onClick={() => {
                                                    var rows = [['ID', 'Date', 'Candidate', 'Job Title', 'Client', 'Status', 'Owner']];
                                                    filteredDetailed.forEach(function(s){
                                                        rows.push([String(s.id || ''), s.dateFormatted || '', s.candidateName || '', s.jobTitle || '', s.clientName || '', s.status || '', s.ownerName || '']);
                                                    });
                                                    var csv = rows.map(function(row){ return row.map(function(c){ return '"' + (c || '').replace(/"/g, '""') + '"'; }).join(','); }).join('\\n');
                                                    var blob = new Blob([csv], { type: 'text/csv' });
                                                    var url = window.URL.createObjectURL(blob);
                                                    var a = document.createElement('a');
                                                    a.href = url;
                                                    a.download = 'detailed_submissions_' + dateRange.start + '_' + dateRange.end + '.csv';
                                                    a.click();
                                                    window.URL.revokeObjectURL(url);
                                                }}
                                                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                                            >
                                                📥 Export Detailed CSV
                                            </button>
                                        )}
                                    </>
                                )}
                                
                                {viewMode === 'detailed_placements' && (
                                    <>
                                        {/* Detailed Placements Table - same structure as Detailed Submissions */}
                                        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg">
                                            <div className="flex items-center justify-between flex-wrap gap-4">
                                                <div>
                                                    <h3 className="text-lg font-semibold text-green-800">Detailed Placements</h3>
                                                    <p className="text-sm text-green-600">Showing all placements with candidate, job, status, and owner details</p>
                                                </div>
                                                <div className="text-2xl font-bold text-green-600">{filteredDetailedPlacements.length} records</div>
                                            </div>
                                            {/* Quick filters */}
                                            <div className="mt-3 flex flex-wrap gap-3 items-center">
                                                <span className="text-sm font-medium text-gray-700">Quick filters:</span>
                                                <select value={filterPlacementOwner} onChange={(e) => setFilterPlacementOwner(e.target.value)}
                                                    className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500">
                                                    <option value="">All owners</option>
                                                    {detailedPlacementsMeta.owners.map(function(o){ return <option key={o} value={o}>{o}</option>; })}
                                                </select>
                                                <select value={filterPlacementStatus} onChange={(e) => setFilterPlacementStatus(e.target.value)}
                                                    className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500">
                                                    <option value="">All statuses</option>
                                                    {detailedPlacementsMeta.statuses.map(function(s){ return <option key={s} value={s}>{s}</option>; })}
                                                </select>
                                                {(filterPlacementOwner || filterPlacementStatus) && (
                                                    <button type="button" onClick={() => { setFilterPlacementOwner(''); setFilterPlacementStatus(''); }}
                                                        className="text-sm text-indigo-600 hover:underline">Clear filters</button>
                                                )}
                                            </div>
                                        </div>
                                        
                                        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
                                            <div className="overflow-x-auto">
                                                <table className="w-full text-sm">
                                                    <thead>
                                                        <tr className="border-b-2 border-gray-300 bg-gray-50">
                                                            <th className="text-left py-3 px-3 font-semibold text-gray-700">ID</th>
                                                            <th className="text-left py-3 px-3 font-semibold text-gray-700">Date</th>
                                                            <th className="text-left py-3 px-3 font-semibold text-gray-700">Candidate</th>
                                                            <th className="text-left py-3 px-3 font-semibold text-gray-700">Job Title</th>
                                                            <th className="text-left py-3 px-3 font-semibold text-gray-700">Client</th>
                                                            <th className="text-left py-3 px-3 font-semibold text-gray-700">Status</th>
                                                            <th className="text-left py-3 px-3 font-semibold text-gray-700">Owner</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {filteredDetailedPlacements.length === 0 ? (
                                                            <tr>
                                                                <td colSpan="7" className="text-center py-12 text-gray-500">
                                                                    <div className="text-4xl mb-2">📭</div>
                                                                    {detailedPlacements.length === 0 ? 'No placements found for this period' : 'No rows match the filters'}
                                                                </td>
                                                            </tr>
                                                        ) : (
                                                            filteredDetailedPlacements.map((plc, idx) => {
                                                                const statusColor = {
                                                                    'Approved': 'bg-green-100 text-green-800',
                                                                    'Active': 'bg-blue-100 text-blue-800',
                                                                    'Denied': 'bg-red-100 text-red-800',
                                                                    'Pending': 'bg-yellow-100 text-yellow-800',
                                                                    'Terminated': 'bg-gray-100 text-gray-800'
                                                                }[plc.status] || 'bg-gray-100 text-gray-700';
                                                                
                                                                return (
                                                                    <tr key={plc.id || idx} className="border-b border-gray-100 hover:bg-green-50 transition-colors">
                                                                        <td className="py-2 px-3 text-gray-600 font-mono text-xs">{plc.id}</td>
                                                                        <td className="py-2 px-3 text-gray-700 whitespace-nowrap">{plc.dateFormatted || 'N/A'}</td>
                                                                        <td className="py-2 px-3 text-gray-800 font-medium">{plc.candidateName}</td>
                                                                        <td className="py-2 px-3 text-gray-700 max-w-xs truncate" title={plc.jobTitle}>{plc.jobTitle}</td>
                                                                        <td className="py-2 px-3 text-gray-600">{plc.clientName}</td>
                                                                        <td className="py-2 px-3">
                                                                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColor}`}>
                                                                                {plc.status}
                                                                            </span>
                                                                        </td>
                                                                        <td className="py-2 px-3 text-gray-700">{plc.ownerName}</td>
                                                                    </tr>
                                                                );
                                                            })
                                                        )}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                        
                                        {detailedPlacements.length > 0 && (
                                            <button
                                                onClick={() => {
                                                    var rows = [['ID', 'Date', 'Candidate', 'Job Title', 'Client', 'Status', 'Owner']];
                                                    filteredDetailedPlacements.forEach(function(p){
                                                        rows.push([String(p.id || ''), p.dateFormatted || '', p.candidateName || '', p.jobTitle || '', p.clientName || '', p.status || '', p.ownerName || '']);
                                                    });
                                                    var csv = rows.map(function(row){ return row.map(function(c){ return '"' + (c || '').replace(/"/g, '""') + '"'; }).join(','); }).join('\\n');
                                                    var blob = new Blob([csv], { type: 'text/csv' });
                                                    var url = window.URL.createObjectURL(blob);
                                                    var a = document.createElement('a');
                                                    a.href = url;
                                                    a.download = 'detailed_placements_' + dateRange.start + '_' + dateRange.end + '.csv';
                                                    a.click();
                                                    window.URL.revokeObjectURL(url);
                                                }}
                                                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                                            >
                                                📥 Export Detailed CSV
                                            </button>
                                        )}
                                    </>
                                )}
                                
                                {/* Explore API section - show in all views */}
                                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                                    <h3 className="text-lg font-semibold text-gray-800 mb-2">Explore API &amp; available fields</h3>
                                    <p className="text-sm text-gray-600 mb-3">Use meta endpoints to see all queryable fields:</p>
                                    <div className="flex flex-wrap gap-2">
                                        <a href="/api/meta/JobSubmission" target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 bg-indigo-100 text-indigo-800 rounded-lg text-sm hover:bg-indigo-200">JobSubmission meta</a>
                                        <a href="/api/meta/Placement" target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 bg-indigo-100 text-indigo-800 rounded-lg text-sm hover:bg-indigo-200">Placement meta</a>
                                        <a href={'/api/submissions/detailed?start=' + encodeURIComponent(dateRange.start) + '&end=' + encodeURIComponent(dateRange.end)} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 bg-green-200 text-green-800 rounded-lg text-sm hover:bg-green-300">Detailed Submissions (raw)</a>
                                        <a href={'/api/placements/detailed?start=' + encodeURIComponent(dateRange.start) + '&end=' + encodeURIComponent(dateRange.end)} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 bg-green-200 text-green-800 rounded-lg text-sm hover:bg-green-300">Detailed Placements (raw)</a>
                                        <a href={'/api/analytics/recruiters?start=' + encodeURIComponent(dateRange.start) + '&end=' + encodeURIComponent(dateRange.end)} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 bg-gray-200 text-gray-800 rounded-lg text-sm hover:bg-gray-300">Recruiters (raw)</a>
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

def access_token_expires_within(minutes=30):
    """Check if access_token expires within X minutes. Returns True if missing or expiring soon."""
    tokens = load_tokens()
    if not tokens:
        return True
    exp = tokens.get('access_token_expires_at')
    if exp is None:
        return True
    now = datetime.now().timestamp()
    return (exp - now) <= (minutes * 60)

def get_bh_rest_token_expiration(rest_url, bh_rest_token):
    """Call /ping to get BhRestToken expiration. Returns epoch seconds or None."""
    try:
        if not rest_url or not bh_rest_token:
            return None
        u = rest_url if rest_url.endswith('/') else rest_url + '/'
        r = requests.get(u + 'ping', params={'BhRestToken': bh_rest_token}, timeout=10)
        if r.ok:
            d = r.json()
            ms = d.get('sessionExpires')
            if ms is not None:
                return int(ms / 1000)
    except Exception as e:
        print(f"Error getting BhRestToken expiration: {e}")
    return None

def refresh_oauth_access_token():
    """Use refresh_token to get new access_token. Returns True on success, False on failure."""
    tokens = load_tokens()
    if not tokens or not tokens.get('refresh_token'):
        print("⚠️ No refresh_token available for OAuth refresh")
        return False
    if not CLIENT_ID or not CLIENT_SECRET:
        print("⚠️ CLIENT_ID or CLIENT_SECRET not set")
        return False
    try:
        r = requests.post(
            'https://auth.bullhornstaffing.com/oauth/token',
            data={
                'grant_type': 'refresh_token',
                'refresh_token': tokens['refresh_token'],
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=15,
        )
        data = r.json() if r.text else {}
        if not r.ok:
            err = data.get('error', '') or str(data)
            desc = data.get('error_description', '')
            if err == 'invalid_grant' or 'refresh' in str(desc).lower() or 'expired' in str(desc).lower():
                print("REFRESH TOKEN EXPIRED - MANUAL RE-AUTH REQUIRED")
            else:
                print(f"OAuth refresh failed: {r.status_code} {err} {desc}")
            return False
        at = data.get('access_token')
        rt = data.get('refresh_token') or tokens.get('refresh_token')
        if not at:
            print("OAuth refresh: no access_token in response")
            return False
        exp_in = int(data.get('expires_in', 36000))
        tokens['access_token'] = at
        tokens['refresh_token'] = rt
        tokens['access_token_expires_at'] = datetime.now().timestamp() + exp_in
        if data.get('restUrl'):
            tokens['rest_url'] = data['restUrl']
        tokens['last_refresh'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_tokens(tokens)
        print(f"✅ OAuth access_token refreshed; expires in {exp_in}s")
        return True
    except Exception as e:
        print(f"❌ OAuth refresh error: {e}")
        return False

def maintain_session():
    """Two-tier token refresh: OAuth access_token + BhRestToken"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] maintain_session: running...")
    tokens = load_tokens()
    if not tokens or not tokens.get('access_token'):
        print("⚠️ No tokens to maintain")
        return
    # Step 1: Refresh OAuth access_token if it expires within 30 minutes
    if access_token_expires_within(minutes=30):
        ok = refresh_oauth_access_token()
        if not ok:
            print("⚠️ OAuth refresh failed; skipping BhRestToken refresh")
            return
        tokens = load_tokens()
    # Step 2: Re-exchange access_token for BhRestToken and get expiration from ping
    at = tokens.get('access_token')
    rest_url = tokens.get('rest_url')
    bh, new_rest = exchange_for_bh_rest_token(at, rest_url)
    if not bh:
        print("⚠️ Failed to obtain BhRestToken")
        return
    tokens['bh_rest_token'] = bh
    if new_rest:
        tokens['rest_url'] = new_rest
        rest_url = new_rest
    # Get BhRestToken expiration from ping
    exp = get_bh_rest_token_expiration(rest_url or tokens.get('rest_url'), bh)
    if exp is not None:
        tokens['bh_rest_token_expires_at'] = exp
    tokens['last_refresh'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_tokens(tokens)
    print(f"✅ maintain_session: BhRestToken refreshed at {tokens['last_refresh']}")

# Schedule two-tier token maintenance (OAuth + BhRestToken)
scheduler.add_job(
    func=maintain_session,
    trigger="interval",
    minutes=REFRESH_INTERVAL_MINUTES,
    id='token_maintenance',
    name='Maintain OAuth and BhRestToken',
    replace_existing=True,
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
        
        # Step 3: Compute expiration timestamps
        expires_in = int(data.get('expires_in') or 36000)
        access_token_expires_at = datetime.now().timestamp() + expires_in
        bh_rest_token_expires_at = get_bh_rest_token_expiration(rest_url, bh_rest_token) if bh_rest_token else None
        
        # Step 4: Save everything
        tokens = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'access_token_expires_at': access_token_expires_at,
            'rest_url': rest_url,
            'bh_rest_token': bh_rest_token,
            'bh_rest_token_expires_at': bh_rest_token_expires_at,
            'expires_in': data.get('expires_in'),
            'last_refresh': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
            tokens['bh_rest_token_expires_at'] = int(data['sessionExpires'] / 1000)
            save_tokens(tokens)
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

# ==================== HELPER FUNCTIONS FOR ANALYTICS ====================

def parse_date_range_from_request():
    """Get (start_ms, end_ms) from request: start/end (YYYY-MM-DD), or year+month, or year only."""
    import calendar
    args = request.args
    start_arg, end_arg = args.get('start'), args.get('end')
    if start_arg and end_arg:
        start_dt = datetime.strptime(start_arg, '%Y-%m-%d')
        end_dt = datetime.strptime(end_arg, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        return int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)
    year = int(args.get('year', datetime.now().year))
    month = args.get('month', type=int)
    if month is None:
        start_dt = datetime(year, 1, 1)
        end_dt = datetime(year, 12, 31, 23, 59, 59)
    else:
        start_dt = datetime(year, month, 1)
        last = calendar.monthrange(year, month)[1]
        end_dt = datetime(year, month, last, 23, 59, 59)
    return int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)

def fetch_job_submissions(start_ms, end_ms, include_recruiter=True):
    """
    Safely fetch JobSubmission records from Bullhorn.
    
    Args:
        start_ms: Start timestamp in milliseconds
        end_ms: End timestamp in milliseconds
        include_recruiter: If True, include sendingUser field
    
    Returns:
        List of submission records or None on error
    """
    tokens = load_tokens()
    if not tokens or not tokens.get('bh_rest_token'):
        return None
    
    try:
        rest_url = tokens['rest_url']
        if not rest_url.endswith('/'):
            rest_url += '/'
        
        url = f"{rest_url}query/JobSubmission"
        
        if include_recruiter:
            fields = 'id,dateAdded,status,sendingUser(id,firstName,lastName)'
        else:
            fields = 'id,dateAdded,status'
        
        params = {
            'BhRestToken': tokens['bh_rest_token'],
            'where': f"dateAdded>={start_ms} AND dateAdded<={end_ms}",
            'fields': fields,
            'orderBy': '-dateAdded',
            'count': 500
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('data', [])
    except Exception as e:
        print(f"Error fetching JobSubmissions: {e}")
        return None

def fetch_placements(start_ms, end_ms, include_recruiter=True):
    """
    Safely fetch Placement records from Bullhorn.
    
    Args:
        start_ms: Start timestamp in milliseconds
        end_ms: End timestamp in milliseconds
        include_recruiter: If True, include sendingUser field
    
    Returns:
        List of placement records or None on error
    """
    tokens = load_tokens()
    if not tokens or not tokens.get('bh_rest_token'):
        return None
    
    try:
        rest_url = tokens['rest_url']
        if not rest_url.endswith('/'):
            rest_url += '/'
        
        url = f"{rest_url}query/Placement"
        
        if include_recruiter:
            fields = 'id,dateAdded,sendingUser(id,firstName,lastName)'
        else:
            fields = 'id,dateAdded'
        
        params = {
            'BhRestToken': tokens['bh_rest_token'],
            'where': f"dateAdded>={start_ms} AND dateAdded<={end_ms}",
            'fields': fields,
            'orderBy': '-dateAdded',
            'count': 500
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('data', [])
    except Exception as e:
        print(f"Error fetching Placements: {e}")
        return None

def get_recruiter_name(item):
    """Extract recruiter name from sendingUser field"""
    if item.get('sendingUser') and item['sendingUser'].get('firstName') and item['sendingUser'].get('lastName'):
        return f"{item['sendingUser']['firstName']} {item['sendingUser']['lastName']}"
    return "Unknown"

def get_recruiter_id(item):
    """Extract recruiter ID from sendingUser field"""
    if item.get('sendingUser') and item['sendingUser'].get('id'):
        return item['sendingUser']['id']
    return None

def get_week_range(date_ms):
    """Get week start and end dates for a given timestamp"""
    date = datetime.fromtimestamp(date_ms / 1000)
    # Get Monday of the week
    days_since_monday = date.weekday()
    week_start = date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end

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
    """Manually trigger two-tier token maintenance"""
    maintain_session()
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
    """Fetch submissions from Bullhorn. Use start/end (YYYY-MM-DD), or year+month, or year."""
    tokens = load_tokens()
    
    if not tokens or not tokens.get('bh_rest_token'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    detailed = request.args.get('detailed', 'false').lower() == 'true'
    start_ms, end_ms = parse_date_range_from_request()
    
    # Query Bullhorn
    try:
        rest_url = tokens['rest_url']
        if not rest_url.endswith('/'):
            rest_url += '/'
        
        url = f"{rest_url}query/JobSubmission"
        
        # Full fields for detailed view - includes candidate, job, owner info
        if detailed:
            fields = 'id,dateAdded,status,candidate(id,firstName,lastName),jobOrder(id,title,clientCorporation(id,name)),sendingUser(id,firstName,lastName)'
        else:
            fields = 'id,dateAdded,status,sendingUser(id,firstName,lastName)'
        
        params = {
            'BhRestToken': tokens['bh_rest_token'],
            'where': f"dateAdded>={start_ms} AND dateAdded<={end_ms}",
            'fields': fields,
            'orderBy': '-dateAdded',
            'count': 500
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        submissions = data.get('data', [])
        
        # Format detailed data for easier frontend consumption
        if detailed:
            formatted = []
            for sub in submissions:
                candidate = sub.get('candidate', {}) or {}
                job = sub.get('jobOrder', {}) or {}
                owner = sub.get('sendingUser', {}) or {}
                client = job.get('clientCorporation', {}) or {}
                
                formatted.append({
                    'id': sub.get('id'),
                    'dateAdded': sub.get('dateAdded'),
                    'dateFormatted': datetime.fromtimestamp(sub.get('dateAdded', 0)/1000).strftime('%Y-%m-%d %H:%M') if sub.get('dateAdded') else None,
                    'status': sub.get('status', 'Unknown'),
                    'candidateId': candidate.get('id'),
                    'candidateName': f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}".strip() or 'Unknown',
                    'jobId': job.get('id'),
                    'jobTitle': job.get('title', 'Unknown'),
                    'clientName': client.get('name', 'Unknown'),
                    'ownerId': owner.get('id'),
                    'ownerName': f"{owner.get('firstName', '')} {owner.get('lastName', '')}".strip() or 'Unknown'
                })
            submissions = formatted
        
        return jsonify({
            'success': True,
            'count': len(submissions),
            'detailed': detailed,
            'data': submissions
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/placements')
def api_placements():
    """Fetch placements from Bullhorn. Use start/end (YYYY-MM-DD), or year+month, or year."""
    tokens = load_tokens()
    
    if not tokens or not tokens.get('bh_rest_token'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    start_ms, end_ms = parse_date_range_from_request()
    
    # Query Bullhorn
    try:
        rest_url = tokens['rest_url']
        if not rest_url.endswith('/'):
            rest_url += '/'
        
        url = f"{rest_url}query/Placement"
        
        # Minimal fields only - no nested associations to avoid 400 Bad Request
        fields = 'id,dateAdded'
        
        params = {
            'BhRestToken': tokens['bh_rest_token'],
            'where': f"dateAdded>={start_ms} AND dateAdded<={end_ms}",
            'fields': fields,
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
            'data': placements
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/placements/detailed')
def api_placements_detailed():
    """Fetch detailed placements. Use start/end (YYYY-MM-DD), or year+month, or year. Same structure as detailed submissions."""
    tokens = load_tokens()
    
    if not tokens or not tokens.get('bh_rest_token'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    start_ms, end_ms = parse_date_range_from_request()
    
    try:
        rest_url = tokens['rest_url']
        if not rest_url.endswith('/'):
            rest_url += '/'
        
        url = f"{rest_url}query/Placement"
        
        # Full fields: candidate, job, client, owner (same shape as submissions/detailed)
        fields = 'id,dateAdded,status,candidate(id,firstName,lastName,email),jobOrder(id,title,clientCorporation(id,name)),sendingUser(id,firstName,lastName)'
        
        params = {
            'BhRestToken': tokens['bh_rest_token'],
            'where': f"dateAdded>={start_ms} AND dateAdded<={end_ms}",
            'fields': fields,
            'orderBy': '-dateAdded',
            'count': 500
        }
        
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        placements = data.get('data', [])
        
        formatted = []
        for plc in placements:
            candidate = plc.get('candidate', {}) or {}
            job = plc.get('jobOrder', {}) or {}
            owner = plc.get('sendingUser', {}) or {}
            client = job.get('clientCorporation', {}) or {}
            
            formatted.append({
                'id': plc.get('id'),
                'dateAdded': plc.get('dateAdded'),
                'dateFormatted': datetime.fromtimestamp(plc.get('dateAdded', 0)/1000).strftime('%Y-%m-%d %H:%M') if plc.get('dateAdded') else None,
                'status': plc.get('status', 'Unknown'),
                'candidateId': candidate.get('id'),
                'candidateName': f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}".strip() or 'Unknown',
                'candidateEmail': candidate.get('email', ''),
                'jobId': job.get('id'),
                'jobTitle': job.get('title', 'Unknown'),
                'clientName': client.get('name', 'Unknown'),
                'ownerId': owner.get('id'),
                'ownerName': f"{owner.get('firstName', '')} {owner.get('lastName', '')}".strip() or 'Unknown'
            })
        
        return jsonify({
            'success': True,
            'count': len(formatted),
            'data': formatted
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/meta/<entity>')
def api_meta(entity):
    """Fetch entity metadata from Bullhorn (all available fields). Use entity=JobSubmission or Placement."""
    tokens = load_tokens()
    
    if not tokens or not tokens.get('bh_rest_token'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    allowed = {'JobSubmission', 'Placement', 'JobOrder', 'Candidate', 'CorporateUser'}
    if entity not in allowed:
        return jsonify({'error': f'Entity not allowed. Use one of: {", ".join(sorted(allowed))}'}), 400
    
    try:
        rest_url = tokens['rest_url']
        if not rest_url.endswith('/'):
            rest_url += '/'
        url = f"{rest_url}meta/{entity}"
        params = {
            'BhRestToken': tokens['bh_rest_token'],
            'fields': '*',
            'meta': 'full'
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return jsonify(data)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/weekly')
def api_analytics_weekly():
    """Get weekly analytics aggregated by week"""
    tokens = load_tokens()
    if not tokens or not tokens.get('bh_rest_token'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    
    # Calculate month date range
    import calendar
    start_date = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, last_day, 23, 59, 59)
    start_ms = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)
    
    try:
        submissions = fetch_job_submissions(start_ms, end_ms, include_recruiter=True)
        placements = fetch_placements(start_ms, end_ms, include_recruiter=True)
        
        if submissions is None or placements is None:
            return jsonify({'error': 'Failed to fetch data from Bullhorn'}), 500
        
        # Group by week
        week_map = {}
        
        # Process submissions
        for sub in submissions:
            if not sub.get('dateAdded'):
                continue
            
            week_start, week_end = get_week_range(sub['dateAdded'])
            week_key = week_start.strftime('%Y-%m-%d')
            
            if week_key not in week_map:
                week_map[week_key] = {
                    'weekStart': week_start.strftime('%Y-%m-%d'),
                    'weekEnd': week_end.strftime('%Y-%m-%d'),
                    'submissions': 0,
                    'presented': 0,
                    'placed': 0,
                    'byRecruiter': {}
                }
            
            week_data = week_map[week_key]
            week_data['submissions'] += 1
            
            # Check if presented (status is "Presented" or contains "presented")
            status = sub.get('status', '') or ''
            status_lower = status.lower()
            if status_lower == 'presented' or 'presented' in status_lower:
                week_data['presented'] += 1
            
            # Group by recruiter
            recruiter_id = get_recruiter_id(sub)
            recruiter_name = get_recruiter_name(sub)
            recruiter_key = f"{recruiter_id}_{recruiter_name}"
            
            if recruiter_key not in week_data['byRecruiter']:
                week_data['byRecruiter'][recruiter_key] = {
                    'recruiterId': recruiter_id,
                    'name': recruiter_name,
                    'submissions': 0,
                    'presented': 0,
                    'placed': 0,
                    'statusCounts': {}
                }
            
            rec_data = week_data['byRecruiter'][recruiter_key]
            rec_data['submissions'] += 1
            
            status_val = sub.get('status', 'Unknown')
            if status_lower == 'presented' or 'presented' in status_lower:
                rec_data['presented'] += 1
            rec_data['statusCounts'][status_val] = rec_data['statusCounts'].get(status_val, 0) + 1
        
        # Process placements (count as "placed")
        for place in placements:
            if not place.get('dateAdded'):
                continue
            
            week_start, week_end = get_week_range(place['dateAdded'])
            week_key = week_start.strftime('%Y-%m-%d')
            
            if week_key not in week_map:
                week_map[week_key] = {
                    'weekStart': week_start.strftime('%Y-%m-%d'),
                    'weekEnd': week_end.strftime('%Y-%m-%d'),
                    'submissions': 0,
                    'presented': 0,
                    'placed': 0,
                    'byRecruiter': {}
                }
            
            week_data = week_map[week_key]
            week_data['placed'] += 1
            
            # Group placement by recruiter
            recruiter_id = get_recruiter_id(place)
            recruiter_name = get_recruiter_name(place)
            recruiter_key = f"{recruiter_id}_{recruiter_name}"
            
            if recruiter_key not in week_data['byRecruiter']:
                week_data['byRecruiter'][recruiter_key] = {
                    'recruiterId': recruiter_id,
                    'name': recruiter_name,
                    'submissions': 0,
                    'presented': 0,
                    'placed': 0,
                    'statusCounts': {}
                }
            
            week_data['byRecruiter'][recruiter_key]['placed'] += 1
        
        # Convert to list format
        result = []
        for week_key in sorted(week_map.keys()):
            week_data = week_map[week_key]
            week_data['byRecruiter'] = list(week_data['byRecruiter'].values())
            result.append(week_data)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/monthly')
def api_analytics_monthly():
    """Get monthly analytics aggregated for entire month"""
    tokens = load_tokens()
    if not tokens or not tokens.get('bh_rest_token'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    
    # Calculate month date range
    import calendar
    start_date = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, last_day, 23, 59, 59)
    start_ms = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)
    
    try:
        submissions = fetch_job_submissions(start_ms, end_ms, include_recruiter=True)
        placements = fetch_placements(start_ms, end_ms, include_recruiter=True)
        
        if submissions is None or placements is None:
            return jsonify({'error': 'Failed to fetch data from Bullhorn'}), 500
        
        # Aggregate for entire month
        result = {
            'monthStart': start_date.strftime('%Y-%m-%d'),
            'monthEnd': end_date.strftime('%Y-%m-%d'),
            'submissions': 0,
            'presented': 0,
            'placed': 0,
            'byRecruiter': {}
        }
        
        # Process submissions
        for sub in submissions:
            result['submissions'] += 1
            
            status = sub.get('status', '') or ''
            status_lower = status.lower()
            if status_lower == 'presented' or 'presented' in status_lower:
                result['presented'] += 1
            
            # Group by recruiter
            recruiter_id = get_recruiter_id(sub)
            recruiter_name = get_recruiter_name(sub)
            recruiter_key = f"{recruiter_id}_{recruiter_name}"
            
            if recruiter_key not in result['byRecruiter']:
                result['byRecruiter'][recruiter_key] = {
                    'recruiterId': recruiter_id,
                    'name': recruiter_name,
                    'submissions': 0,
                    'presented': 0,
                    'placed': 0,
                    'statusCounts': {}
                }
            
            rec_data = result['byRecruiter'][recruiter_key]
            rec_data['submissions'] += 1
            
            status_val = sub.get('status', 'Unknown')
            if status_lower == 'presented' or 'presented' in status_lower:
                rec_data['presented'] += 1
            rec_data['statusCounts'][status_val] = rec_data['statusCounts'].get(status_val, 0) + 1
        
        # Process placements (count as "placed")
        for place in placements:
            result['placed'] += 1
            
            # Group placement by recruiter
            recruiter_id = get_recruiter_id(place)
            recruiter_name = get_recruiter_name(place)
            recruiter_key = f"{recruiter_id}_{recruiter_name}"
            
            if recruiter_key not in result['byRecruiter']:
                result['byRecruiter'][recruiter_key] = {
                    'recruiterId': recruiter_id,
                    'name': recruiter_name,
                    'submissions': 0,
                    'presented': 0,
                    'placed': 0,
                    'statusCounts': {}
                }
            
            result['byRecruiter'][recruiter_key]['placed'] += 1
        
        result['byRecruiter'] = list(result['byRecruiter'].values())
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/submissions/detailed')
def api_submissions_detailed():
    """Fetch detailed submissions. Use start/end (YYYY-MM-DD), or year+month, or year."""
    tokens = load_tokens()
    
    if not tokens or not tokens.get('bh_rest_token'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    start_ms, end_ms = parse_date_range_from_request()
    
    # Query Bullhorn
    try:
        rest_url = tokens['rest_url']
        if not rest_url.endswith('/'):
            rest_url += '/'
        
        url = f"{rest_url}query/JobSubmission"
        
        # Full fields including candidate, job, client, and owner
        fields = 'id,dateAdded,status,candidate(id,firstName,lastName,email),jobOrder(id,title,clientCorporation(id,name)),sendingUser(id,firstName,lastName)'
        
        params = {
            'BhRestToken': tokens['bh_rest_token'],
            'where': f"dateAdded>={start_ms} AND dateAdded<={end_ms}",
            'fields': fields,
            'orderBy': '-dateAdded',
            'count': 500
        }
        
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        submissions = data.get('data', [])
        
        # Format detailed data
        formatted = []
        for sub in submissions:
            candidate = sub.get('candidate', {}) or {}
            job = sub.get('jobOrder', {}) or {}
            owner = sub.get('sendingUser', {}) or {}
            client = job.get('clientCorporation', {}) or {}
            
            formatted.append({
                'id': sub.get('id'),
                'dateAdded': sub.get('dateAdded'),
                'dateFormatted': datetime.fromtimestamp(sub.get('dateAdded', 0)/1000).strftime('%Y-%m-%d %H:%M') if sub.get('dateAdded') else None,
                'status': sub.get('status', 'Unknown'),
                'candidateId': candidate.get('id'),
                'candidateName': f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}".strip() or 'Unknown',
                'candidateEmail': candidate.get('email', ''),
                'jobId': job.get('id'),
                'jobTitle': job.get('title', 'Unknown'),
                'clientName': client.get('name', 'Unknown'),
                'ownerId': owner.get('id'),
                'ownerName': f"{owner.get('firstName', '')} {owner.get('lastName', '')}".strip() or 'Unknown'
            })
        
        return jsonify({
            'success': True,
            'count': len(formatted),
            'data': formatted
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/analytics/recruiters')
def api_analytics_recruiters():
    """Get recruiter-level analytics. Use start/end (YYYY-MM-DD), or year+month, or year."""
    tokens = load_tokens()
    if not tokens or not tokens.get('bh_rest_token'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    start_ms, end_ms = parse_date_range_from_request()
    
    try:
        submissions = fetch_job_submissions(start_ms, end_ms, include_recruiter=True)
        placements = fetch_placements(start_ms, end_ms, include_recruiter=True)
        
        if submissions is None or placements is None:
            return jsonify({'error': 'Failed to fetch data from Bullhorn'}), 500
        
        recruiter_map = {}
        
        # Process submissions
        for sub in submissions:
            recruiter_id = get_recruiter_id(sub)
            recruiter_name = get_recruiter_name(sub)
            recruiter_key = f"{recruiter_id}_{recruiter_name}"
            
            if recruiter_key not in recruiter_map:
                recruiter_map[recruiter_key] = {
                    'recruiterId': recruiter_id,
                    'name': recruiter_name,
                    'totalSubmissions': 0,
                    'totalPlacements': 0,
                    'statusBreakdown': {}
                }
            
            rec_data = recruiter_map[recruiter_key]
            rec_data['totalSubmissions'] += 1
            
            status = sub.get('status', 'Unknown')
            rec_data['statusBreakdown'][status] = rec_data['statusBreakdown'].get(status, 0) + 1
        
        # Process placements
        for place in placements:
            recruiter_id = get_recruiter_id(place)
            recruiter_name = get_recruiter_name(place)
            recruiter_key = f"{recruiter_id}_{recruiter_name}"
            
            if recruiter_key not in recruiter_map:
                recruiter_map[recruiter_key] = {
                    'recruiterId': recruiter_id,
                    'name': recruiter_name,
                    'totalSubmissions': 0,
                    'totalPlacements': 0,
                    'statusBreakdown': {}
                }
            
            recruiter_map[recruiter_key]['totalPlacements'] += 1
        
        result = list(recruiter_map.values())
        result.sort(key=lambda x: x['totalSubmissions'], reverse=True)
        
        return jsonify({'recruiters': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"Starting Bullhorn OAuth server on port {port}")
    print(f"Auto-refresh enabled: every {REFRESH_INTERVAL_MINUTES} minutes")
    app.run(host='0.0.0.0', port=port, debug=False)
