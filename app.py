import os
import random
from datetime import datetime, date, timedelta
import pytz

from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Event, Grid, GridCell, BingoWin

# ---------- App initialization ----------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'postgresql://bingo:bingo@db:5432/bingo'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()
    # Seed events if the table is empty
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

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

FRANCE_TZ = pytz.timezone('Europe/Paris')

# ---------- Login manager ----------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------- Helper functions ----------
def get_now_paris():
    """Return current datetime in Paris timezone."""
    return datetime.now(FRANCE_TZ)

def get_monday(date_obj):
    """Return the Monday of the week for a given date."""
    return date_obj - timedelta(days=date_obj.weekday())

def generate_grid(user, grid_type):
    """
    Generate a 5x5 grid for the given user and type.
    Picks 25 events (with replacement if pool < 25).
    """
    # Get active events of the required type
    events = Event.query.filter_by(event_type=grid_type, is_active=True).all()
    if not events:
        # Fallback: if no active events, use all events of that type (including inactive)
        events = Event.query.filter_by(event_type=grid_type).all()
    # If still empty, raise error (should not happen after seeding)
    if not events:
        raise ValueError(f"Aucun événement disponible pour le type {grid_type}")

    # Sample 25 events, allowing duplicates if pool size < 25
    chosen_events = random.choices(events, k=25) if len(events) < 25 else random.sample(events, 25)

    # Create grid
    now = get_now_paris()
    grid = Grid(
        user_id=user.id,
        grid_type=grid_type,
        created_at=now,
        week_start=get_monday(now.date()) if grid_type == 'weekly' else None
    )
    db.session.add(grid)
    db.session.flush()  # get grid.id

    # Create cells (5x5)
    idx = 0
    for row in range(5):
        for col in range(5):
            cell = GridCell(
                grid_id=grid.id,
                row=row,
                col=col,
                event_id=chosen_events[idx].id,
                checked=False
            )
            db.session.add(cell)
            idx += 1

    db.session.commit()
    return grid

def get_or_create_grid(user, grid_type):
    """
    Return the current grid for the user and type.
    For daily: grid created today. For weekly: grid for current week (Monday).
    If none exists, generate a new one.
    """
    now = get_now_paris()
    if grid_type == 'daily':
        today = now.date()
        grid = Grid.query.filter(
            Grid.user_id == user.id,
            Grid.grid_type == 'daily',
            db.func.date(Grid.created_at) == today
        ).first()
    else:  # weekly
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
    """
    Check if the grid has any complete row, column or diagonal.
    Returns a list of bingo types detected (that haven't been recorded yet).
    Records wins in DB.
    """
    cells = GridCell.query.filter_by(grid_id=grid.id).order_by(GridCell.row, GridCell.col).all()
    # Build a 5x5 matrix of checked status
    matrix = [[False]*5 for _ in range(5)]
    for cell in cells:
        matrix[cell.row][cell.col] = cell.checked

    wins_found = []

    # Rows
    for r in range(5):
        if all(matrix[r][c] for c in range(5)):
            wins_found.append(f'row_{r}')
    # Columns
    for c in range(5):
        if all(matrix[r][c] for r in range(5)):
            wins_found.append(f'col_{c}')
    # Diagonals
    if all(matrix[i][i] for i in range(5)):
        wins_found.append('diag_main')
    if all(matrix[i][4-i] for i in range(5)):
        wins_found.append('diag_anti')

    # Record only new bingo types for this grid
    existing_wins = {w.bingo_type for w in BingoWin.query.filter_by(grid_id=grid.id).all()}
    new_bingos = [b for b in wins_found if b not in existing_wins]

    for bingo_type in new_bingos:
        win = BingoWin(
            user_id=grid.user_id,
            grid_id=grid.id,
            bingo_type=bingo_type
        )
        db.session.add(win)
    if new_bingos:
        db.session.commit()
    return new_bingos

