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

    // ---------- Add event (button + Enter key) ----------
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
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const type = input.dataset.type;
                addEvent(type, input);
            }
        });
    });

    // ---------- Admin status ----------
    const isAdmin = document.body.dataset.isAdmin === 'true';

    // ---------- Initial data load ----------
    fetch('/api/progress').then(res => res.json()).then(renderProgress);
    fetch('/api/events').then(res => res.json()).then(renderAllEvents);
});