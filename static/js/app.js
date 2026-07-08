const state = {
    items: [],
    platform: 'all',
    sort: 'latest',
    search: '',
    loading: true,
    stats: {},
    readItems: new Set(JSON.parse(localStorage.getItem('readItems') || '[]')),
    lastTotal: 0
};

// Utilities
function debounce(fn, delay) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}

function timeAgo(isoString) {
    if (!isoString) return 'Unknown time';
    const date = new Date(isoString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    // Format explicit date (e.g., Oct 15, 2023)
    const options = { month: 'short', day: 'numeric', year: 'numeric' };
    const dateString = date.toLocaleDateString(undefined, options);
    
    let relativeStr = '';
    let interval = seconds / 31536000;
    if (interval > 1) relativeStr = Math.floor(interval) + ' years ago';
    else {
        interval = seconds / 2592000;
        if (interval > 1) relativeStr = Math.floor(interval) + ' months ago';
        else {
            interval = seconds / 86400;
            if (interval > 1) relativeStr = Math.floor(interval) + ' days ago';
            else {
                interval = seconds / 3600;
                if (interval > 1) relativeStr = Math.floor(interval) + ' hours ago';
                else {
                    interval = seconds / 60;
                    if (interval > 1) relativeStr = Math.floor(interval) + ' mins ago';
                    else relativeStr = 'just now';
                }
            }
        }
    }
    
    return `${dateString} • ${relativeStr}`;
}

function getImportanceClass(score) {
    const s = parseInt(score);
    if (isNaN(s)) return 'importance--low';
    if (s >= 8) return 'importance--high';
    if (s >= 5) return 'importance--medium';
    return 'importance--low';
}

function getSentimentEmoji(sentiment) {
    const s = (sentiment || '').toLowerCase();
    if (s.includes('positive')) return '😊';
    if (s.includes('negative')) return '😟';
    if (s.includes('mixed')) return '🤔';
    return '😐';
}

function getPlatformIcon(platform) {
    const p = (platform || '').toLowerCase();
    if (p === 'youtube') return `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>`;
    if (p === 'instagram') return `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z"/></svg>`;
    if (p === 'twitter') return `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>`;
    return '📌';
}

// API Calls
async function fetchStats() {
    if (window.db) {
        try {
            const snapshot = await window.db.collection('seen_content').get();
            const docs = snapshot.docs.map(doc => doc.data());
            
            const stats = { total: docs.length, by_platform: {} };
            let totalImportance = 0;
            let importanceCount = 0;
            
            docs.forEach(doc => {
                const p = doc.platform;
                stats.by_platform[p] = (stats.by_platform[p] || 0) + 1;
                
                try {
                    const raw = typeof doc.raw_data === 'string' ? JSON.parse(doc.raw_data) : (doc.raw_data || {});
                    const imp = parseInt(raw?.importance_score);
                    if (!isNaN(imp)) {
                        totalImportance += imp;
                        importanceCount++;
                    }
                } catch(e) {}
            });
            
            stats.avg_importance = importanceCount > 0 ? (totalImportance / importanceCount).toFixed(1) : "0.0";
            
            // Update DOM
            animateValue("statTotal", state.stats.total || 0, stats.total, 500);
            animateValue("statYoutube", state.stats.by_platform?.youtube || 0, stats.by_platform?.youtube || 0, 500);
            animateValue("statInstagram", state.stats.by_platform?.instagram || 0, stats.by_platform?.instagram || 0, 500);
            animateValue("statTwitter", state.stats.by_platform?.twitter || 0, stats.by_platform?.twitter || 0, 500);
            
            document.getElementById('statImportance').textContent = stats.avg_importance + '/10';
            
            state.stats = stats;
        } catch (e) {
            console.error("Failed to fetch stats from Firebase", e);
        }
        return;
    }

    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        
        // Update DOM
        animateValue("statTotal", state.stats.total || 0, data.total, 500);
        animateValue("statYoutube", state.stats.by_platform?.youtube || 0, data.by_platform?.youtube || 0, 500);
        animateValue("statInstagram", state.stats.by_platform?.instagram || 0, data.by_platform?.instagram || 0, 500);
        animateValue("statTwitter", state.stats.by_platform?.twitter || 0, data.by_platform?.twitter || 0, 500);
        
        document.getElementById('statImportance').textContent = data.avg_importance + '/10';
        
        state.stats = data;
    } catch (e) {
        console.error("Failed to fetch stats", e);
    }
}