# ---------- Routes ----------
@app.route('/')
def index():
    """Redirect to bingo page or login."""
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
                # Auto-create user – first user becomes admin
                is_admin = (User.query.first() is None)
                user = User(username=username, is_admin=is_admin)
                db.session.add(user)
                db.session.commit()
                if is_admin:
                    flash("Vous êtes le premier utilisateur et avez été défini comme administrateur.", "info")
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
    """Main bingo page showing both grids."""
    daily_grid = get_or_create_grid(current_user, 'daily')
    weekly_grid = get_or_create_grid(current_user, 'weekly')

    # Build cell data for templates
    daily_cells = GridCell.query.filter_by(grid_id=daily_grid.id).order_by(GridCell.row, GridCell.col).all()
    weekly_cells = GridCell.query.filter_by(grid_id=weekly_grid.id).order_by(GridCell.row, GridCell.col).all()

    # Get all users for sidebar progress
    users = User.query.all()
    progress = {}
    for u in users:
        d_grid = get_or_create_grid(u, 'daily')
        w_grid = get_or_create_grid(u, 'weekly')
        progress[u.username] = {
            'daily_checked': GridCell.query.filter_by(grid_id=d_grid.id, checked=True).count(),
            'weekly_checked': GridCell.query.filter_by(grid_id=w_grid.id, checked=True).count(),
            'daily_total': 25,
            'weekly_total': 25
        }

    return render_template(
        'bingo.html',
        daily_grid=daily_grid,
        weekly_grid=weekly_grid,
        daily_cells=daily_cells,
        weekly_cells=weekly_cells,
        progress=progress
    )

@app.route('/api/toggle_cell', methods=['POST'])
@login_required
def toggle_cell():
    """Toggle the checked state of a cell and check for bingo."""
    data = request.get_json()
    cell_id = data.get('cell_id')
    cell = GridCell.query.get(cell_id)
    if not cell or cell.grid.user_id != current_user.id:
        return jsonify({'error': 'Cellule invalide'}), 403

    cell.checked = not cell.checked
    db.session.commit()

    # After toggling, check for bingo on the parent grid
    grid = cell.grid
    new_bingos = check_bingo(grid)
    bingo_message = None
    if new_bingos:
        bingo_message = f"{current_user.username} a un BINGO ({grid.grid_type}) !"
        # You could also broadcast this via WebSocket – here we rely on polling

    return jsonify({
        'checked': cell.checked,
        'bingo_message': bingo_message
    })

@app.route('/api/bingo_wins')
@login_required
def bingo_wins():
    """Return recent bingo wins (from the last 24h) for polling."""
    since = get_now_paris() - timedelta(hours=24)
    wins = BingoWin.query.filter(BingoWin.timestamp >= since).order_by(BingoWin.timestamp.desc()).limit(20).all()
    result = []
    for w in wins:
        result.append({
            'username': w.user.username,
            'grid_type': w.grid.grid_type,
            'bingo_type': w.bingo_type,
            'timestamp': w.timestamp.strftime('%H:%M:%S')
        })
    return jsonify(result)

@app.route('/api/progress')
@login_required
def api_progress():
    """Return progress for all users (checked slots)."""
    users = User.query.all()
    progress = {}
    for u in users:
        d_grid = get_or_create_grid(u, 'daily')
        w_grid = get_or_create_grid(u, 'weekly')
        progress[u.username] = {
            'daily_checked': GridCell.query.filter_by(grid_id=d_grid.id, checked=True).count(),
            'weekly_checked': GridCell.query.filter_by(grid_id=w_grid.id, checked=True).count(),
        }
    return jsonify(progress)

# Admin panel
@app.route('/api/events', methods=['GET'])
@login_required
def get_events():
    """Return all events (admin only)."""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin only'}), 403
    events = Event.query.all()
    return jsonify([{'id': e.id, 'text': e.text, 'event_type': e.event_type, 'is_active': e.is_active} for e in events])

@app.route('/api/events', methods=['POST'])
@login_required
def add_event():
    """Add a new event (admin only)."""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin only'}), 403
    data = request.get_json()
    event = Event(
        text=data['text'],
        event_type=data['event_type'],
        is_active=data.get('is_active', True)
    )
    db.session.add(event)
    db.session.commit()
    return jsonify({'id': event.id})

@app.route('/api/events/<int:event_id>', methods=['PUT'])
@login_required
def update_event(event_id):
    """Update event text or active status (admin only)."""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin only'}), 403
    event = Event.query.get_or_404(event_id)
    data = request.get_json()
    if 'text' in data:
        event.text = data['text']
    if 'event_type' in data:
        event.event_type = data['event_type']
    if 'is_active' in data:
        event.is_active = data['is_active']
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/events/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    """Delete an event (admin only)."""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin only'}), 403
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)