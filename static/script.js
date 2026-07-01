document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    // ---------- Sidebar toggle ----------
    const sidebar = document.getElementById('sidebar');
    document.getElementById('toggle-sidebar').addEventListener('click', () => {
        sidebar.classList.toggle('hidden');
    });

    // ---------- Cell click ----------
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

    // ---------- WebSocket: bingo alert ----------
    socket.on('bingo', (data) => {
        showBingoMessage(data.message);
    });

    // ---------- WebSocket: progress update ----------
    socket.on('progress_update', (progressData) => {
        renderProgress(progressData);
    });

    // ---------- WebSocket: event list update ----------
    socket.on('event_changed', (events) => {
        renderAllEvents(events);
    });

    function showBingoMessage(msg) {
        const alertDiv = document.getElementById('bingo-message');
        alertDiv.textContent = msg;
        alertDiv.style.display = 'block';
        setTimeout(() => { alertDiv.style.display = 'none'; }, 8000);
    }

    // ---------- Progress rendering (unchanged) ----------
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

    // ---------- Events rendering (split by type) ----------
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
                <span class="${ev.is_active ? '' : 'inactive'}">${ev.text}</span>
                ${isAdmin ? '<button class="delete-event-btn" data-id="'+ev.id+'">🗑️</button>' : ''}
            `;
            container.appendChild(div);
        });
        // Attach delete handlers
        container.querySelectorAll('.delete-event-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const eventId = btn.dataset.id;
                const res = await fetch('/api/events/' + eventId, { method: 'DELETE' });
                if (!res.ok) alert('Erreur suppression');
            });
        });
    }

    // ---------- Collapsible logic ----------
    document.querySelectorAll('.collapsible-header').forEach(header => {
        header.addEventListener('click', () => {
            const targetId = header.dataset.target;
            const body = document.getElementById(targetId);
            header.classList.toggle('open');
            body.classList.toggle('open');
        });
    });

    // ---------- Events rendering (with inline editing) ----------
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
            ${isAdmin ? '<button class="delete-event-btn" data-id="'+ev.id+'">🗑️</button>' : ''}
        `;
        container.appendChild(div);
    });

    // Attach inline editing to event texts
    container.querySelectorAll('.event-text').forEach(span => {
        span.addEventListener('click', function(e) {
            if (this.classList.contains('editing')) return; // already editing
            const eventId = this.dataset.eventId;
            const originalText = this.textContent;
            const input = document.createElement('input');
            input.type = 'text';
            input.value = originalText;
            input.className = 'edit-event-input';
            input.style.width = '100%';
            // Replace span with input
            this.replaceWith(input);
            input.focus();
            input.select();

            // Save on Enter or blur
            const save = async () => {
                const newText = input.value.trim();
                if (newText === originalText) {
                    // No change, revert to span
                    input.replaceWith(span);
                    return;
                }
                // Send update (PUT with text; server will delete if empty)
                const res = await fetch(`/api/events/${eventId}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ text: newText })
                });
                // List will be refreshed via socket 'event_changed'
            };

            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    input.blur();
                }
            });
            input.addEventListener('blur', save);
        });
    });

    // Delete button (admin only) – unchanged
    container.querySelectorAll('.delete-event-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const eventId = btn.dataset.id;
            const res = await fetch(`/api/events/${eventId}`, { method: 'DELETE' });
            if (!res.ok) alert('Erreur suppression');
        });
    });
}

    // ---------- Admin status ----------
    const isAdmin = document.body.dataset.isAdmin === 'true';

    // ---------- Initial data load ----------
    fetch('/api/progress').then(res => res.json()).then(renderProgress);
    fetch('/api/events').then(res => res.json()).then(renderAllEvents);
});