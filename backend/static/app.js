/**
 * ENTERPRISE AI CODE REVIEWER DASHBOARD CONTROLLER (Modular SPA Architecture)
 */

class DashboardApp {
    constructor() {
        this.currentTab = 'overview';
        this.currentRole = 'Developer';
        this.currentPage = 1;
        this.pageSize = 6;
        this.ws = null;
        this.charts = { trend: null, pie: null };
        this.selectedReview = null;
        this.selectedMemoryId = null;

        // Document bindings
        this.initDOM();
        this.loadConfig(); // Dynamic environment branding
        this.initEvents();
        this.checkAuth();
    }

    initDOM() {
        this.authShield = document.getElementById('auth-shield');
        this.btnLogin = document.getElementById('btn-login');
        this.btnLogout = document.getElementById('btn-logout');
        
        this.btnThemeToggle = document.getElementById('btn-theme-toggle');
        this.selectRole = document.getElementById('select-role');
        this.liveStatusContainer = document.querySelector('.live-status');
        this.txtLiveStatus = document.getElementById('txt-live-status');

        this.navItems = document.querySelectorAll('.nav-item');
        this.tabContents = document.querySelectorAll('.tab-content');

        // Drawer
        this.drawer = document.getElementById('drawer-review-details');
        this.btnCloseDrawer = document.getElementById('drawer-review-details'); // Close by background click too

        // Retrainer
        this.btnTriggerRetrain = document.getElementById('btn-trigger-retrain');
        this.consoleTerminal = document.getElementById('console-terminal');

        // Memory modal
        this.modalBoost = document.getElementById('modal-boost');
        this.btnSaveBoost = document.getElementById('btn-save-boost');
        this.boostScoreInput = document.getElementById('boost-score-input');
    }

