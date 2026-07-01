import os
import random
from datetime import datetime, date, timedelta
import pytz

import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit
from models import db, User, Event, Grid, GridCell, BingoWin

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'postgresql://bingo:bingo@db:5432/bingo'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

FRANCE_TZ = pytz.timezone('Europe/Paris')

@app.cli.command('export-events')
def export_events():
    """Export all events as a JSON file."""
    import json
    events = Event.query.all()
    data = [{'text': e.text, 'event_type': e.event_type, 'is_active': e.is_active} for e in events]
    # Write to a file inside the container (mounted volume later)
    with open('events_export.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"{len(data)} événements exportés dans events_export.json")

# ---------- Auto‑seed ----------
with app.app_context():
    db.create_all()
    if Event.query.count() == 0:
        daily_events = [
            "discussion caca", "projet KO", "discusion canibalisme",
            "gagner un point d'eval", "crash son pc (non voulu)",
            "avancer son cursus (1 commit min)", "bus avec +10min de retard",
            "se prendre un skill issue", "a bu l'entièreté de sa gourde",
            "valider un nouveau poste", '"et c\'est ok!"', "mentionner factorio",
            '"my bad"', '"bingo !"', '"j\'en ai marre de ce projet"',
            '"utilise HL vpn"', "Tomy arrive avant 10h30 (groupe)",
            "le groupe a commandé + de Croc que de wrap",
            "le groupe a commandé + de wrap que de Croc",
            "on apprend une dinguerie sur un politicien",
            "fuite de données sur un site français",
            "discussion kink", "baptiste perd aux échecs",
            '"Bonjour tout le monde" de cdutel', "claquette perdue"
        ]
        weekly_events = [
            "foyers ouvert", "gildas est venu", "pluie",
            "win bingo dans la semaine", "intra down", "annonce bocal",
            "alternants présents", "validation de projet (groupe)",
            "oubbli d'object en cluster (groupe)", "quota github atteint",
            "exam réussi (groupe)", "voir une biche", "bouffe gratuite",
            "graille vide", "cours de réseau de Raph",
            "cours de physique d'Astrale", "mention ECS",
            "fourchette disparaît", "le pchit de nettoyage a disparut",
            "toilette cassé/sale", "croc nutella",
            "erreur de commande au foyer (groupe)", "utilisation /educate",
            "a perdu 4h de logtime (confiance--)",
            "gros down d'un site internet", "plainte frigo pas propre",
            "coupure elec", "on enttend alarme incendie"
        ]
        for text in daily_events:
            db.session.add(Event(text=text, event_type='daily'))
        for text in weekly_events:
            db.session.add(Event(text=text, event_type='weekly'))
        db.session.commit()

# ---------- Login manager ----------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------- Helpers ----------
def get_now_paris():
    return datetime.now(FRANCE_TZ)

def get_monday(date_obj):
    return date_obj - timedelta(days=date_obj.weekday())

def generate_grid(user, grid_type):
    events = Event.query.filter_by(event_type=grid_type, is_active=True).all()
    if not events:
        events = Event.query.filter_by(event_type=grid_type).all()
    if not events:
        raise ValueError(f"Aucun événement disponible pour le type {grid_type}")
    chosen_events = random.choices(events, k=25) if len(events) < 25 else random.sample(events, 25)
    now = get_now_paris()
    grid = Grid(
        user_id=user.id,
        grid_type=grid_type,
        created_at=now,
        week_start=get_monday(now.date()) if grid_type == 'weekly' else None
    )
    db.session.add(grid)
    db.session.flush()
    idx = 0
    for row in range(5):
        for col in range(5):
            cell = GridCell(grid_id=grid.id, row=row, col=col,
                            event_id=chosen_events[idx].id, checked=False)
            db.session.add(cell)
            idx += 1
    db.session.commit()
    return grid

def get_or_create_grid(user, grid_type):
    now = get_now_paris()
    if grid_type == 'daily':
        today = now.date()
        grid = Grid.query.filter(
            Grid.user_id == user.id,
            Grid.grid_type == 'daily',
            db.func.date(Grid.created_at) == today
        ).first()
    else:
        monday = get_monday(now.date())
        grid = Grid.query.filter(
            Grid.user_id == user.id,
            Grid.grid_type == 'weekly',
            Grid.week_start == monday
        ).first()
    if grid is None:
        grid = generate_grid(user, grid_type)
    return grid

def check_bingo(grid):
    cells = GridCell.query.filter_by(grid_id=grid.id).order_by(GridCell.row, GridCell.col).all()
    matrix = [[False]*5 for _ in range(5)]
    for cell in cells:
        matrix[cell.row][cell.col] = cell.checked
    wins_found = []
    for r in range(5):
        if all(matrix[r][c] for c in range(5)):
            wins_found.append(f'row_{r}')
    for c in range(5):
        if all(matrix[r][c] for r in range(5)):
            wins_found.append(f'col_{c}')
    if all(matrix[i][i] for i in range(5)):
        wins_found.append('diag_main')
    if all(matrix[i][4-i] for i in range(5)):
        wins_found.append('diag_anti')
    existing_wins = {w.bingo_type for w in BingoWin.query.filter_by(grid_id=grid.id).all()}
    new_bingos = [b for b in wins_found if b not in existing_wins]
    for bingo_type in new_bingos:
        win = BingoWin(user_id=grid.user_id, grid_id=grid.id, bingo_type=bingo_type)
        db.session.add(win)
    if new_bingos:
        db.session.commit()
    return new_bingos

def user_has_bingo(user, grid_type):
    grid = get_or_create_grid(user, grid_type)
    return BingoWin.query.filter_by(grid_id=grid.id).first() is not None

# ---------- Routes ----------
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('bingo'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('bingo'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        if not username:
            error = "Veuillez entrer un nom d'utilisateur."
        else:
            user = User.query.filter_by(username=username).first()
            if user is None:
                user = User(username=username)
                db.session.add(user)
                db.session.commit()
            login_user(user)
            return redirect(url_for('bingo'))
    return render_template('login.html', error=error)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/bingo')
@login_required
def bingo():
    daily_grid = get_or_create_grid(current_user, 'daily')
    weekly_grid = get_or_create_grid(current_user, 'weekly')
    daily_cells = GridCell.query.filter_by(grid_id=daily_grid.id).order_by(GridCell.row, GridCell.col).all()
    weekly_cells = GridCell.query.filter_by(grid_id=weekly_grid.id).order_by(GridCell.row, GridCell.col).all()

    users = User.query.all()
    progress = {}
    for u in users:
        progress[u.username] = {
            'daily_checked': GridCell.query.filter_by(grid_id=get_or_create_grid(u, 'daily').id, checked=True).count(),
            'weekly_checked': GridCell.query.filter_by(grid_id=get_or_create_grid(u, 'weekly').id, checked=True).count(),
            'daily_bingo': user_has_bingo(u, 'daily'),
            'weekly_bingo': user_has_bingo(u, 'weekly'),
        }
    return render_template('bingo.html',
                           daily_grid=daily_grid, weekly_grid=weekly_grid,
                           daily_cells=daily_cells, weekly_cells=weekly_cells,
                           progress=progress)

@app.route('/api/toggle_cell', methods=['POST'])
@login_required
def toggle_cell():
    data = request.get_json()
    cell_id = data.get('cell_id')
    cell = GridCell.query.get(cell_id)
    if not cell or cell.grid.user_id != current_user.id:
        return jsonify({'error': 'Cellule invalide'}), 403
    cell.checked = not cell.checked
    db.session.commit()
    new_bingos = check_bingo(cell.grid)
    bingo_message = None
    if new_bingos:
        bingo_message = f"{current_user.username} a un BINGO ({cell.grid.grid_type}) !"
        socketio.emit('bingo', {
            'username': current_user.username,
            'grid_type': cell.grid.grid_type,
            'message': bingo_message
        })
        socketio.emit('progress_update', get_progress_data())
    return jsonify({'checked': cell.checked, 'bingo_message': bingo_message})

# ---------- Progress ----------
def get_progress_data():
    users = User.query.all()
    progress = {}
    for u in users:
        d_grid = get_or_create_grid(u, 'daily')
        w_grid = get_or_create_grid(u, 'weekly')
        progress[u.username] = {
            'daily_checked': GridCell.query.filter_by(grid_id=d_grid.id, checked=True).count(),
            'weekly_checked': GridCell.query.filter_by(grid_id=w_grid.id, checked=True).count(),
            'daily_bingo': user_has_bingo(u, 'daily'),
            'weekly_bingo': user_has_bingo(u, 'weekly'),
        }
    return progress

@app.route('/api/progress')
@login_required
def api_progress():
    return jsonify(get_progress_data())

# ---------- Events (sorted) ----------
def get_events_list():
    return [{'id': e.id, 'text': e.text, 'event_type': e.event_type, 'is_active': e.is_active}
            for e in Event.query.order_by(Event.text).all()]

@app.route('/api/events', methods=['GET'])
@login_required
def get_events():
    return jsonify(get_events_list())

@app.route('/api/events', methods=['POST'])
@login_required
def add_event():
    data = request.get_json()
    new_event = Event(
        text=data['text'],
        event_type=data['event_type'],
        is_active=data.get('is_active', True)
    )
    db.session.add(new_event)
    db.session.commit()
    socketio.emit('event_changed', get_events_list())
    return jsonify({'id': new_event.id})

@app.route('/api/events/<int:event_id>', methods=['PUT'])
@login_required
def update_event(event_id):
    event = Event.query.get_or_404(event_id)
    data = request.get_json()
    new_text = data.get('text', '').strip()
    if new_text == '':
        # Delete the event
        affected_users = delete_event_and_regenerate(event)
        socketio.emit('event_changed', get_events_list())
        # Notify affected clients to reload their grids
        for user_id in affected_users:
            socketio.emit('grid_regenerated', {'user_id': user_id}, room=f'user_{user_id}')
        return jsonify({'success': True, 'deleted': True})
    event.text = new_text
    db.session.commit()
    socketio.emit('event_changed', get_events_list())
    return jsonify({'success': True})

@app.route('/api/events/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    affected_users = delete_event_and_regenerate(event)
    socketio.emit('event_changed', get_events_list())
    for user_id in affected_users:
        socketio.emit('grid_regenerated', {'user_id': user_id}, room=f'user_{user_id}')
    return jsonify({'success': True})

def delete_event_and_regenerate(event):
    """Delete event and regenerate current grids that used it. Returns list of affected user IDs."""
    # Find all grids that are current (daily for today, weekly for current week)
    now = get_now_paris()
    today = now.date()
    monday = get_monday(today)

    # Grids that contain this event
    cells = GridCell.query.filter_by(event_id=event.id).all()
    affected_users = set()
    grids_to_regen = []
    for cell in cells:
        grid = cell.grid
        # Check if grid is current
        if grid.grid_type == 'daily' and grid.created_at.date() == today:
            grids_to_regen.append(grid)
            affected_users.add(grid.user_id)
        elif grid.grid_type == 'weekly' and grid.week_start == monday:
            grids_to_regen.append(grid)
            affected_users.add(grid.user_id)

    # Delete the event (cascading? No cascade on event, so we must delete cells first, or handle)
    # First delete the GridCells referencing this event for the current grids, then delete the grids and recreate.
    # Actually, we can just delete the grids, which cascade-deletes cells, then regenerate.
    for grid in grids_to_regen:
        db.session.delete(grid)
    # Delete the event itself
    db.session.delete(event)
    db.session.commit()

    # Regenerate grids for affected users
    for user_id in affected_users:
        user = User.query.get(user_id)
        # Determine which grid type(s) were affected
        # For simplicity, we regenerate both types if the event type matches? But we only deleted grids of the same type. We'll loop through affected types.
        # We'll just re-create daily if any daily was deleted, etc.
        # Approach: for each grid we deleted, regenerate that type for that user.
        # Since we lost the type info, we re-evaluate: we know the event type, so only grids of that type could have been affected.
        event_type = event.event_type
        # We'll regenerate the matching type for each affected user. But a user may have had multiple grids? Only one per type per period.
        # So just call get_or_create_grid for that user and that event_type, which will create a new one.
        get_or_create_grid(user, event_type)
    db.session.commit()
    return list(affected_users)

# ---------- SocketIO ----------
@socketio.on('connect')
def handle_connect():
    # Join user-specific room for targeted updates
    if current_user.is_authenticated:
        room = f'user_{current_user.id}'
        join_room(room)

@socketio.on('disconnect')
def handle_disconnect():
    pass

# ---------- Grid retrieval for client ----------
@app.route('/api/grid/<grid_type>')
@login_required
def get_grid(grid_type):
    if grid_type not in ('daily', 'weekly'):
        return jsonify({'error': 'Invalid grid type'}), 400
    grid = get_or_create_grid(current_user, grid_type)
    cells = GridCell.query.filter_by(grid_id=grid.id).order_by(GridCell.row, GridCell.col).all()
    return jsonify({
        'grid_id': grid.id,
        'cells': [{'id': c.id, 'row': c.row, 'col': c.col,
                   'event_text': c.event.text, 'checked': c.checked} for c in cells]
    })

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5042, debug=False, use_reloader=False)