async function fetchFeed() {
    state.loading = true;
    updateUIStates();
    
    if (window.db) {
        try {
            const snapshot = await window.db.collection('seen_content')
                .orderBy('analyzed_at', 'desc')
                .limit(100)
                .get();
                
            let items = snapshot.docs.map(doc => {
                let data = doc.data();
                try {
                    data.analysis = typeof data.raw_data === 'string' ? JSON.parse(data.raw_data) : (data.raw_data || {});
                } catch(e) { data.analysis = {}; }
                return data;
            });
            
            // Filter platform
            if (state.platform !== 'all') {
                items = items.filter(i => i.platform === state.platform);
            }
            // Search
            if (state.search) {
                const s = state.search.toLowerCase();
                items = items.filter(i => 
                    (i.title || '').toLowerCase().includes(s) || 
                    (i.summary || '').toLowerCase().includes(s)
                );
            }
            // Sort
            if (state.sort === 'importance') {
                items.sort((a, b) => {
                    const scoreA = parseInt(a.analysis?.importance_score) || 0;
                    const scoreB = parseInt(b.analysis?.importance_score) || 0;
                    return scoreB - scoreA;
                });
            } else {
                items.sort((a, b) => new Date(b.published_at || b.analyzed_at) - new Date(a.published_at || a.analyzed_at));
            }
            
            items = items.slice(0, 50);
            
            if (state.lastTotal > 0 && items.length > state.lastTotal) {
                updateBadge(items.length - state.lastTotal);
                if (items.length > 0) {
                    sendBrowserNotification(items[0]);
                }
            }
            state.lastTotal = items.length;
            
            state.items = items;
            renderFeed();
        } catch (e) {
            console.error("Failed to fetch feed from Firebase", e);
        } finally {
            state.loading = false;
            updateUIStates();
        }
        return;
    }
    
    try {
        const query = new URLSearchParams({
            platform: state.platform,
            sort: state.sort,
            search: state.search,
            limit: 50
        });
        
        const res = await fetch(`/api/feed?${query.toString()}`);
        const data = await res.json();
        
        if (state.lastTotal > 0 && data.total > state.lastTotal) {
            updateBadge(data.total - state.lastTotal);
            if (data.items.length > 0) {
                sendBrowserNotification(data.items[0]);
            }
        }
        state.lastTotal = data.total;
        
        state.items = data.items;
        renderFeed();
    } catch (e) {
        console.error("Failed to fetch feed", e);
    } finally {
        state.loading = false;
        updateUIStates();
    }
}

// UI Updates
function updateUIStates() {
    const loadingEl = document.getElementById('loadingState');
    const emptyEl = document.getElementById('emptyState');
    const feedEl = document.getElementById('feedContainer');
    
    if (state.loading && state.items.length === 0) {
        loadingEl.style.display = 'flex';
        emptyEl.style.display = 'none';
        feedEl.style.display = 'none';
    } else if (!state.loading && state.items.length === 0) {
        loadingEl.style.display = 'none';
        emptyEl.style.display = 'flex';
        feedEl.style.display = 'none';
    } else {
        loadingEl.style.display = 'none';
        emptyEl.style.display = 'none';
        feedEl.style.display = 'grid';
    }
}

function updateBadge(count) {
    const badge = document.getElementById('notifBadge');
    if (count > 0) {
        badge.textContent = count;
        badge.style.display = 'block';
    } else {
        badge.style.display = 'none';
    }
}

function renderFeed() {
    const container = document.getElementById('feedContainer');
    container.innerHTML = '';
    
    state.items.forEach((item, index) => {
        const card = createCard(item);
        card.style.animationDelay = `${index * 0.05}s`;
        container.appendChild(card);
    });
}

function createCard(item) {
    const card = document.createElement('div');
    const platformClass = `card--${(item.platform || '').toLowerCase()}`;
    card.className = `card card-enter ${platformClass}`;
    
    const analysis = item.analysis || {};
    const importanceScore = analysis.importance_score || '?';
    const importanceClass = getImportanceClass(importanceScore);
    const sentimentEmoji = getSentimentEmoji(analysis.sentiment);
    const platformIcon = getPlatformIcon(item.platform);
    
    const isRead = state.readItems.has(item.content_id);
    if (!isRead) {
        card.style.borderRight = '4px solid var(--accent-primary)';
    }
    
    const topicsHtml = (analysis.key_topics || []).slice(0, 3).map(t => 
        `<span class="topic-pill">${t}</span>`
    ).join('');

    const thumb = item.thumbnail || analysis.thumbnail;
    const thumbnailHtml = thumb ? `<div class="card-thumbnail"><img src="${thumb}" alt="Thumbnail"></div>` : '';

    card.innerHTML = `
        <div class="card-header">
            <div class="card-badge">${platformIcon} <span>${item.platform}</span></div>
            <div class="card-time">${timeAgo(item.published_at || item.analyzed_at)}</div>
        </div>
        ${thumbnailHtml}
        <div class="card-title">${item.title || 'Untitled Content'}</div>
        <div class="card-summary">${analysis.summary || 'No summary available.'}</div>
        <div class="card-topics">${topicsHtml}</div>
        <div class="card-footer">
            <div class="card-metrics">
                <span class="metric-badge ${importanceClass}">🔥 ${importanceScore}/10</span>
                <span class="metric-badge sentiment-badge" title="Sentiment: ${analysis.sentiment}">${sentimentEmoji}</span>
            </div>
            <button class="view-btn">View Details</button>
        </div>
    `;
    
    card.addEventListener('click', () => openDetail(item, card));
    return card;
}

