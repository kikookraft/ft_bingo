document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    // ---------- Sidebar ----------
    const sidebar = document.getElementById('sidebar');
    document.getElementById('toggle-sidebar').addEventListener('click', () => {
        sidebar.classList.toggle('hidden');
    });

    // ---------- Cell clicks ----------
    document.querySelectorAll('.bingo-cell').forEach(cell => {
        cell.addEventListener('click', async () => {
            const cellId = cell.dataset.cellId;
            const response = await fetch('/api/toggle_cell', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({cell_id: cellId})
            });
            const data = await response.json();
            if (data.checked !== undefined) {
                cell.classList.toggle('checked', data.checked);
            }
        });
    });

    // ---------- WebSocket events ----------
    socket.on('bingo', (data) => showBingoMessage(data.message));
    socket.on('progress_update', (data) => renderProgress(data));
    socket.on('event_changed', (events) => renderAllEvents(events));
    socket.on('grid_regenerated', (data) => {
        // If the regenerated grid belongs to the current user, reload that grid
        if (data.user_id === currentUserId) {
            reloadGrids();
        }
    });

    let currentUserId = null;
    // Get current user id from a hidden meta tag (we'll add it to base.html)
    const userIdMeta = document.querySelector('meta[name="user-id"]');
    if (userIdMeta) currentUserId = parseInt(userIdMeta.content);

    function showBingoMessage(msg) {
        const alertDiv = document.getElementById('bingo-message');
        alertDiv.textContent = msg;
        alertDiv.style.display = 'block';
        setTimeout(() => { alertDiv.style.display = 'none'; }, 8000);
    }

    // ---------- Progress ----------
    function renderProgress(progress) {
        const list = document.getElementById('progress-list');
        list.innerHTML = '';
        for (const [username, data] of Object.entries(progress)) {
            const dailyPct = (data.daily_checked / 25 * 100).toFixed(0);
            const weeklyPct = (data.weekly_checked / 25 * 100).toFixed(0);
            const dailyBingoClass = data.daily_bingo ? 'dot-bingo' : 'dot-no-bingo';
            const weeklyBingoClass = data.weekly_bingo ? 'dot-bingo' : 'dot-no-bingo';
            const li = document.createElement('li');
            li.innerHTML = `
                <strong>${username}</strong>
                <span class="bingo-dot ${dailyBingoClass}" title="Bingo journalier"></span>
                <span class="bingo-dot ${weeklyBingoClass}" title="Bingo hebdomadaire"></span>
                <div>Jour: ${data.daily_checked}/25</div>
                <div class="progress-bar"><div class="progress-fill" style="width:${dailyPct}%"></div></div>
                <div>Semaine: ${data.weekly_checked}/25</div>
                <div class="progress-bar"><div class="progress-fill" style="width:${weeklyPct}%"></div></div>
            `;
            list.appendChild(li);
        }
    }

    // ---------- Events lists ----------
    function renderAllEvents(events) {
        const dailyEvents = events.filter(e => e.event_type === 'daily');
        const weeklyEvents = events.filter(e => e.event_type === 'weekly');
        renderEventSublist('daily-events-list', dailyEvents);
        renderEventSublist('weekly-events-list', weeklyEvents);
    }

    function renderEventSublist(containerId, events) {
        const container = document.getElementById(containerId);
        container.innerHTML = '';
        events.forEach(ev => {
            const div = document.createElement('div');
            div.className = 'event-item';
            div.innerHTML = `
                <span class="event-text ${ev.is_active ? '' : 'inactive'}" data-event-id="${ev.id}" title="Cliquez pour éditer">${ev.text}</span>
                <button class="delete-event-btn" data-id="${ev.id}">🗑️</button>
            `;
            container.appendChild(div);
        });

        // Inline editing
        container.querySelectorAll('.event-text').forEach(span => {
            span.addEventListener('click', function(e) {
                if (this.classList.contains('editing')) return;
                const eventId = this.dataset.eventId;
                const originalText = this.textContent;
                const input = document.createElement('input');
                input.type = 'text';
                input.value = originalText;
                input.className = 'edit-event-input';
                input.style.width = '100%';
                this.replaceWith(input);
                input.focus();
                input.select();

                const save = async () => {
                    const newText = input.value.trim();
                    if (newText === originalText) {
                        input.replaceWith(span);
                        return;
                    }
                    await fetch(`/api/events/${eventId}`, {
                        method: 'PUT',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ text: newText })
                    });
                };
                input.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        input.blur();
                    }
                });
                input.addEventListener('blur', save);
            });
        });

        // Delete buttons (everyone)
        container.querySelectorAll('.delete-event-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const eventId = btn.dataset.id;
                await fetch(`/api/events/${eventId}`, { method: 'DELETE' });
            });
        });
    }

    // ---------- Add events (Enter works now) ----------
    function addEvent(type, inputElement) {
        const text = inputElement.value.trim();
        if (!text) return;
        fetch('/api/events', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text, event_type: type, is_active: true})
        }).then(res => {
            if (res.ok) inputElement.value = '';
        });
    }

    document.querySelectorAll('.add-event-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const type = btn.dataset.type;
            const input = document.querySelector(`.add-event-input[data-type="${type}"]`);
            addEvent(type, input);
        });
    });

    document.querySelectorAll('.add-event-input').forEach(input => {
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const type = input.dataset.type;
                addEvent(type, input);
            }
        });
    });

    // ---------- Collapsible menus ----------
    document.querySelectorAll('.collapsible-header').forEach(header => {
        header.addEventListener('click', () => {
            const targetId = header.dataset.target;
            const body = document.getElementById(targetId);
            header.classList.toggle('open');
            body.classList.toggle('open');
        });
    });

    // ---------- Reload grids after regeneration ----------
    async function reloadGrids() {
        for (const type of ['daily', 'weekly']) {
            const resp = await fetch(`/api/grid/${type}`);
            const data = await resp.json();
            if (data.cells) {
                const gridSection = document.querySelector(`.bingo-grid[data-grid-id="${data.grid_id}"]`);
                if (!gridSection) continue;
                gridSection.innerHTML = '';
                data.cells.forEach(cell => {
                    const div = document.createElement('div');
                    div.className = `bingo-cell ${cell.checked ? 'checked' : ''}`;
                    div.dataset.cellId = cell.id;
                    div.dataset.row = cell.row;
                    div.dataset.col = cell.col;
                    div.innerHTML = `<span class="cell-text">${cell.event_text}</span><span class="checkmark">✓</span>`;
                    div.addEventListener('click', cellClickHandler);
                    gridSection.appendChild(div);
                });
            }
        }
    }

    function cellClickHandler() {
        const cellId = this.dataset.cellId;
        fetch('/api/toggle_cell', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({cell_id: cellId})
        }).then(res => res.json()).then(data => {
            if (data.checked !== undefined) {
                this.classList.toggle('checked', data.checked);
            }
        });
    }

    // Initial load
    fetch('/api/progress').then(res => res.json()).then(renderProgress);
    fetch('/api/events').then(res => res.json()).then(renderAllEvents);
});