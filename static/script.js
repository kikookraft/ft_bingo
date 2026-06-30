document.addEventListener('DOMContentLoaded', () => {
    // ---------- Sidebar toggle ----------
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('toggle-sidebar');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('hidden');
        });
    }

    // ---------- Admin button visibility ----------
    // (Set by template: if user is admin, button should be shown. We'll handle via a global variable.)
    fetch('/api/progress').then(() => {
        // We can't detect admin directly, but we'll set a data attribute on body from template.
        // For simplicity, we'll add a hidden input in bingo.html with is_admin.
    });

    // ---------- Cell toggle ----------
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
            if (data.bingo_message) {
                showBingoMessage(data.bingo_message);
            }
            updateProgress();
        });
    });

    // ---------- Polling for bingo wins ----------
    setInterval(checkBingoWins, 5000);
    async function checkBingoWins() {
        const res = await fetch('/api/bingo_wins');
        const wins = await res.json();
        if (wins.length > 0) {
            const lastWin = wins[0];
            const lastShown = sessionStorage.getItem('lastBingoId');
            if (lastShown !== String(lastWin.timestamp)) {
                showBingoMessage(`${lastWin.username} a BINGO (${lastWin.grid_type}) !`);
                sessionStorage.setItem('lastBingoId', lastWin.timestamp);
            }
        }
    }

    function showBingoMessage(msg) {
        const alertDiv = document.getElementById('bingo-message');
        alertDiv.textContent = msg;
        alertDiv.style.display = 'block';
        setTimeout(() => { alertDiv.style.display = 'none'; }, 8000);
    }

    // ---------- Progress sidebar ----------
    function updateProgress() {
        fetch('/api/progress')
            .then(res => res.json())
            .then(data => {
                const list = document.getElementById('progress-list');
                list.innerHTML = '';
                for (const [username, counts] of Object.entries(data)) {
                    const totalDaily = 25, totalWeekly = 25;
                    const dailyPct = (counts.daily_checked / totalDaily * 100).toFixed(0);
                    const weeklyPct = (counts.weekly_checked / totalWeekly * 100).toFixed(0);
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <strong>${username}</strong>
                        <div>Jour: ${counts.daily_checked}/25</div>
                        <div class="progress-bar"><div class="progress-fill" style="width:${dailyPct}%"></div></div>
                        <div>Semaine: ${counts.weekly_checked}/25</div>
                        <div class="progress-bar"><div class="progress-fill" style="width:${weeklyPct}%"></div></div>
                    `;
                    list.appendChild(li);
                }
            });
    }
    updateProgress(); // initial load

    // ---------- Admin modal ----------
    // We'll check if current user is admin by looking at a hidden element in the template.
    const isAdmin = document.body.dataset.isAdmin === 'true';
    if (isAdmin) {
        document.getElementById('admin-btn').style.display = 'inline-block';
        const adminBtn = document.getElementById('admin-btn');
        const modal = document.getElementById('admin-modal');
        const closeModal = modal.querySelector('.close');

        adminBtn.addEventListener('click', () => {
            modal.style.display = 'block';
            loadEvents();
        });
        closeModal.addEventListener('click', () => modal.style.display = 'none');
        window.addEventListener('click', (e) => {
            if (e.target === modal) modal.style.display = 'none';
        });

        async function loadEvents() {
            const res = await fetch('/api/events');
            const events = await res.json();
            const list = document.getElementById('event-list');
            list.innerHTML = events.map(e => `
                <div class="event-item" data-id="${e.id}">
                    <span class="${e.is_active ? '' : 'inactive'}">${e.text} (${e.event_type})</span>
                    <button class="edit-event">✏️</button>
                    <button class="delete-event">🗑️</button>
                </div>
            `).join('');
            // Attach edit/delete handlers...
        }

        document.getElementById('add-event-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const text = document.getElementById('new-event-text').value.trim();
            const type = document.getElementById('new-event-type').value;
            if (!text) return;
            await fetch('/api/events', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text, event_type: type, is_active: true})
            });
            document.getElementById('new-event-text').value = '';
            loadEvents();
        });
    }
});

// Add data attribute for admin in bingo.html: <body data-is-admin="{{ 'true' if current_user.is_admin else 'false' }}">
// We'll modify the template to include that.