// Modal Functions
function openDetail(item, cardElement) {
    if (!state.readItems.has(item.content_id)) {
        state.readItems.add(item.content_id);
        localStorage.setItem('readItems', JSON.stringify([...state.readItems]));
        if (cardElement) {
            cardElement.style.borderRight = 'none';
        }
    }
    
    const modalContent = document.getElementById('modalContent');
    const analysis = item.analysis || {};
    
    const platformIcon = getPlatformIcon(item.platform);
    
    const topicsHtml = (analysis.key_topics || []).map(t => 
        `<span class="topic-pill">${t}</span>`
    ).join('');
    
    const takeawaysHtml = (analysis.key_takeaways || []).map(t => 
        `<li class="takeaway-item">${t}</li>`
    ).join('');

    const thumb = item.thumbnail || analysis.thumbnail;
    const thumbnailHtml = thumb ? `<div class="modal-thumbnail"><img src="${thumb}" alt="Thumbnail"></div>` : '';

    modalContent.innerHTML = `
        <div class="modal-header">
            <div class="card-badge">${platformIcon} <span>${item.platform}</span></div>
            <h2 class="modal-title">${item.title}</h2>
            <div class="card-time">Published: ${new Date(item.published_at || item.analyzed_at).toLocaleString()}</div>
        </div>
        
        ${thumbnailHtml}
        
        <div class="modal-section">
            <h4>AI Summary</h4>
            <div class="modal-summary">${analysis.summary || 'No summary available.'}</div>
        </div>
        
        ${topicsHtml ? `
        <div class="modal-section">
            <h4>Key Topics</h4>
            <div class="card-topics">${topicsHtml}</div>
        </div>` : ''}
        
        ${takeawaysHtml ? `
        <div class="modal-section">
            <h4>Key Takeaways</h4>
            <ul class="takeaway-list">${takeawaysHtml}</ul>
        </div>` : ''}
        
        <div class="modal-section" style="display:flex; gap:16px; margin-top:32px;">
            <div class="metric-badge ${getImportanceClass(analysis.importance_score)}">
                🔥 Importance: ${analysis.importance_score}/10
            </div>
            <div class="metric-badge sentiment-badge">
                ${getSentimentEmoji(analysis.sentiment)} ${analysis.sentiment || 'Unknown'}
            </div>
            <div class="metric-badge sentiment-badge">
                📁 ${analysis.content_category || 'Unknown'}
            </div>
        </div>
        
        <div class="modal-actions">
            <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="btn-primary">
                Open Original ↗
            </a>
        </div>
    `;
    
    document.getElementById('modalOverlay').classList.add('active');
}

function closeModal() {
    document.getElementById('modalOverlay').classList.remove('active');
}

// Animation Utils
function animateValue(id, start, end, duration) {
    if (start === end) {
        document.getElementById(id).textContent = end;
        return;
    }
    const obj = document.getElementById(id);
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.innerHTML = Math.floor(progress * (end - start) + start);
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

// Notifications
function requestNotificationPermission() {
    if (!("Notification" in window)) {
        alert("This browser does not support desktop notification");
    } else if (Notification.permission === "granted") {
        updateBadge(0); // Clear badge on click
    } else if (Notification.permission !== "denied") {
        Notification.requestPermission().then(permission => {
            if (permission === "granted") {
                new Notification("Notifications Enabled", {
                    body: "You will now receive alerts for new content."
                });
            }
        });
    }
}

function sendBrowserNotification(item) {
    if ("Notification" in window && Notification.permission === 'granted') {
        const emoji = getPlatformEmoji(item.platform);
        new Notification(`${emoji} New ${item.platform} ${item.content_type}`, {
            body: item.title,
            icon: '/static/icon.png',
            tag: item.content_id,
        });
    }
}

// Setup Event Listeners
function setupEventListeners() {
    // Search
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', debounce((e) => {
        state.search = e.target.value;
        fetchFeed();
    }, 300));
    
    // Filters
    document.querySelectorAll('.filter-tab').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active'));
            const target = e.currentTarget;
            target.classList.add('active');
            state.platform = target.dataset.platform;
            fetchFeed();
        });
    });
    
    // Sort
    document.getElementById('sortSelect').addEventListener('change', (e) => {
        state.sort = e.target.value;
        fetchFeed();
    });
    
    // Modal
    document.getElementById('modalClose').addEventListener('click', closeModal);
    document.getElementById('modalOverlay').addEventListener('click', (e) => {
        if (e.target.id === 'modalOverlay') closeModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });
    
    // Notifications
    document.getElementById('notifBell').addEventListener('click', () => {
        requestNotificationPermission();
        updateBadge(0);
    });
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    fetchStats();
    fetchFeed();
    setupEventListeners();
    
    // Auto-refresh
    setInterval(fetchFeed, 30000); // 30s
    setInterval(fetchStats, 60000); // 60s
});

// PWA Service Worker Registration
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
            .then(registration => {
                console.log('ServiceWorker registration successful with scope: ', registration.scope);
            })
            .catch(err => {
                console.log('ServiceWorker registration failed: ', err);
            });
    });
}