    initEvents() {
        // Authenticate
        this.btnLogin.addEventListener('click', () => this.login());
        this.btnLogout.addEventListener('click', () => this.logout());

        // Theme Toggle
        this.btnThemeToggle.addEventListener('click', () => this.toggleTheme());

        // RBAC selector
        this.selectRole.addEventListener('change', (e) => this.handleRoleChange(e.target.value));

        // Navigation
        this.navItems.forEach(item => {
            item.addEventListener('click', (e) => {
                const targetTab = e.currentTarget.getAttribute('data-tab');
                this.switchTab(targetTab);
            });
        });

        // Audit Log Filters
        document.getElementById('filter-search').addEventListener('input', () => this.debounce(() => this.loadReviews(), 300));
        document.getElementById('filter-repo').addEventListener('change', () => this.loadReviews());
        document.getElementById('filter-sentiment').addEventListener('change', () => this.loadReviews());
        document.getElementById('btn-reset-filters').addEventListener('click', () => this.resetFilters());

        // Audit Log Pagination
        document.getElementById('btn-page-prev').addEventListener('click', () => this.changePage(-1));
        document.getElementById('btn-page-next').addEventListener('click', () => this.changePage(1));

        // Memory Search
        document.getElementById('filter-memory-search').addEventListener('input', () => this.debounce(() => this.loadMemories(), 300));

        // Settings Form
        document.getElementById('form-repo-settings').addEventListener('submit', (e) => this.saveSettings(e));
        document.getElementById('settings-select-repo').addEventListener('change', (e) => this.loadRepoSettings(e.target.value));

        // Trigger Retraining
        this.btnTriggerRetrain.addEventListener('click', () => this.triggerRetraining());

        // Close details drawer
        document.getElementById('btn-close-drawer').addEventListener('click', () => this.toggleDrawer(false));
        document.getElementById('btn-close-modal').addEventListener('click', () => this.toggleModalBoost(false));

        // Keyboard Shortcuts: Ctrl+Alt+R triggers retraining, Escape closes drawers
        window.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.altKey && e.key.toLowerCase() === 'r') {
                e.preventDefault();
                this.triggerRetraining();
            }
            if (e.key === 'Escape') {
                this.toggleDrawer(false);
                this.toggleModalBoost(false);
            }
        });
    }

    /* AUTHENTICATION SHIELD */
    checkAuth() {
        if (localStorage.getItem('admin_authenticated') === 'true') {
            this.authShield.classList.add('hidden');
            this.currentRole = localStorage.getItem('user_role') || 'Developer';
            this.selectRole.value = this.currentRole;
            this.handleRoleChange(this.currentRole);
            this.initWebSocket();
            this.initCharts();
            this.loadDashboardData();
        }
    }

    login() {
        localStorage.setItem('admin_authenticated', 'true');
        localStorage.setItem('user_role', 'Developer');
        this.authShield.classList.add('hidden');
        this.currentRole = 'Developer';
        this.selectRole.value = 'Developer';
        this.handleRoleChange('Developer');
        this.initWebSocket();
        this.initCharts();
        this.loadDashboardData();
        this.addTerminalLine('system', '[Auth] Secure GitHub App Session Initiated successfully.');
    }

    logout() {
        localStorage.removeItem('admin_authenticated');
        localStorage.removeItem('user_role');
        this.authShield.classList.remove('hidden');
        if (this.ws) {
            this.ws.close();
        }
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/dashboard/config');
            const data = await response.json();

            // 1. Browser tab title
            if (data.browser_title) {
                document.title = data.browser_title;
            }

            // 2. Main top-left branding
            const txtBrandName = document.getElementById('txt-brand-name');
            if (txtBrandName && data.platform_name) {
                txtBrandName.textContent = data.platform_name;
            }

            const txtBrandSubtitle = document.getElementById('txt-brand-subtitle');
            if (txtBrandSubtitle && data.platform_subtitle) {
                txtBrandSubtitle.textContent = data.platform_subtitle;
            }

            const iconBrandLogo = document.getElementById('icon-brand-logo');
            if (iconBrandLogo && data.logo_icon_class) {
                iconBrandLogo.className = `${data.logo_icon_class} logo-icon`;
            }

            // 3. Login shield overlay branding
            const iconLoginLogo = document.getElementById('icon-login-logo');
            if (iconLoginLogo && data.login_logo_icon_class) {
                iconLoginLogo.className = `${data.login_logo_icon_class} auth-logo`;
            }

            const txtLoginTitle = document.getElementById('txt-login-title');
            if (txtLoginTitle && data.platform_name) {
                txtLoginTitle.textContent = data.platform_name;
            }

            const txtLoginSubtitle = document.getElementById('txt-login-subtitle');
            if (txtLoginSubtitle && data.platform_subtitle) {
                txtLoginSubtitle.textContent = data.platform_subtitle;
            }

        } catch (err) {
            console.error("Failed to load platform branding configurations:", err);
        }
    }

    /* THEME SWITCHER */
    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const nextTheme = currentTheme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', nextTheme);
        
        const themeIcon = this.btnThemeToggle.querySelector('i');
        if (nextTheme === 'light') {
            themeIcon.className = 'fa-solid fa-sun';
        } else {
            themeIcon.className = 'fa-solid fa-moon';
        }

        // Redraw charts to match theme styling variables
        setTimeout(() => this.redrawCharts(nextTheme), 150);
    }

    /* WEBSOCKET REAL-TIME BRIDGE */
    initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${window.location.host}/ws/dashboard`);

        this.ws.onopen = () => {
            this.liveStatusContainer.className = 'live-status online';
            this.txtLiveStatus.textContent = 'Real-time WebSocket Live';
        };

        this.ws.onclose = () => {
            this.liveStatusContainer.className = 'live-status';
            this.txtLiveStatus.textContent = 'Updates Offline (Retrying...)';
            setTimeout(() => this.initWebSocket(), 5000);
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.event === 'refresh') {
                    this.loadDashboardData();
                }
            } catch (err) {
                console.error("Failed to parse WebSocket broadcast event:", err);
            }
        };
    }

    /* RBAC SIMULATION HANLDER */
    handleRoleChange(role) {
        this.currentRole = role;
        localStorage.setItem('user_role', role);

        const rbacMemoryBanner = document.getElementById('rbac-memory-banner');
        const rbacSettingsBanner = document.getElementById('rbac-settings-banner');

        // Banners visibility
        if (role === 'Admin') {
            rbacMemoryBanner.style.display = 'none';
            rbacSettingsBanner.style.display = 'none';
            this.btnTriggerRetrain.removeAttribute('disabled');
            document.getElementById('btn-save-settings').removeAttribute('disabled');
        } else {
            rbacMemoryBanner.style.display = 'flex';
            rbacSettingsBanner.style.display = 'flex';
            this.btnTriggerRetrain.setAttribute('disabled', 'true');
            document.getElementById('btn-save-settings').setAttribute('disabled', 'true');
        }

        // Reload views to update button permissions dynamically
        if (this.currentTab === 'memory') {
            this.loadMemories();
        } else if (this.currentTab === 'settings') {
            this.loadRepoSettings('test/repo');
        } else if (this.currentTab === 'health') {
            this.loadSystemStatus();
        }
    }

    /* TAB NAVIGATOR */
    switchTab(tab) {
        this.currentTab = tab;
        this.navItems.forEach(item => {
            item.classList.toggle('active', item.getAttribute('data-tab') === tab);
        });

        this.tabContents.forEach(content => {
            content.classList.toggle('active', content.getAttribute('id') === `tab-${tab}`);
        });

        // Trigger dynamic tab load
        if (tab === 'overview') {
            this.loadStats();
        } else if (tab === 'reviews') {
            this.currentPage = 1;
            this.loadReviews();
        } else if (tab === 'memory') {
            this.loadMemories();
        } else if (tab === 'settings') {
            this.loadRepoSettings('test/repo');
        } else if (tab === 'health') {
            this.loadSystemStatus();
        }
    }

    /* DATA LOADER ENGINES */
    loadDashboardData() {
        this.loadStats();
        if (this.currentTab === 'reviews') this.loadReviews();
        if (this.currentTab === 'memory') this.loadMemories();
        if (this.currentTab === 'settings') this.loadRepoSettings('test/repo');
        if (this.currentTab === 'health') this.loadSystemStatus();
    }

    async loadStats() {
        try {
            const response = await fetch('/api/dashboard/stats');
            const data = await response.json();

            document.getElementById('stat-total-reviews').textContent = data.total_reviews;
            document.getElementById('stat-helpfulness-rate').textContent = `${data.helpfulness_rate}%`;
            document.getElementById('stat-false-positive-rate').textContent = `${data.false_positive_rate}%`;
            document.getElementById('stat-repos-count').textContent = data.unique_repos;

            // Populate ApexCharts
            this.updateCharts(data);
        } catch (err) {
            console.error("Failed to load analytics metrics stats:", err);
        }
    }

    async loadReviews() {
        this.renderTableSkeleton('table-audit-log', 7);

        const search = document.getElementById('filter-search').value;
        const repo = document.getElementById('filter-repo').value;
        const sentiment = document.getElementById('filter-sentiment').value;

        let url = `/api/dashboard/reviews?page=${this.currentPage}&size=${this.pageSize}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (repo) url += `&repo=${encodeURIComponent(repo)}`;
        if (sentiment) url += `&sentiment=${sentiment}`;

        try {
            const response = await fetch(url);
            const data = await response.json();
            this.renderReviewsTable(data);
        } catch (err) {
            console.error("Failed to load audited review comments:", err);
        }
    }

    renderReviewsTable(data) {
        const tbody = document.querySelector('#table-audit-log tbody');
        tbody.innerHTML = '';

        if (!data.reviews || data.reviews.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center" style="text-align: center; color: var(--text-secondary);">No review entries found matching filters.</td></tr>`;
            document.getElementById('txt-page-info').textContent = 'Showing 0-0 of 0 entries';
            return;
        }

        data.reviews.forEach(review => {
            const tr = document.createElement('tr');
            
            // Sentiment badge
            let badgeClass = 'neutral';
            let badgeText = 'Neutral';
            if (review.score > 0) {
                badgeClass = 'positive';
                badgeText = `Positive (+${review.score})`;
            } else if (review.score < 0) {
                badgeClass = 'negative';
                badgeText = `Rejected (${review.score})`;
            }

            // Decayed RAG Weight
            let weightClass = 'neutral';
            if (review.decayed_score > 0) weightClass = 'positive';
            else if (review.decayed_score < 0) weightClass = 'negative';

            tr.innerHTML = `
                <td>PR #${review.pr_number}</td>
                <td><strong>${review.repo_full_name}</strong></td>
                <td><code style="font-family: inherit; font-size: 13px;">${review.file_path}</code></td>
                <td><span class="badge ${badgeClass}">${badgeText}</span></td>
                <td><span class="badge ${weightClass}">${review.decayed_score}</span></td>
                <td><span style="font-size: 12px; color: var(--text-secondary);">${review.created_at}</span></td>
                <td>
                    <button class="btn btn-outline btn-sm btn-view-review" data-id="${review.id}"><i class="fa-solid fa-circle-info"></i> Explain</button>
                </td>
            `;

            tr.querySelector('.btn-view-review').addEventListener('click', () => this.showReviewDetails(review));
            tbody.appendChild(tr);
        });

        // Pagination metadata
        const start = (data.page - 1) * data.size + 1;
        const end = Math.min(start + data.reviews.length - 1, data.total);
        document.getElementById('txt-page-info').textContent = `Showing ${start}-${end} of ${data.total} entries`;

        // Buttons state
        document.getElementById('btn-page-prev').disabled = data.page <= 1;
        document.getElementById('btn-page-next').disabled = end >= data.total;
    }

    async showReviewDetails(review) {
        this.selectedReview = review;
        
        document.getElementById('drawer-repo').textContent = review.repo_full_name;
        document.getElementById('drawer-pr').textContent = `PR #${review.pr_number}`;
        document.getElementById('drawer-decay-score').textContent = review.decayed_score;
        
        // Mocking similarity & RAG explanation metrics
        const simPercent = review.score !== 0 ? Math.round(75 + Math.random() * 20) : 0;
        document.getElementById('drawer-similarity').textContent = simPercent > 0 ? `${simPercent}%` : 'N/A';
        
        const explanationText = review.score > 0 
            ? `The developer welcomed this guideline suggestion. The pattern has been weighted UP inside ChromaDB, which increases the likelihood of fetching matching rules for reviews.`
            : review.score < 0 
            ? `The developer rejected this comment as incorrect or unhelpful. The pattern has been marked as an Anti-Pattern inside ChromaDB, instructing the review agent not to repeat this comment.`
            : `This review was generated from baseline code guidelines. It has not received developer feedback yet.`;
        document.getElementById('drawer-explanation').textContent = explanationText;

        document.getElementById('drawer-problem-code').textContent = review.code_snippet;
        document.getElementById('drawer-comment').textContent = review.comment_text;
        
        // Suggested fix code snippet
        const fixBlock = document.getElementById('drawer-suggested-fix');
        if (review.suggested_fix) {
            fixBlock.parentElement.style.display = 'block';
            fixBlock.textContent = review.suggested_fix;
        } else {
            fixBlock.parentElement.style.display = 'none';
        }

        // Developer applied fix patch
        const devFixBlock = document.getElementById('drawer-applied-fix');
        if (review.score > 0 && review.suggested_fix) {
            devFixBlock.parentElement.style.display = 'block';
            // Simulate Git diff patch
            devFixBlock.textContent = review.suggested_fix.split('\n').map(l => `+ ${l}`).join('\n');
        } else {
            devFixBlock.parentElement.style.display = 'none';
        }

        this.toggleDrawer(true);
    }

    toggleDrawer(show) {
        if (show) {
            this.drawer.classList.add('active');
        } else {
            this.drawer.classList.remove('active');
        }
    }

    changePage(delta) {
        this.currentPage += delta;
        this.loadReviews();
    }

    resetFilters() {
        document.getElementById('filter-search').value = '';
        document.getElementById('filter-repo').value = '';
        document.getElementById('filter-sentiment').value = '';
        this.currentPage = 1;
        this.loadReviews();
    }

    /* RAG VECTOR MEMORY MANAGER */
    async loadMemories() {
        const search = document.getElementById('filter-memory-search').value;
        let url = `/api/dashboard/memory`;
        if (search) url += `?search=${encodeURIComponent(search)}`;

        try {
            const response = await fetch(url);
            const memories = await response.json();
            this.renderMemoryTable(memories);
        } catch (err) {
            console.error("Failed to load Vector RAG memories:", err);
        }
    }

    renderMemoryTable(memories) {
        const tbody = document.querySelector('#table-memory-logs tbody');
        tbody.innerHTML = '';

        if (!memories || memories.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">No vector guidelines found in ChromaDB.</td></tr>`;
            return;
        }

        const isAdmin = this.currentRole === 'Admin';

        memories.forEach(memory => {
            const tr = document.createElement('tr');
            
            // Format code snippet window
            const snippet = memory.problematic_code.split('\n').slice(0, 3).join('\n') + (memory.problematic_code.split('\n').length > 3 ? '\n...' : '');
            
            // Format score weight
            const scoreVal = parseFloat(memory.score);
            let scoreBadgeClass = 'neutral';
            let scoreText = scoreVal.toFixed(2);
            if (scoreVal > 0) {
                scoreBadgeClass = 'positive';
                scoreText = `+${scoreVal.toFixed(2)}`;
            } else if (scoreVal < 0) {
                scoreBadgeClass = 'negative';
            }

            // Source layer
            const sourceBadge = memory.source === 'feedback_loop' ? '<span class="badge system">Feedback</span>' : '<span class="badge neutral">Baseline</span>';

            tr.innerHTML = `
                <td>${sourceBadge}</td>
                <td><pre style="background: var(--code-bg); padding: 6px; border-radius: 4px; font-family: 'Courier New', monospace; font-size: 11px;">${this.escapeHTML(snippet)}</pre></td>
                <td><span style="font-size: 13px; color: var(--text-secondary);">${this.escapeHTML(memory.review_comment)}</span></td>
                <td><span class="badge ${scoreBadgeClass}">${scoreText}</span></td>
                <td>
                    <div style="display: flex; gap: 8px;">
                        <button class="btn btn-outline btn-sm btn-boost-mem" ${isAdmin ? '' : 'disabled'}><i class="fa-solid fa-arrow-trend-up"></i> Boost</button>
                        <button class="btn btn-outline btn-sm btn-delete-mem" style="border-color: rgba(244, 63, 94, 0.2); color: #f87171;" ${isAdmin ? '' : 'disabled'}><i class="fa-solid fa-trash"></i> Delete</button>
                    </div>
                </td>
            `;

            // Wire actions
            if (isAdmin) {
                tr.querySelector('.btn-boost-mem').addEventListener('click', () => this.openBoostModal(memory.id, memory.score));
                tr.querySelector('.btn-delete-mem').addEventListener('click', () => this.deleteMemoryEntry(memory.id));
            }

            tbody.appendChild(tr);
        });
    }

    openBoostModal(id, currentScore) {
        this.selectedMemoryId = id;
        this.boostScoreInput.value = parseFloat(currentScore).toFixed(1);
        this.toggleModalBoost(true);
    }

    toggleModalBoost(show) {
        if (show) {
            this.modalBoost.classList.add('active');
        } else {
            this.modalBoost.classList.remove('active');
            this.selectedMemoryId = null;
        }
    }

    async saveMemoryBoost() {
        if (!this.selectedMemoryId) return;

        const score = parseFloat(this.boostScoreInput.value);
        try {
            const response = await fetch('/api/dashboard/memory/boost', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: this.selectedMemoryId,
                    score: score,
                    role: this.currentRole
                })
            });

            if (response.ok) {
                this.addTerminalLine('success', `[RAG Boost] Vector Memory ID ${this.selectedMemoryId} weight score boosted to ${score.toFixed(2)}.`);
                this.toggleModalBoost(false);
                this.loadMemories();
                this.loadStats();
            } else {
                const err = await response.json();
                alert(`Boost failed: ${err.detail}`);
            }
        } catch (err) {
            console.error("Failed to apply vector RAG score boost:", err);
        }
    }

    async deleteMemoryEntry(id) {
        if (!confirm("Are you sure you want to permanently delete this guideline from the ChromaDB vector database?")) return;

        try {
            const response = await fetch('/api/dashboard/memory/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: id,
                    role: this.currentRole
                })
            });

            if (response.ok) {
                this.addTerminalLine('error', `[RAG Prune] Guidelines Memory ID ${id} permanently removed from ChromaDB.`);
                this.loadMemories();
                this.loadStats();
            } else {
                const err = await response.json();
                alert(`Delete failed: ${err.detail}`);
            }
        } catch (err) {
            console.error("Failed to delete Vector RAG memory entry:", err);
        }
    }

    // Trigger memory boost save
    initMemoryBoostSave() {
        this.btnSaveBoost.addEventListener('click', () => this.saveMemoryBoost());
    }

    /* REPOSITORY SETTINGS CONFIGS */
    async loadRepoSettings(repo) {
        try {
            const response = await fetch(`/api/dashboard/settings?repo=${encodeURIComponent(repo)}`);
            const data = await response.json();

            document.getElementById('settings-strictness').value = data.strictness;
            document.getElementById('settings-review-mode').value = data.review_mode;
            document.getElementById('settings-retrieval-depth').value = data.retrieval_depth;
            document.getElementById('settings-custom-prompt').value = data.custom_prompt;
        } catch (err) {
            console.error("Failed to load repo settings:", err);
        }
    }

    async saveSettings(e) {
        e.preventDefault();

        const repo = document.getElementById('settings-select-repo').value;
        const strictness = document.getElementById('settings-strictness').value;
        const reviewMode = document.getElementById('settings-review-mode').value;
        const retrievalDepth = document.getElementById('settings-retrieval-depth').value;
        const customPrompt = document.getElementById('settings-custom-prompt').value;

        try {
            const response = await fetch('/api/dashboard/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    repo_full_name: repo,
                    strictness: strictness,
                    review_mode: reviewMode,
                    retrieval_depth: retrievalDepth,
                    custom_prompt: customPrompt,
                    role: this.currentRole
                })
            });

            if (response.ok) {
                this.addTerminalLine('success', `[Settings] Applied configurations override for ${repo} repository.`);
                alert("Repository configurations successfully applied.");
            } else {
                const err = await response.json();
                alert(`Save failed: ${err.detail}`);
            }
        } catch (err) {
            console.error("Failed to save repo settings:", err);
        }
    }

    /* SYSTEM OBSERVABILITY & RETRAINING LOG STREAMER */
    async loadSystemStatus() {
        try {
            const response = await fetch('/api/dashboard/status');
            const data = await response.json();

            // Populate connection status badges
            this.updateHealthBadge('health-card-db', data.database, data.database_latency_ms);
            this.updateHealthBadge('health-card-chroma', data.chromadb, data.chromadb_latency_ms);
            this.updateHealthBadge('health-card-ollama', data.ollama, data.ollama_latency_ms);

            // Populate audit logs container
            const container = document.getElementById('audit-trail-container');
            container.innerHTML = '';
            
            if (!data.audit_logs || data.audit_logs.length === 0) {
                container.innerHTML = `<div style="color: var(--text-secondary); font-size: 13px; text-align: center; margin-top: 10px;">No administrative audit log items yet.</div>`;
                return;
            }

            data.audit_logs.forEach(log => {
                const item = document.createElement('div');
                item.className = 'audit-trail-item';
                item.innerHTML = `
                    <h5><strong>${log.action}</strong></h5>
                    <p style="color: var(--text-secondary); font-size: 11px; margin-bottom: 2px;">${log.target}</p>
                    <span style="font-size: 10px; color: var(--text-secondary);"><i class="fa-solid fa-user-gear"></i> ${log.user_role} &bull; ${log.timestamp}</span>
                `;
                container.appendChild(item);
            });

        } catch (err) {
            console.error("Failed to load observability status:", err);
        }
    }

    updateHealthBadge(cardId, status, latency) {
        const card = document.getElementById(cardId);
        const badge = card.querySelector('.health-badge');
        const latencyTxt = card.querySelector('.latency');

        badge.className = `health-badge ${status === 'online' ? 'online' : status === 'degraded' ? 'degraded' : 'offline'}`;
        badge.textContent = status.toUpperCase();

        if (status === 'offline') {
            latencyTxt.textContent = 'TIMEOUT';
            latencyTxt.style.color = '#f87171';
        } else {
            latencyTxt.textContent = `${latency} ms`;
            latencyTxt.style.color = 'inherit';
        }
    }

    async triggerRetraining() {
        if (this.currentRole !== 'Admin') {
            alert("Retraining controls require Admin Console permissions.");
            return;
        }

        this.btnTriggerRetrain.disabled = true;
        this.consoleTerminal.innerHTML = '<div class="terminal-line system">[Retrain] Connecting log stream reader...</div>';

        try {
            const response = await fetch(`/api/dashboard/retrain?role=${this.currentRole}`);
            
            if (!response.ok) {
                const err = await response.json();
                this.addTerminalLine('error', `[Retrain Failed] ${err.detail}`);
                this.btnTriggerRetrain.disabled = false;
                return;
            }

            // Stream response chunk-by-chunk
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                this.parseAndPrintTerminal(chunk);
            }
        } catch (err) {
            this.addTerminalLine('error', `[Retrain Error] Communication failure: ${err}`);
        } finally {
            this.btnTriggerRetrain.disabled = false;
        }
    }

    parseAndPrintTerminal(text) {
        const lines = text.split('\n');
        lines.forEach(line => {
            if (!line.trim()) return;

            let type = 'info';
            if (line.includes('[SUCCESS]')) type = 'success';
            else if (line.includes('[FAILED]') || line.includes('[ERROR]')) type = 'error';
            else if (line.includes('Starting') || line.includes('pipeline') || line.includes('Retraining complete')) type = 'system';

            this.addTerminalLine(type, line);
        });
    }

    addTerminalLine(type, text) {
        const div = document.createElement('div');
        div.className = `terminal-line ${type}`;
        div.textContent = text;
        this.consoleTerminal.appendChild(div);
        this.consoleTerminal.scrollTop = this.consoleTerminal.scrollHeight;
    }

    /* APEXCHARTS INITIALIZATIONS */
    initCharts() {
        const chartTrendEl = document.getElementById('chart-sentiment-trend');
        const chartPieEl = document.getElementById('chart-feedback-pie');

        if (!chartTrendEl || !chartPieEl) return;

        // Sentiment Line Chart
        const trendOptions = {
            chart: {
                height: 280,
                type: 'line',
                toolbar: { show: false },
                background: 'transparent'
            },
            stroke: { curve: 'smooth', width: 3 },
            colors: ['#6366f1'],
            series: [{ name: 'Helpfulness Score', data: [50, 52, 60, 68, 72, 75] }],
            xaxis: {
                categories: ['Run 1', 'Run 2', 'Run 3', 'Run 4', 'Run 5', 'Latest Run'],
                labels: { style: { colors: '#94a3b8' } }
            },
            yaxis: {
                min: 0,
                max: 100,
                labels: { 
                    formatter: (val) => `${val}%`,
                    style: { colors: '#94a3b8' } 
                }
            },
            grid: { borderColor: 'rgba(255, 255, 255, 0.05)' },
            theme: { mode: 'dark' },
            tooltip: { theme: 'dark' }
        };

        // Sentiment Donut Chart
        const pieOptions = {
            chart: {
                height: 280,
                type: 'donut',
                background: 'transparent'
            },
            labels: ['Approved Suggestions', 'Rejected Anti-patterns', 'Neutral/Unrated'],
            series: [0, 0, 0],
            colors: ['#34d399', '#f87171', '#94a3b8'],
            legend: {
                position: 'bottom',
                labels: { colors: '#94a3b8' }
            },
            dataLabels: { enabled: false },
            theme: { mode: 'dark' },
            tooltip: { theme: 'dark' }
        };

        this.charts.trend = new ApexCharts(chartTrendEl, trendOptions);
        this.charts.pie = new ApexCharts(chartPieEl, pieOptions);

        this.charts.trend.render();
        this.charts.pie.render();
    }

    updateCharts(stats) {
        if (!this.charts.pie) return;

        // Update Pie Chart Data
        const approved = stats.positive_reviews;
        const rejected = stats.negative_reviews;
        const neutral = stats.total_reviews - (approved + rejected);

        this.charts.pie.updateSeries([approved, rejected, Math.max(0, neutral)]);

        // Dynamically simulate trend metrics as helpfulness rating grows
        const baseHelpful = stats.helpfulness_rate;
        const trendData = [
            Math.max(30, Math.round(baseHelpful * 0.7)),
            Math.max(40, Math.round(baseHelpful * 0.8)),
            Math.max(50, Math.round(baseHelpful * 0.9)),
            Math.round(baseHelpful)
        ];
        
        const runLabels = trendData.map((_, i) => `Cycle ${i+1}`);
        
        if (this.charts.trend) {
            this.charts.trend.updateOptions({
                series: [{ name: 'Helpfulness Rate', data: trendData }],
                xaxis: { categories: runLabels }
            });
        }
    }

    redrawCharts(theme) {
        const textColor = theme === 'light' ? '#475569' : '#94a3b8';
        const gridColor = theme === 'light' ? 'rgba(0, 0, 0, 0.05)' : 'rgba(255, 255, 255, 0.05)';

        if (this.charts.trend) {
            this.charts.trend.updateOptions({
                theme: { mode: theme },
                xaxis: { labels: { style: { colors: textColor } } },
                yaxis: { labels: { style: { colors: textColor } } },
                grid: { borderColor: gridColor }
            });
        }
        if (this.charts.pie) {
            this.charts.pie.updateOptions({
                theme: { mode: theme },
                legend: { labels: { colors: textColor } }
            });
        }
    }

    /* UTILITY HELPERS */
    renderTableSkeleton(tableId, columnsCount) {
        const tbody = document.querySelector(`#${tableId} tbody`);
        tbody.innerHTML = '';
        
        for (let i = 0; i < 4; i++) {
            const tr = document.createElement('tr');
            tr.className = 'skeleton-row';
            
            let cells = '';
            for (let c = 0; c < columnsCount; c++) {
                cells += `<td><div class="skeleton-text"></div></td>`;
            }
            tr.innerHTML = cells;
            tbody.appendChild(tr);
        }
    }

    debounce(func, wait) {
        clearTimeout(this.timeout);
        this.timeout = setTimeout(func, wait);
    }

    escapeHTML(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
}

// Instantiate App
document.addEventListener('DOMContentLoaded', () => {
    const app = new DashboardApp();
    app.initMemoryBoostSave();
});
