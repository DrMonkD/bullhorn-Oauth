from flask import Flask, request, redirect, render_template_string, jsonify
import requests
import json
import os
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from supabase import create_client, Client

app = Flask(__name__)

# Configuration
CLIENT_ID = os.environ.get('BULLHORN_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('BULLHORN_CLIENT_SECRET', '')
REDIRECT_URI = 'https://bullhorn-oauth.onrender.com/oauth/callback'
TOKEN_FILE = 'token_store.json'

# Logo: set LOGO_URL to override; default uses Concord Icon from bullhorn-Oauth repo
LOGO_URL = os.environ.get('LOGO_URL', 'https://raw.githubusercontent.com/DrMonkD/bullhorn-Oauth/main/Concord%20Icon.png')

# Supabase configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', os.environ.get('SUPABASE_KEY', ''))  # Support both names
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        # Initialize Supabase client without proxy to avoid version compatibility issues
        # The client will use the REST API URL directly (not the PostgreSQL pooler)
        # For proxy/network issues, configure HTTP_PROXY/HTTPS_PROXY env vars separately if needed
        supabase = create_client(
            SUPABASE_URL,
            SUPABASE_KEY,
            options={
                'auto_refresh_token': False,
                'persist_session': False
            }
        )
        print("✅ Supabase client initialized")
    except TypeError as e:
        # Handle version compatibility - try without options if they're not supported
        if 'proxy' in str(e).lower() or 'unexpected keyword' in str(e).lower():
            try:
                # Fallback: simple initialization without options
                supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
                print("✅ Supabase client initialized (fallback method)")
            except Exception as e2:
                print(f"⚠️ Failed to initialize Supabase client: {e2}")
        else:
            print(f"⚠️ Failed to initialize Supabase client: {e}")
    except Exception as e:
        print(f"⚠️ Failed to initialize Supabase client: {e}")
else:
    missing = []
    if not SUPABASE_URL:
        missing.append('SUPABASE_URL')
    if not SUPABASE_KEY:
        missing.append('SUPABASE_SERVICE_KEY (or SUPABASE_KEY)')
    print(f"⚠️ Supabase not configured. Missing environment variables: {', '.join(missing)}")

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
                <a href="/analytics?view=jobs" class="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors inline-flex items-center gap-2">
                    Jobs Dashboard
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
                    <div class="bg-white p-2 rounded">GET /api/jobs/detailed?start=YYYY-MM-DD&end=YYYY-MM-DD - Fetch JobOrder records (title, status, client, owner)</div>
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
    <title>Bullhorn Analytics Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>body{font-family:'Inter',system-ui,-apple-system,sans-serif}</style>
    <script src="https://cdn.tailwindcss.com"></script>
    <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/react-is@18/umd/react-is.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
</head>
<body class="bg-slate-100 min-h-screen p-6 font-sans antialiased">
    <div id="root">
        <div class="p-6 text-center">
            <div class="inline-block animate-spin rounded-full h-12 w-12 border-2 border-slate-300 border-t-slate-600"></div>
            <p class="mt-4 text-slate-600">Loading dashboard...</p>
        </div>
    </div>
    
    <script type="text/babel">
        const { useState, useEffect, useMemo, useRef } = React;
        
        // Bar chart via Chart.js (works from CDN); supports bar/line toggle
        function BarChartCanvas({ data, labelsKey, datasets, title, height }) {
            const canvasRef = useRef(null);
            const chartRef = useRef(null);
            const [chartType, setChartType] = useState('bar');
            const ChartLib = typeof window !== 'undefined' ? window.Chart : (typeof Chart !== 'undefined' ? Chart : null);
            
            useEffect(function() {
                if (!ChartLib || !data || data.length === 0) return;
                var ctx = canvasRef.current && canvasRef.current.getContext('2d');
                if (!ctx) return;
                if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; }
                var isLine = chartType === 'line';
                chartRef.current = new ChartLib(ctx, {
                    type: isLine ? 'line' : 'bar',
                    data: {
                        labels: data.map(function(d) { return d[labelsKey]; }),
                        datasets: datasets.map(function(ds) {
                            var base = { label: ds.label, data: data.map(function(d) { return d[ds.dataKey] || 0; }) };
                            if (isLine) return Object.assign(base, { borderColor: ds.color, backgroundColor: ds.color, fill: false });
                            return Object.assign(base, { backgroundColor: ds.color });
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
            }, [data, labelsKey, chartType]);
            
            if (!ChartLib) return <div className="p-4 bg-amber-50 border-2 border-amber-200 rounded-lg"><p className="text-amber-800 text-sm">Charts unavailable (Chart.js failed to load).</p></div>;
            if (!data || data.length === 0) return null;
            return (
                <div className="bg-white border-2 border-slate-200 rounded-lg p-4">
                    <div className="flex justify-between items-center gap-4 mb-4 flex-wrap">
                        <div>{title && <h3 className="text-base font-medium text-slate-800">{title}</h3>}</div>
                        <div className="flex gap-2">
                            <button
                                onClick={() => setChartType('bar')}
                                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${chartType === 'bar' ? 'bg-slate-800 text-white' : 'bg-white border-2 border-slate-200 text-slate-600 hover:bg-slate-50'}`}
                            >
                                Bar
                            </button>
                            <button
                                onClick={() => setChartType('line')}
                                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${chartType === 'line' ? 'bg-slate-800 text-white' : 'bg-white border-2 border-slate-200 text-slate-600 hover:bg-slate-50'}`}
                            >
                                Line
                            </button>
                        </div>
                    </div>
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
            
            // View mode: 'basic', 'recruiter', 'detailed', 'detailed_placements', 'jobs'
            const [viewMode, setViewMode] = useState(function(){
                try { if (typeof window !== 'undefined' && window.location.search.indexOf('view=jobs') >= 0) return 'jobs'; } catch(e) {}
                return 'basic';
            });
            
            // Detailed submissions data
            const [detailedSubmissions, setDetailedSubmissions] = useState([]);
            
            // Quick filters for Detailed view (client-side)
            const [filterOwner, setFilterOwner] = useState('');
            const [filterStatus, setFilterStatus] = useState('');
            
            // Detailed placements data and filters
            const [detailedPlacements, setDetailedPlacements] = useState([]);
            const [filterPlacementOwner, setFilterPlacementOwner] = useState('');
            const [filterPlacementStatus, setFilterPlacementStatus] = useState('');
            
            // Detailed jobs data and filters
            const [detailedJobs, setDetailedJobs] = useState([]);
            const [filterJobOwner, setFilterJobOwner] = useState('');
            const [filterJobStatus, setFilterJobStatus] = useState('');
            const [filterJobOpenClosed, setFilterJobOpenClosed] = useState('');
            
            // Basic view: filter by submission owner (submitter)
            const [filterBasicOwner, setFilterBasicOwner] = useState('');
            
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
            
            // Fetch basic data (existing). When owner selected, submissions use start − EXTENDED_SUBMISSIONS_MONTHS for owner–placement linkage.
            const fetchBasicData = async () => {
                setLoading(true);
                setError(null);
                try {
                    var r = dateRange;
                    var subsStart = r.start, subsEnd = r.end;
                    if (filterBasicOwner) {
                        var d = new Date(r.start + 'T12:00:00');
                        d.setMonth(d.getMonth() - EXTENDED_SUBMISSIONS_MONTHS);
                        subsStart = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
                    }
                    console.log('Fetching data for', r.start, 'to', r.end);
                    var subsUrl = '/api/submissions?start=' + encodeURIComponent(subsStart) + '&end=' + encodeURIComponent(subsEnd);
                    if (filterBasicOwner) subsUrl += '&count=2000';
                    const [subsRes, placeRes] = await Promise.all([
                        fetch(subsUrl),
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
                    } else if (viewMode === 'jobs') {
                        const res = await fetch('/api/jobs/detailed?' + q);
                        if (res.ok) {
                            const data = await res.json();
                            setDetailedJobs(data.data || []);
                        } else {
                            const errorText = await res.text();
                            throw new Error('Failed to fetch detailed jobs: ' + errorText.substring(0, 100));
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
            }, [dateRange.start, dateRange.end, viewMode, filterBasicOwner]);
            
            // Stats (id, dateAdded; placements have status). Booked = Requested Credentialing, Credentialed, On assignment, Assignment completed.
            const EXTENDED_SUBMISSIONS_MONTHS = 12;
            const BOOKED_STATUSES = ['requested credentialing', 'credentialed', 'on assignment', 'assignment completed'];
            const isBooked = (p) => {
                const s = String(p.status || '').toLowerCase().replace(/\\s+/g, ' ').trim();
                return BOOKED_STATUSES.indexOf(s) >= 0;
            };
            const CANCELLED_STATUSES = ['provider cancelled', 'concord cancelled', 'client cancelled', 'credentialing cancelled'];
            const isCancelled = (p) => {
                const s = String(p.status || '').toLowerCase().replace(/\\s+/g, ' ').trim();
                return CANCELLED_STATUSES.indexOf(s) >= 0;
            };
            // Submissions whose dateAdded falls in the user-selected range (needed when submissions response is extended for owner linkage).
            const submissionsInRange = useMemo(() => {
                var startMs = new Date(dateRange.start + 'T00:00:00').getTime();
                var endMs = new Date(dateRange.end + 'T23:59:59.999').getTime();
                return submissions.filter(function(sub){ var t = sub.dateAdded; return t != null && t >= startMs && t <= endMs; });
            }, [submissions, dateRange.start, dateRange.end]);
            // Basic: unique owners from submissions (submitter = sendingUser)
            const basicOwnerList = useMemo(() => {
                const m = new Map();
                submissionsInRange.forEach(function(sub){
                    var u = sub.sendingUser;
                    if (!u || u.id == null) return;
                    var name = (String(u.firstName || '') + ' ' + String(u.lastName || '')).trim() || 'Unknown';
                    m.set(String(u.id), name);
                });
                return Array.from(m.entries()).map(function(kv){ return { id: kv[0], name: kv[1] }; }).sort(function(a,b){ return a.name.localeCompare(b.name); });
            }, [submissionsInRange]);
            // (candidateId,jobId) pairs for selected owner: one candidate to multiple jobs = separate entries, each counts as one book.
            // Only placements whose (candidate, job) was submitted by this owner are included when filtered.
            const ownerCandidateJobSet = useMemo(() => {
                if (!filterBasicOwner) return null;
                var s = new Set();
                submissions.forEach(function(sub){
                    if (!sub.sendingUser || String(sub.sendingUser.id) !== String(filterBasicOwner)) return;
                    var cid = sub.candidate && sub.candidate.id;
                    var jid = sub.jobOrder && sub.jobOrder.id;
                    if (cid != null && jid != null) s.add(String(cid) + ',' + String(jid));
                });
                return s;
            }, [submissions, filterBasicOwner]);
            const filteredSubmissions = useMemo(() => {
                if (!filterBasicOwner) return submissionsInRange;
                return submissionsInRange.filter(function(sub){ return sub.sendingUser && String(sub.sendingUser.id) === String(filterBasicOwner); });
            }, [submissionsInRange, filterBasicOwner]);
            // Placements: include only (candidate, job) pairs that this owner submitted. Candidate+job = one placement/book.
            const filteredPlacements = useMemo(() => {
                if (!filterBasicOwner || !ownerCandidateJobSet) return placements;
                return placements.filter(function(pl){
                    var cid = pl.candidate && pl.candidate.id;
                    var jid = pl.jobOrder && pl.jobOrder.id;
                    if (cid == null || jid == null) return false;
                    return ownerCandidateJobSet.has(String(cid) + ',' + String(jid));
                });
            }, [placements, filterBasicOwner, ownerCandidateJobSet]);
            const stats = useMemo(() => {
                const totalSubmissions = filteredSubmissions.length;
                const totalPlacements = filteredPlacements.length;
                const totalBooked = filteredPlacements.filter(isBooked).length;
                const totalCancelled = filteredPlacements.filter(isCancelled).length;
                const totalEverBooked = totalBooked + totalCancelled;
                const conversionRate = totalSubmissions > 0 ? (totalBooked / totalSubmissions * 100).toFixed(1) : 0;
                const cancelledShare = totalEverBooked > 0 ? (totalCancelled / totalEverBooked * 100) : null;
                return {
                    totalSubmissions,
                    totalPlacements,
                    totalBooked,
                    totalCancelled,
                    totalEverBooked,
                    conversionRate: parseFloat(conversionRate),
                    cancelledShare
                };
            }, [filteredSubmissions, filteredPlacements]);
            
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
                filteredSubmissions.forEach(sub => {
                    if (!sub.dateAdded) return;
                    const week = getWeekNumber(sub.dateAdded);
                    const key = `Week ${week}`;
                    if (!weekMap.has(key)) weekMap.set(key, { name: key, submissions: 0, placements: 0, booked: 0, cancelled: 0 });
                    weekMap.get(key).submissions++;
                });
                filteredPlacements.forEach(place => {
                    if (!place.dateAdded) return;
                    const week = getWeekNumber(place.dateAdded);
                    const key = `Week ${week}`;
                    if (!weekMap.has(key)) weekMap.set(key, { name: key, submissions: 0, placements: 0, booked: 0, cancelled: 0 });
                    weekMap.get(key).placements++;
                    if (isBooked(place)) weekMap.get(key).booked++;
                    if (isCancelled(place)) weekMap.get(key).cancelled++;
                });
                return Array.from(weekMap.values()).sort((a, b) => {
                    const weekA = parseInt(a.name.replace('Week ', ''), 10);
                    const weekB = parseInt(b.name.replace('Week ', ''), 10);
                    return weekA - weekB;
                });
            }, [filteredSubmissions, filteredPlacements]);
            
            // Export CSV (by-week data)
            const exportCSV = () => {
                const rows = [['Week', 'Submissions', 'Placements', 'Booked', 'Cancelled']];
                chartData.forEach(d => rows.push([d.name, String(d.submissions), String(d.placements), String(d.booked || 0), String(d.cancelled || 0)]));
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
            const getCancelledShareColor = (pct) => {
                if (pct == null) return 'text-gray-600';
                if (pct >= 50) return 'text-red-600 font-semibold';
                if (pct >= 25) return 'text-yellow-600 font-semibold';
                return 'text-green-600 font-semibold';
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
            
            const detailedJobsMeta = useMemo(function(){
                var owners = [], statuses = [];
                detailedJobs.forEach(function(j){
                    var o = String(j.ownerName != null ? j.ownerName : '').trim();
                    var s = String(j.status != null ? j.status : '').trim();
                    if (o && owners.indexOf(o) < 0) owners.push(o);
                    if (s && statuses.indexOf(s) < 0) statuses.push(s);
                });
                owners.sort(); statuses.sort();
                return { owners: owners, statuses: statuses };
            }, [detailedJobs]);
            const filteredDetailedJobs = useMemo(function(){
                var l = detailedJobs;
                if (filterJobOwner) l = l.filter(function(j){ return String(j.ownerName != null ? j.ownerName : '').toLowerCase().indexOf(filterJobOwner.toLowerCase()) >= 0; });
                if (filterJobStatus) l = l.filter(function(j){ return String(j.status != null ? j.status : '') === filterJobStatus; });
                if (filterJobOpenClosed === 'open') l = l.filter(function(j){ return j.isOpen === true || j.isOpen === 1; });
                if (filterJobOpenClosed === 'closed') l = l.filter(function(j){ return j.isOpen === false || j.isOpen === 0; });
                return l;
            }, [detailedJobs, filterJobOwner, filterJobStatus, filterJobOpenClosed]);
            
            return (
                <div className="max-w-7xl mx-auto">
                    <div className="bg-white rounded-lg shadow-sm border-2 border-slate-200 p-6 mb-6">
                        <div className="flex items-center justify-between mb-6">
                            <div className="flex items-center gap-3">
                                <img src="{{ logo_url }}" alt="Concord" className="h-10 w-auto" />
                                <h1 className="text-2xl font-semibold text-slate-800 tracking-tight">Bullhorn Analytics Dashboard</h1>
                            </div>
                            <div className="flex items-center gap-2 flex-wrap justify-end">
                                <a href="/" className="px-4 py-2 border border-slate-300 text-slate-700 rounded-md hover:bg-slate-50 transition-colors text-sm font-medium">
                                    Back to OAuth
                                </a>
                                <button
                                    onClick={() => { if (viewMode === 'basic') fetchBasicData(); else fetchAnalyticsData(); }}
                                    className="px-4 py-2 bg-slate-800 text-white rounded-md text-sm font-medium hover:bg-slate-700 transition-colors"
                                >
                                    Refresh
                                </button>
                                {(viewMode === 'basic' || (viewMode === 'detailed' && detailedSubmissions.length > 0) || (viewMode === 'detailed_placements' && detailedPlacements.length > 0) || (viewMode === 'jobs' && detailedJobs.length > 0)) && (
                                    <button
                                        onClick={() => {
                                            if (viewMode === 'basic') {
                                                var rows = [['Week', 'Submissions', 'Placements', 'Booked', 'Cancelled']];
                                                chartData.forEach(function(d){ rows.push([d.name, String(d.submissions), String(d.placements), String(d.booked || 0), String(d.cancelled || 0)]); });
                                                var csv = rows.map(function(row){ return row.join(','); }).join('\\n');
                                                var blob = new Blob([csv], { type: 'text/csv' });
                                                var url = window.URL.createObjectURL(blob);
                                                var a = document.createElement('a');
                                                a.href = url;
                                                a.download = 'analytics_' + dateRange.start + '_' + dateRange.end + '.csv';
                                                a.click();
                                                window.URL.revokeObjectURL(url);
                                            } else if (viewMode === 'detailed') {
                                                var rows = [['ID', 'Date', 'Candidate', 'Job Title', 'Client', 'Status', 'Owner']];
                                                filteredDetailed.forEach(function(s){ rows.push([String(s.id || ''), s.dateFormatted || '', s.candidateName || '', s.jobTitle || '', s.clientName || '', s.status || '', s.ownerName || '']); });
                                                var csv = rows.map(function(row){ return row.map(function(c){ return '"' + (c || '').replace(/"/g, '""') + '"'; }).join(','); }).join('\\n');
                                                var blob = new Blob([csv], { type: 'text/csv' });
                                                var url = window.URL.createObjectURL(blob);
                                                var a = document.createElement('a');
                                                a.href = url;
                                                a.download = 'detailed_submissions_' + dateRange.start + '_' + dateRange.end + '.csv';
                                                a.click();
                                                window.URL.revokeObjectURL(url);
                                            } else if (viewMode === 'detailed_placements') {
                                                var rows = [['ID', 'Date', 'Candidate', 'Job Title', 'Client', 'Status', 'Owner']];
                                                filteredDetailedPlacements.forEach(function(p){ rows.push([String(p.id || ''), p.dateFormatted || '', p.candidateName || '', p.jobTitle || '', p.clientName || '', p.status || '', p.ownerName || '']); });
                                                var csv = rows.map(function(row){ return row.map(function(c){ return '"' + (c || '').replace(/"/g, '""') + '"'; }).join(','); }).join('\\n');
                                                var blob = new Blob([csv], { type: 'text/csv' });
                                                var url = window.URL.createObjectURL(blob);
                                                var a = document.createElement('a');
                                                a.href = url;
                                                a.download = 'detailed_placements_' + dateRange.start + '_' + dateRange.end + '.csv';
                                                a.click();
                                                window.URL.revokeObjectURL(url);
                                            } else if (viewMode === 'jobs') {
                                                var rows = [['ID', 'Date', 'Job Title', 'Client', 'Status', 'Open/Closed', 'Owner']];
                                                filteredDetailedJobs.forEach(function(j){ rows.push([String(j.id || ''), j.dateFormatted || '', j.title || '', j.clientName || '', j.status || '', (j.isOpen === true || j.isOpen === 1) ? 'Open' : 'Closed', j.ownerName || '']); });
                                                var csv = rows.map(function(row){ return row.map(function(c){ return '"' + (c || '').replace(/"/g, '""') + '"'; }).join(','); }).join('\\n');
                                                var blob = new Blob([csv], { type: 'text/csv' });
                                                var url = window.URL.createObjectURL(blob);
                                                var a = document.createElement('a');
                                                a.href = url;
                                                a.download = 'jobs_' + dateRange.start + '_' + dateRange.end + '.csv';
                                                a.click();
                                                window.URL.revokeObjectURL(url);
                                            }
                                        }}
                                        className="px-4 py-2 border border-slate-300 text-slate-700 rounded-md text-sm font-medium hover:bg-slate-50 transition-colors"
                                    >
                                        Export CSV
                                    </button>
                                )}
                            </div>
                        </div>
                        
                        {/* View Mode Toggle */}
                        <div className="mb-4 p-4 bg-slate-50 border-2 border-slate-200 rounded-lg">
                            <label className="block text-sm font-medium text-slate-700 mb-2 text-center">View</label>
                            <div className="flex gap-2 flex-wrap justify-center items-center">
                                <button
                                    onClick={() => setViewMode('basic')}
                                    className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                                        viewMode === 'basic' 
                                            ? 'bg-slate-800 text-white' 
                                            : 'bg-white border-2 border-slate-200 text-slate-600 hover:bg-slate-50'
                                    }`}
                                >
                                    At a glance
                                </button>
                                <button
                                    onClick={() => setViewMode('detailed')}
                                    className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                                        viewMode === 'detailed' 
                                            ? 'bg-slate-800 text-white' 
                                            : 'bg-white border-2 border-slate-200 text-slate-600 hover:bg-slate-50'
                                    }`}
                                >
                                    Detailed Submissions
                                </button>
                                <button
                                    onClick={() => setViewMode('detailed_placements')}
                                    className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                                        viewMode === 'detailed_placements' 
                                            ? 'bg-slate-800 text-white' 
                                            : 'bg-white border-2 border-slate-200 text-slate-600 hover:bg-slate-50'
                                    }`}
                                >
                                    Detailed Placements
                                </button>
                                <button
                                    onClick={() => setViewMode('jobs')}
                                    className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                                        viewMode === 'jobs' 
                                            ? 'bg-slate-800 text-white' 
                                            : 'bg-white border-2 border-slate-200 text-slate-600 hover:bg-slate-50'
                                    }`}
                                >
                                    Jobs
                                </button>
                            </div>
                        </div>
                        
                        {/* Date / Period + Filter by owner (when At a glance) */}
                        <div className="flex flex-wrap justify-center items-end gap-4 mb-6 p-4 bg-white border-2 border-slate-200 rounded-lg">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Period</label>
                                <select
                                    value={periodType}
                                    onChange={(e) => setPeriodType(e.target.value)}
                                    className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-slate-400 focus:border-slate-400"
                                >
                                    <option value="week">Week</option>
                                    <option value="month">Month</option>
                                    <option value="year">Year</option>
                                    <option value="custom">Custom range</option>
                                </select>
                            </div>
                            {periodType === 'week' && (
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Date in week</label>
                                    <input type="date" value={weekDate} onChange={(e) => setWeekDate(e.target.value)}
                                        className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-slate-400 focus:border-slate-400" />
                                </div>
                            )}
                            {periodType === 'month' && (
                                <>
                                    <div>
                                        <label className="block text-sm font-medium text-slate-700 mb-1">Year</label>
                                        <select value={year} onChange={(e) => setYear(parseInt(e.target.value))}
                                            className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-slate-400 focus:border-slate-400">
                                            {[2024, 2025, 2026, 2027].map(function(y){ return <option key={y} value={y}>{y}</option>; })}
                                        </select>
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-slate-700 mb-1">Month</label>
                                        <select value={month} onChange={(e) => setMonth(parseInt(e.target.value))}
                                            className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-slate-400 focus:border-slate-400">
                                            {Array.from({ length: 12 }, function(_, i){ var m = i + 1; return <option key={m} value={m}>{new Date(2024, m - 1).toLocaleString('default', { month: 'long' })}</option>; })}
                                        </select>
                                    </div>
                                </>
                            )}
                            {periodType === 'year' && (
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Year</label>
                                    <select value={year} onChange={(e) => setYear(parseInt(e.target.value))}
                                        className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-slate-400 focus:border-slate-400">
                                        {[2024, 2025, 2026, 2027].map(function(y){ return <option key={y} value={y}>{y}</option>; })}
                                    </select>
                                </div>
                            )}
                            {periodType === 'custom' && (
                                <>
                                    <div>
                                        <label className="block text-sm font-medium text-slate-700 mb-1">From</label>
                                        <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
                                            className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-slate-400 focus:border-slate-400" />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-slate-700 mb-1">To</label>
                                        <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
                                            className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-slate-400 focus:border-slate-400" />
                                    </div>
                                </>
                            )}
                            {viewMode === 'basic' && (
                                <div className="flex items-end gap-2">
                                    <div>
                                        <label className="block text-sm font-medium text-slate-700 mb-1">Filter by owner (submitter)</label>
                                        <div className="flex items-center gap-2">
                                            <select
                                                value={filterBasicOwner}
                                                onChange={(e) => setFilterBasicOwner(e.target.value)}
                                                className="px-3 py-2 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-slate-400 focus:border-slate-400 min-w-[180px]"
                                            >
                                                <option value="">All</option>
                                                {basicOwnerList.map(function(o){ return <option key={o.id} value={o.id}>{o.name}</option>; })}
                                            </select>
                                            {filterBasicOwner && (
                                                <button type="button" onClick={() => setFilterBasicOwner('')}
                                                    className="text-sm text-slate-600 hover:text-slate-800">Clear</button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                        
                        {error && (
                            <div className="mb-4 p-4 bg-red-50 border-2 border-red-200 rounded-lg">
                                <p className="text-red-800 text-sm">Error: {error}</p>
                            </div>
                        )}
                        
                        {loading ? (
                            <div className="text-center py-12">
                                <div className="inline-block animate-spin rounded-full h-12 w-12 border-2 border-slate-200 border-t-slate-600"></div>
                                <p className="mt-4 text-slate-600">Loading data...</p>
                            </div>
                        ) : (
                            <>
                                {viewMode === 'basic' && (
                                    <>
                                        {/* Basic View - Stats & Chart (same box style as Detailed) */}
                                        <div className="mb-4 p-4 bg-slate-50 border-2 border-slate-200 rounded-lg">
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                                            <div className="bg-white border-2 border-slate-200 rounded-lg p-4">
                                                <div className="text-sm text-slate-500 mb-1">Total Submissions</div>
                                                <div className="text-2xl font-semibold text-slate-900">{stats.totalSubmissions}</div>
                                            </div>
                                            <div className="bg-white border-2 border-slate-200 rounded-lg p-4">
                                                <div className="text-sm text-slate-500 mb-1">Total Placements</div>
                                                <div className="text-2xl font-semibold text-slate-900">{stats.totalPlacements}</div>
                                            </div>
                                            <div className="bg-white border-2 border-slate-200 rounded-lg p-4">
                                                <div className="text-sm text-slate-500 mb-1">Booked</div>
                                                <div className="text-2xl font-semibold text-slate-900">{stats.totalBooked}</div>
                                            </div>
                                            <div className="bg-white border-2 border-slate-200 rounded-lg p-4">
                                                <div className="text-sm text-slate-500 mb-1">Booked / Submitted</div>
                                                <div className={`text-2xl font-semibold ${getConversionColor(stats.conversionRate)}`}>
                                                    {stats.conversionRate}%
                                                </div>
                                            </div>
                                            <div className="bg-white border-2 border-slate-200 rounded-lg p-4">
                                                <div className="text-sm text-slate-500 mb-1">Cancelled</div>
                                                <div className="text-2xl font-semibold text-slate-900">{stats.totalCancelled}</div>
                                            </div>
                                            <div className="bg-white border-2 border-slate-200 rounded-lg p-4">
                                                <div className="text-sm text-slate-500 mb-1">Cancelled / (Booked+Cancelled)</div>
                                                <div className="text-2xl font-semibold flex justify-between items-baseline gap-2">
                                                    <span className="text-slate-900">{stats.totalCancelled}/{stats.totalEverBooked}</span>
                                                    <span className={getCancelledShareColor(stats.cancelledShare)}>
                                                        {stats.cancelledShare != null ? '(' + stats.cancelledShare.toFixed(1) + '%)' : '(—)'}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                        
                                        <div className="flex flex-col lg:flex-row gap-6">
                                            <div className="flex-1 min-w-0">
                                        <div className="mb-6">
                                            <BarChartCanvas
                                                data={chartData}
                                                labelsKey="name"
                                                datasets={[
                                                    { dataKey: 'submissions', label: 'Submissions', color: 'rgba(59,130,246,0.8)' },
                                                    { dataKey: 'placements', label: 'Placements', color: 'rgba(16,185,129,0.8)' },
                                                    { dataKey: 'booked', label: 'Booked', color: 'rgba(245,158,11,0.8)' },
                                                    { dataKey: 'cancelled', label: 'Cancelled', color: 'rgba(239,68,68,0.8)' }
                                                ]}
                                                title="Submissions, Placements, Booked & Cancelled by Week"
                                                height={300}
                                            />
                                        </div>
                                            </div>
                                            <aside className="lg:w-80 flex-shrink-0">
                                                <div className="p-4 bg-slate-50/80 border-2 border-slate-200 rounded-lg text-sm text-slate-600">
                                                    <h4 className="font-medium text-slate-800 mb-3">How we calculate</h4>
                                                    <ul className="space-y-2 list-none">
                                                        <li><strong>Submissions:</strong> In selected date range. With owner: only that owner (submitter).</li>
                                                        <li><strong>Placements:</strong> In range. With owner: only (candidate, job) submitted by that owner; submissions 12 months back when owner set for linkage.</li>
                                                        <li><strong>Booked:</strong> Status in Requested Credentialing, Credentialed, On assignment, Assignment completed. Current only; excludes cancelled. Linked to owner by (candidate, job).</li>
                                                        <li><strong>Cancelled:</strong> Status in Provider, Concord, Client, or Credentialing Cancelled. Linked to owner by (candidate, job).</li>
                                                        <li><strong>Booked / Submitted:</strong> Booked ÷ Submissions × 100.</li>
                                                        <li><strong>Cancelled / (Booked+Cancelled):</strong> Cancelled ÷ (Booked + Cancelled). Of those who reached booked or were cancelled, the share cancelled. Denominator = Booked + Cancelled.</li>
                                                    </ul>
                                                </div>
                                            </aside>
                                        </div>
                                        </div>
                                    </>
                                )}
                                
                                {viewMode === 'recruiter' && (
                                    <>
                                        {/* Recruiter Leaderboard */}
                                        <div className="mb-4 p-4 bg-slate-50 border-2 border-slate-200 rounded-lg">
                                            <h3 className="text-base font-semibold text-slate-800 mb-4">Recruiter Leaderboard</h3>
                                            <div className="overflow-x-auto bg-white border-2 border-slate-200 rounded-lg">
                                                <table className="w-full">
                                                    <thead>
                                                        <tr className="border-b border-slate-200 bg-slate-50">
                                                            <th className="text-left py-2 px-4 font-medium text-slate-600 text-sm">Recruiter</th>
                                                            <th className="text-right py-2 px-4 font-medium text-slate-600 text-sm">Submissions</th>
                                                            <th className="text-right py-2 px-4 font-medium text-slate-600 text-sm">Presented</th>
                                                            <th className="text-right py-2 px-4 font-medium text-slate-600 text-sm">Placed</th>
                                                            <th className="text-right py-2 px-4 font-medium text-slate-600 text-sm">Conversion %</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {recruitersData.length === 0 ? (
                                                            <tr>
                                                                <td colSpan="5" className="text-center py-8 text-slate-500 text-sm">No recruiter data available</td>
                                                            </tr>
                                                        ) : (
                                                            recruitersData.map((rec, idx) => {
                                                                const conversion = rec.totalSubmissions > 0 
                                                                    ? (rec.totalPlacements / rec.totalSubmissions * 100).toFixed(1) 
                                                                    : 0;
                                                                return (
                                                                    <tr key={idx} className="border-b border-slate-100 hover:bg-slate-50 last:border-b-0">
                                                                        <td className="py-2 px-4 text-slate-800 text-sm">{rec.name}</td>
                                                                        <td className="py-2 px-4 text-right text-slate-600 text-sm">{rec.totalSubmissions}</td>
                                                                        <td className="py-2 px-4 text-right text-slate-600 text-sm">{(rec.statusBreakdown || {})['Presented'] || 0}</td>
                                                                        <td className="py-2 px-4 text-right text-slate-600 text-sm">{rec.totalPlacements}</td>
                                                                        <td className={`py-2 px-4 text-right text-sm ${getConversionColor(parseFloat(conversion))}`}>{conversion}%</td>
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
                                        <div className="mb-4 p-4 bg-slate-50 border-2 border-slate-200 rounded-lg">
                                            <div className="flex items-center justify-between flex-wrap gap-4">
                                                <div>
                                                    <h3 className="text-base font-semibold text-slate-800">Detailed Submissions</h3>
                                                    <p className="text-sm text-slate-600">Candidate, job, status, and owner</p>
                                                </div>
                                                <div className="text-lg font-semibold text-slate-700">{filteredDetailed.length} records</div>
                                            </div>
                                            <div className="mt-3 flex flex-wrap gap-3 items-center">
                                                <span className="text-sm font-medium text-slate-600">Filters</span>
                                                <select value={filterOwner} onChange={(e) => setFilterOwner(e.target.value)}
                                                    className="px-3 py-1.5 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-slate-400 focus:border-slate-400">
                                                    <option value="">All owners</option>
                                                    {detailedMeta.owners.map(function(o){ return <option key={o} value={o}>{o}</option>; })}
                                                </select>
                                                <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}
                                                    className="px-3 py-1.5 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-slate-400 focus:border-slate-400">
                                                    <option value="">All statuses</option>
                                                    {detailedMeta.statuses.map(function(s){ return <option key={s} value={s}>{s}</option>; })}
                                                </select>
                                                {(filterOwner || filterStatus) && (
                                                    <button type="button" onClick={() => { setFilterOwner(''); setFilterStatus(''); }}
                                                        className="text-sm text-slate-600 hover:text-slate-800">Clear</button>
                                                )}
                                            </div>
                                        </div>
                                        
                                        <div className="bg-white border-2 border-slate-200 rounded-lg p-4 mb-6">
                                            <div className="overflow-x-auto">
                                                <table className="w-full text-sm">
                                                    <thead>
                                                        <tr className="border-b border-slate-200 bg-slate-50">
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">ID</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Date</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Candidate</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Job Title</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Client</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Status</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Owner</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {filteredDetailed.length === 0 ? (
                                                            <tr>
                                                                <td colSpan="7" className="text-center py-12 text-slate-500 text-sm">
                                                                    {detailedSubmissions.length === 0 ? 'No submissions for this period' : 'No rows match the filters'}
                                                                </td>
                                                            </tr>
                                                        ) : (
                                                            filteredDetailed.map((sub, idx) => {
                                                                const statusColor = {
                                                                    'Submitted': 'bg-slate-100 text-slate-700',
                                                                    'Presented': 'bg-amber-50 text-amber-800',
                                                                    'Client Review': 'bg-slate-100 text-slate-700',
                                                                    'Interview': 'bg-amber-50 text-amber-800',
                                                                    'Offered': 'bg-emerald-50 text-emerald-800',
                                                                    'Placed': 'bg-emerald-100 text-emerald-800',
                                                                    'Rejected': 'bg-red-50 text-red-700',
                                                                    'Withdrawn': 'bg-slate-100 text-slate-600'
                                                                }[sub.status] || 'bg-slate-100 text-slate-600';
                                                                
                                                                return (
                                                                    <tr key={sub.id || idx} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                                                                        <td className="py-2 px-3 text-slate-500 font-mono text-xs">{sub.id}</td>
                                                                        <td className="py-2 px-3 text-slate-600 whitespace-nowrap">{sub.dateFormatted || '—'}</td>
                                                                        <td className="py-2 px-3 text-slate-800 font-medium">{sub.candidateName}</td>
                                                                        <td className="py-2 px-3 text-slate-600 max-w-xs truncate" title={sub.jobTitle}>{sub.jobTitle}</td>
                                                                        <td className="py-2 px-3 text-slate-500">{sub.clientName}</td>
                                                                        <td className="py-2 px-3">
                                                                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColor}`}>
                                                                                {sub.status}
                                                                            </span>
                                                                        </td>
                                                                        <td className="py-2 px-3 text-slate-600">{sub.ownerName}</td>
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
                                
                                {viewMode === 'detailed_placements' && (
                                    <>
                                        {/* Detailed Placements Table */}
                                        <div className="mb-4 p-4 bg-slate-50 border-2 border-slate-200 rounded-lg">
                                            <div className="flex items-center justify-between flex-wrap gap-4">
                                                <div>
                                                    <h3 className="text-base font-semibold text-slate-800">Detailed Placements</h3>
                                                    <p className="text-sm text-slate-600">Candidate, job, status, and owner</p>
                                                </div>
                                                <div className="text-lg font-semibold text-slate-700">{filteredDetailedPlacements.length} records</div>
                                            </div>
                                            <div className="mt-3 flex flex-wrap gap-3 items-center">
                                                <span className="text-sm font-medium text-slate-600">Filters</span>
                                                <select value={filterPlacementOwner} onChange={(e) => setFilterPlacementOwner(e.target.value)}
                                                    className="px-3 py-1.5 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-slate-400 focus:border-slate-400">
                                                    <option value="">All owners</option>
                                                    {detailedPlacementsMeta.owners.map(function(o){ return <option key={o} value={o}>{o}</option>; })}
                                                </select>
                                                <select value={filterPlacementStatus} onChange={(e) => setFilterPlacementStatus(e.target.value)}
                                                    className="px-3 py-1.5 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-slate-400 focus:border-slate-400">
                                                    <option value="">All statuses</option>
                                                    {detailedPlacementsMeta.statuses.map(function(s){ return <option key={s} value={s}>{s}</option>; })}
                                                </select>
                                                {(filterPlacementOwner || filterPlacementStatus) && (
                                                    <button type="button" onClick={() => { setFilterPlacementOwner(''); setFilterPlacementStatus(''); }}
                                                        className="text-sm text-slate-600 hover:text-slate-800">Clear</button>
                                                )}
                                            </div>
                                        </div>
                                        
                                        <div className="bg-white border-2 border-slate-200 rounded-lg p-4 mb-6">
                                            <div className="overflow-x-auto">
                                                <table className="w-full text-sm">
                                                    <thead>
                                                        <tr className="border-b border-slate-200 bg-slate-50">
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">ID</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Date</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Candidate</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Job Title</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Client</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Status</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Owner</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {filteredDetailedPlacements.length === 0 ? (
                                                            <tr>
                                                                <td colSpan="7" className="text-center py-12 text-slate-500 text-sm">
                                                                    {detailedPlacements.length === 0 ? 'No placements for this period' : 'No rows match the filters'}
                                                                </td>
                                                            </tr>
                                                        ) : (
                                                            filteredDetailedPlacements.map((plc, idx) => {
                                                                const statusColor = {
                                                                    'Approved': 'bg-emerald-50 text-emerald-800',
                                                                    'Active': 'bg-slate-100 text-slate-700',
                                                                    'Denied': 'bg-red-50 text-red-700',
                                                                    'Pending': 'bg-amber-50 text-amber-800',
                                                                    'Terminated': 'bg-slate-100 text-slate-600'
                                                                }[plc.status] || 'bg-slate-100 text-slate-600';
                                                                
                                                                return (
                                                                    <tr key={plc.id || idx} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                                                                        <td className="py-2 px-3 text-slate-500 font-mono text-xs">{plc.id}</td>
                                                                        <td className="py-2 px-3 text-slate-600 whitespace-nowrap">{plc.dateFormatted || '—'}</td>
                                                                        <td className="py-2 px-3 text-slate-800 font-medium">{plc.candidateName}</td>
                                                                        <td className="py-2 px-3 text-slate-600 max-w-xs truncate" title={plc.jobTitle}>{plc.jobTitle}</td>
                                                                        <td className="py-2 px-3 text-slate-500">{plc.clientName}</td>
                                                                        <td className="py-2 px-3">
                                                                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColor}`}>
                                                                                {plc.status}
                                                                            </span>
                                                                        </td>
                                                                        <td className="py-2 px-3 text-slate-600">{plc.ownerName}</td>
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
                                
                                {viewMode === 'jobs' && (
                                    <>
                                        {/* Detailed Jobs: stats, filters, table */}
                                        <div className="mb-4 p-4 bg-slate-50 border-2 border-slate-200 rounded-lg">
                                            <div className="flex items-center justify-between flex-wrap gap-4">
                                                <div>
                                                    <h3 className="text-base font-semibold text-slate-800">Detailed Jobs</h3>
                                                    <p className="text-sm text-slate-600">Job order, client, status, owner</p>
                                                </div>
                                                <div className="text-lg font-semibold text-slate-700">{filteredDetailedJobs.length} records</div>
                                            </div>
                                            <div className="mt-3 text-sm text-slate-600">
                                                Total Jobs: {detailedJobs.length} &nbsp;|&nbsp; Open: {detailedJobs.filter(function(j){ return j.isOpen === true || j.isOpen === 1; }).length} &nbsp;|&nbsp; Closed: {detailedJobs.filter(function(j){ return j.isOpen === false || j.isOpen === 0; }).length}
                                                {(() => {
                                                    var statusCounts = {};
                                                    detailedJobs.forEach(function(j){ var s = String(j.status || '').trim() || 'Unknown'; statusCounts[s] = (statusCounts[s]||0)+1; });
                                                    var top5 = Object.entries(statusCounts).sort(function(a,b){ return b[1]-a[1]; }).slice(0,5);
                                                    if (top5.length) return <span> &nbsp;|&nbsp; Top: {top5.map(function(x){ return x[0] + ' (' + x[1] + ')'; }).join(', ')}</span>;
                                                    return null;
                                                })()}
                                            </div>
                                            <div className="mt-3 flex flex-wrap gap-3 items-center">
                                                <span className="text-sm font-medium text-slate-600">Filters</span>
                                                <select value={filterJobOwner} onChange={(e) => setFilterJobOwner(e.target.value)}
                                                    className="px-3 py-1.5 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-slate-400 focus:border-slate-400">
                                                    <option value="">All owners</option>
                                                    {detailedJobsMeta.owners.map(function(o){ return <option key={o} value={o}>{o}</option>; })}
                                                </select>
                                                <select value={filterJobStatus} onChange={(e) => setFilterJobStatus(e.target.value)}
                                                    className="px-3 py-1.5 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-slate-400 focus:border-slate-400">
                                                    <option value="">All statuses</option>
                                                    {detailedJobsMeta.statuses.map(function(s){ return <option key={s} value={s}>{s}</option>; })}
                                                </select>
                                                <select value={filterJobOpenClosed} onChange={(e) => setFilterJobOpenClosed(e.target.value)}
                                                    className="px-3 py-1.5 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-slate-400 focus:border-slate-400">
                                                    <option value="">All</option>
                                                    <option value="open">Open Only</option>
                                                    <option value="closed">Closed Only</option>
                                                </select>
                                                {(filterJobOwner || filterJobStatus || filterJobOpenClosed) && (
                                                    <button type="button" onClick={() => { setFilterJobOwner(''); setFilterJobStatus(''); setFilterJobOpenClosed(''); }}
                                                        className="text-sm text-slate-600 hover:text-slate-800">Clear</button>
                                                )}
                                            </div>
                                        </div>
                                        
                                        <div className="bg-white border-2 border-slate-200 rounded-lg p-4 mb-6">
                                            <div className="overflow-x-auto">
                                                <table className="w-full text-sm">
                                                    <thead>
                                                        <tr className="border-b border-slate-200 bg-slate-50">
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">ID</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Date</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Job Title</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Client</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Status</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Open/Closed</th>
                                                            <th className="text-left py-2.5 px-3 font-medium text-slate-700">Owner</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {filteredDetailedJobs.length === 0 ? (
                                                            <tr>
                                                                <td colSpan="7" className="text-center py-12 text-slate-500 text-sm">
                                                                    {detailedJobs.length === 0 ? 'No jobs for this period' : 'No rows match the filters'}
                                                                </td>
                                                            </tr>
                                                        ) : (
                                                            filteredDetailedJobs.map(function(job, idx) {
                                                                var statusColor = { 'Open': 'bg-green-50 text-green-800', 'Closed': 'bg-slate-100 text-slate-600', 'On Hold': 'bg-yellow-50 text-yellow-800', 'Cancelled': 'bg-red-50 text-red-700' }[job.status] || 'bg-slate-100 text-slate-600';
                                                                var isOpenVal = job.isOpen === true || job.isOpen === 1;
                                                                return (
                                                                    <tr key={job.id || idx} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                                                                        <td className="py-2 px-3 text-slate-500 font-mono text-xs">{job.id}</td>
                                                                        <td className="py-2 px-3 text-slate-600 whitespace-nowrap">{job.dateFormatted || '—'}</td>
                                                                        <td className="py-2 px-3 text-slate-800 font-medium max-w-xs truncate" title={job.title}>{job.title}</td>
                                                                        <td className="py-2 px-3 text-slate-500">{job.clientName}</td>
                                                                        <td className="py-2 px-3">
                                                                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColor}`}>{job.status}</span>
                                                                        </td>
                                                                        <td className="py-2 px-3">
                                                                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${isOpenVal ? 'bg-green-100 text-green-800 font-semibold' : 'bg-slate-100 text-slate-600'}`}>{isOpenVal ? 'Open' : 'Closed'}</span>
                                                                        </td>
                                                                        <td className="py-2 px-3 text-slate-600">{job.ownerName}</td>
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
                                
                                {/* Explore API - show in all views */}
                                <div className="bg-slate-50 border-2 border-slate-200 rounded-lg p-4">
                                    <h3 className="text-sm font-medium text-slate-800 mb-2">Explore API</h3>
                                    <div className="flex flex-wrap gap-2">
                                        <a href="/api/meta/JobSubmission" target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 bg-white border-2 border-slate-200 text-slate-700 rounded-md text-sm hover:bg-slate-50">JobSubmission meta</a>
                                        <a href="/api/meta/Placement" target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 bg-white border-2 border-slate-200 text-slate-700 rounded-md text-sm hover:bg-slate-50">Placement meta</a>
                                        <a href={'/api/submissions/detailed?start=' + encodeURIComponent(dateRange.start) + '&end=' + encodeURIComponent(dateRange.end)} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 bg-white border-2 border-slate-200 text-slate-700 rounded-md text-sm hover:bg-slate-50">Submissions (raw)</a>
                                        <a href={'/api/placements/detailed?start=' + encodeURIComponent(dateRange.start) + '&end=' + encodeURIComponent(dateRange.end)} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 bg-white border-2 border-slate-200 text-slate-700 rounded-md text-sm hover:bg-slate-50">Placements (raw)</a>
                                        <a href={'/api/jobs/detailed?start=' + encodeURIComponent(dateRange.start) + '&end=' + encodeURIComponent(dateRange.end)} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 bg-white border-2 border-slate-200 text-slate-700 rounded-md text-sm hover:bg-slate-50">Jobs (raw)</a>
                                        <a href={'/api/analytics/recruiters?start=' + encodeURIComponent(dateRange.start) + '&end=' + encodeURIComponent(dateRange.end)} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 bg-white border-2 border-slate-200 text-slate-700 rounded-md text-sm hover:bg-slate-50">Recruiters (raw)</a>
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
                rootEl.innerHTML = '<div class="p-6 text-center bg-red-50 border-2 border-red-200 rounded-lg"><p class="text-red-600 font-semibold">Error: React is not loaded</p></div>';
                return;
            }
            
            if (typeof ReactDOM === 'undefined') {
                rootEl.innerHTML = '<div class="p-6 text-center bg-red-50 border-2 border-red-200 rounded-lg"><p class="text-red-600 font-semibold">Error: ReactDOM is not loaded</p></div>';
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
                rootEl.innerHTML = '<div class="p-6 text-center bg-red-50 border-2 border-red-200 rounded-lg"><p class="text-red-600 font-semibold">Error rendering component</p><p class="text-red-500 text-sm mt-2">' + err.message + '</p></div>';
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

def sync_bullhorn_jobs():
    """Fetch open jobs from Bullhorn API and upsert into Supabase open_jobs table"""
    if not supabase:
        print("⚠️ Supabase client not initialized. Skipping job sync.")
        return
    
    tokens = load_tokens()
    if not tokens or not tokens.get('bh_rest_token'):
        print("⚠️ No valid Bullhorn session. Skipping job sync.")
        return
    
    try:
        rest_url = tokens['rest_url']
        if not rest_url.endswith('/'):
            rest_url += '/'
        
        url = f"{rest_url}query/JobOrder"
        
        params = {
            'BhRestToken': tokens['bh_rest_token'],
            'where': 'isOpen=true AND isDeleted=false',
            'fields': 'id,title,status,isOpen,dateAdded,employmentType,salary,numOpenings,clientCorporation(id,name),owner(id,firstName,lastName)',
            'count': 500
        }
        
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        jobs = data.get('data', [])
        print(f"📥 Fetched {len(jobs)} open jobs from Bullhorn")
        
        if not jobs:
            print("ℹ️ No open jobs to sync")
            return
        
        # Map Bullhorn API response to SQL schema
        synced_at = datetime.now().isoformat()
        upsert_data = []
        
        for job in jobs:
            owner = (job.get('owner') or {})
            client = (job.get('clientCorporation') or {})
            date_added_ms = job.get('dateAdded')
            date_added = None
            if date_added_ms:
                date_added = datetime.fromtimestamp(date_added_ms / 1000).isoformat()
            
            owner_name = f"{owner.get('firstName', '')} {owner.get('lastName', '')}".strip() or None
            
            row = {
                'bullhorn_id': job.get('id'),
                'title': job.get('title', 'Unknown'),
                'status': job.get('status', 'Unknown'),
                'client_id': client.get('id'),
                'client_name': client.get('name'),
                'owner_id': owner.get('id'),
                'owner_name': owner_name,
                'employment_type': job.get('employmentType'),
                'salary': job.get('salary'),
                'start_date': None,  # Not in API response
                'num_openings': job.get('numOpenings'),
                'is_open': job.get('isOpen', True),
                'date_added': date_added,
                'synced_at': synced_at,
                'updated_at': synced_at
            }
            upsert_data.append(row)
        
        # Bulk upsert to Supabase
        result = supabase.table('open_jobs').upsert(
            upsert_data,
            on_conflict='bullhorn_id'
        ).execute()
        
        print(f"✅ Synced {len(upsert_data)} jobs to Supabase (upserted/updated)")
        
    except Exception as e:
        print(f"❌ Error syncing Bullhorn jobs: {e}")

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

# Schedule Bullhorn jobs sync to Supabase (every 60 minutes)
if supabase:
    scheduler.add_job(
        func=sync_bullhorn_jobs,
        trigger="interval",
        minutes=60,
        id='sync_bullhorn_jobs',
        name='Sync Bullhorn open jobs to Supabase',
        replace_existing=True,
    )
    print("✅ Scheduled Bullhorn jobs sync: every 60 minutes")
else:
    print("⚠️ Supabase not configured. Job sync scheduler not started.")

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
    return render_template_string(ANALYTICS_TEMPLATE, logo_url=LOGO_URL)

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
        include_recruiter: If True, include owner (CorporateUser) field. Placement uses owner, not sendingUser.
    
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
            fields = 'id,dateAdded,owner(id,firstName,lastName)'
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
    """Extract recruiter name from sendingUser (JobSubmission) or owner (Placement) field."""
    u = item.get('sendingUser') or item.get('owner')
    if u and (u.get('firstName') or u.get('lastName')):
        return f"{u.get('firstName', '')} {u.get('lastName', '')}".strip() or "Unknown"
    return "Unknown"

def get_recruiter_id(item):
    """Extract recruiter ID from sendingUser (JobSubmission) or owner (Placement) field."""
    u = item.get('sendingUser') or item.get('owner')
    return u.get('id') if u else None

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

@app.route('/api/supabase/status')
def api_supabase_status():
    """Check Supabase configuration and connection status"""
    status = {
        'configured': supabase is not None,
        'supabase_url_set': bool(SUPABASE_URL),
        'supabase_key_set': bool(SUPABASE_KEY),
    }
    
    if not status['configured']:
        missing = []
        if not SUPABASE_URL:
            missing.append('SUPABASE_URL')
        if not SUPABASE_KEY:
            missing.append('SUPABASE_KEY')
        status['message'] = f"Supabase not configured. Missing: {', '.join(missing)}"
        status['instructions'] = "Set SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_KEY) environment variables in Render"
        return jsonify(status), 200
    
    # Test connection by querying a simple table
    try:
        result = supabase.table('open_jobs').select('bullhorn_id', count='exact').limit(1).execute()
        status['connected'] = True
        status['message'] = 'Supabase connected successfully'
        status['table_exists'] = True
    except Exception as e:
        status['connected'] = False
        status['message'] = f'Supabase connection test failed: {str(e)}'
        status['table_exists'] = False
    
    return jsonify(status), 200

@app.route('/api/supabase/sync', methods=['POST'])
def api_supabase_sync():
    """Manually trigger Bullhorn jobs sync to Supabase"""
    if not supabase:
        return jsonify({
            'success': False,
            'error': 'Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_KEY) environment variables.'
        }), 400
    
    try:
        sync_bullhorn_jobs()
        return jsonify({
            'success': True,
            'message': 'Sync completed. Check logs for details.'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
            # Basic: sendingUser (owner) + candidate(id), jobOrder(id) for owner filter; (candidate,job) links to placement (one candidate to multiple jobs = separate)
            fields = 'id,dateAdded,status,sendingUser(id,firstName,lastName),candidate(id),jobOrder(id)'
        
        count = request.args.get('count', 500, type=int)
        count = max(1, min(count, 5000)) if count is not None else 500
        params = {
            'BhRestToken': tokens['bh_rest_token'],
            'where': f"dateAdded>={start_ms} AND dateAdded<={end_ms}",
            'fields': fields,
            'orderBy': '-dateAdded',
            'count': count
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
        
        # id, dateAdded, status, candidate(id), jobOrder(id) for owner filter (candidate,job) to submission; one candidate to multiple jobs = separate books
        fields = 'id,dateAdded,status,candidate(id),jobOrder(id)'
        
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
        
        # Full fields: candidate, job, client, owner. Placement uses owner (CorporateUser), not sendingUser.
        fields = 'id,dateAdded,status,candidate(id,firstName,lastName,email),jobOrder(id,title,clientCorporation(id,name)),owner(id,firstName,lastName)'
        
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
            owner = plc.get('owner', {}) or {}
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

@app.route('/api/jobs/detailed')
def api_jobs_detailed():
    """Fetch detailed JobOrder records. Use start/end (YYYY-MM-DD), or year+month, or year.
    Bullhorn entity: JobOrder. Endpoint: query/JobOrder. JPQL where with dateAdded in ms."""
    tokens = load_tokens()

    if not tokens or not tokens.get('bh_rest_token'):
        return jsonify({'error': 'Not authenticated'}), 401

    start_ms, end_ms = parse_date_range_from_request()

    try:
        rest_url = tokens['rest_url']
        if not rest_url.endswith('/'):
            rest_url += '/'

        url = f"{rest_url}query/JobOrder"

        fields = 'id,dateAdded,title,status,isOpen,clientCorporation(id,name),owner(id,firstName,lastName)'

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

        jobs = data.get('data', [])

        formatted = []
        for job in jobs:
            owner = (job.get('owner') or {})
            client = (job.get('clientCorporation') or {})
            ts = job.get('dateAdded')
            formatted.append({
                'id': job.get('id'),
                'dateAdded': ts,
                'dateFormatted': datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M') if ts else None,
                'title': job.get('title', 'Unknown'),
                'status': job.get('status', 'Unknown'),
                'isOpen': job.get('isOpen', False),
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
