from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import pytz

db = SQLAlchemy()

# ---------- Users ----------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    # Relationships
    grids = db.relationship('Grid', back_populates='user', lazy='dynamic')
    wins = db.relationship('BingoWin', back_populates='user', lazy='dynamic')

    def get_id(self):
        return str(self.id)

# ---------- Events ----------
class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(255), nullable=False)
    event_type = db.Column(db.String(10), nullable=False)  # 'daily' or 'weekly'
    is_active = db.Column(db.Boolean, default=True)

# ---------- Grids ----------
class Grid(db.Model):
    __tablename__ = 'grids'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    grid_type = db.Column(db.String(10), nullable=False)   # 'daily' or 'weekly'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    week_start = db.Column(db.Date)  # used for weekly grids to know the Monday

    user = db.relationship('User', back_populates='grids')
    cells = db.relationship('GridCell', back_populates='grid', cascade='all, delete-orphan')
    wins = db.relationship('BingoWin', back_populates='grid')

# ---------- Grid Cells ----------
class GridCell(db.Model):
    __tablename__ = 'grid_cells'
    id = db.Column(db.Integer, primary_key=True)
    grid_id = db.Column(db.Integer, db.ForeignKey('grids.id'), nullable=False)
    row = db.Column(db.Integer, nullable=False)
    col = db.Column(db.Integer, nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    checked = db.Column(db.Boolean, default=False)

    grid = db.relationship('Grid', back_populates='cells')
    event = db.relationship('Event')

# ---------- Bingo Wins ----------
class BingoWin(db.Model):
    __tablename__ = 'bingo_wins'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    grid_id = db.Column(db.Integer, db.ForeignKey('grids.id'), nullable=False)
    bingo_type = db.Column(db.String(20))  # 'row', 'col', 'diag'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='wins')
    grid = db.relationship('Grid', back_populates='wins')