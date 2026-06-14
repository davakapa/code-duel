from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///codeduel.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Модели ---

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    rating = db.Column(db.Integer, default=1000)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def winrate(self):
        total = self.wins + self.losses
        if total == 0:
            return 0
        return round(self.wins / total * 100)

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    winner = db.Column(db.String(50))
    loser = db.Column(db.String(50))
    task_title = db.Column(db.String(100))
    played_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

rooms = {}
matchmaking_queue = []

TASKS = [
    {
        "id": 1,
        "title": "Сумма двух чисел",
        "description": "Напиши функцию solution(a, b), которая возвращает сумму двух чисел.",
        "tests": [
            {"input": [1, 2], "output": 3},
            {"input": [10, 20], "output": 30},
            {"input": [-5, 5], "output": 0},
        ]
    },
    {
        "id": 2,
        "title": "Максимум из трёх",
        "description": "Напиши функцию solution(a, b, c), которая возвращает максимальное из трёх чисел.",
        "tests": [
            {"input": [1, 2, 3], "output": 3},
            {"input": [10, 5, 8], "output": 10},
            {"input": [-1, -2, -3], "output": -1},
        ]
    },
    {
        "id": 3,
        "title": "Чётное или нечётное",
        "description": "Напиши функцию solution(n), которая возвращает True если число чётное, и False если нечётное.",
        "tests": [
            {"input": [2], "output": True},
            {"input": [3], "output": False},
            {"input": [0], "output": True},
        ]
    },
    {
        "id": 4,
        "title": "Факториал",
        "description": "Напиши функцию solution(n), которая возвращает факториал числа n.",
        "tests": [
            {"input": [0], "output": 1},
            {"input": [5], "output": 120},
            {"input": [3], "output": 6},
        ]
    },
    {
        "id": 5,
        "title": "Переворот строки",
        "description": "Напиши функцию solution(s), которая возвращает строку в обратном порядке.",
        "tests": [
            {"input": ["hello"], "output": "olleh"},
            {"input": ["abcd"], "output": "dcba"},
            {"input": ["a"], "output": "a"},
        ]
    },
    {
        "id": 6,
        "title": "Палиндром",
        "description": "Напиши функцию solution(s), которая возвращает True если строка является палиндромом, и False если нет.",
        "tests": [
            {"input": ["racecar"], "output": True},
            {"input": ["hello"], "output": False},
            {"input": ["madam"], "output": True},
        ]
    },
    {
        "id": 7,
        "title": "Сумма списка",
        "description": "Напиши функцию solution(nums), которая принимает список чисел и возвращает их сумму без использования sum().",
        "tests": [
            {"input": [[1, 2, 3, 4, 5]], "output": 15},
            {"input": [[-1, -2, 3]], "output": 0},
            {"input": [[10, 20, 30]], "output": 60},
        ]
    },
    {
        "id": 8,
        "title": "Количество гласных",
        "description": "Напиши функцию solution(s), которая возвращает количество гласных букв (a, e, i, o, u) в строке.",
        "tests": [
            {"input": ["hello"], "output": 2},
            {"input": ["python"], "output": 1},
            {"input": ["aeiou"], "output": 5},
        ]
    },
    {
        "id": 9,
        "title": "Число Фибоначчи",
        "description": "Напиши функцию solution(n), которая возвращает n-е число Фибоначчи. F(0)=0, F(1)=1, F(2)=1...",
        "tests": [
            {"input": [0], "output": 0},
            {"input": [6], "output": 8},
            {"input": [10], "output": 55},
        ]
    },
    {
        "id": 10,
        "title": "Простое число",
        "description": "Напиши функцию solution(n), которая возвращает True если число простое, и False если нет.",
        "tests": [
            {"input": [2], "output": True},
            {"input": [9], "output": False},
            {"input": [17], "output": True},
        ]
    },
    {
        "id": 11,
        "title": "Максимум в списке",
        "description": "Напиши функцию solution(nums), которая возвращает максимальный элемент списка без использования max().",
        "tests": [
            {"input": [[3, 1, 4, 1, 5, 9]], "output": 9},
            {"input": [[-5, -1, -3]], "output": -1},
            {"input": [[42]], "output": 42},
        ]
    },
    {
        "id": 12,
        "title": "FizzBuzz",
        "description": "Напиши функцию solution(n), которая возвращает 'Fizz' если n делится на 3, 'Buzz' если на 5, 'FizzBuzz' если на 15, и само число в остальных случаях.",
        "tests": [
            {"input": [3], "output": "Fizz"},
            {"input": [5], "output": "Buzz"},
            {"input": [15], "output": "FizzBuzz"},
            {"input": [7], "output": 7},
        ]
    },
    {
        "id": 13,
        "title": "Степень числа",
        "description": "Напиши функцию solution(base, exp), которая возвращает base в степени exp без использования ** и pow().",
        "tests": [
            {"input": [2, 10], "output": 1024},
            {"input": [3, 3], "output": 27},
            {"input": [5, 0], "output": 1},
        ]
    },
    {
        "id": 14,
        "title": "Уникальные элементы",
        "description": "Напиши функцию solution(nums), которая возвращает список уникальных элементов, сохраняя порядок первого появления.",
        "tests": [
            {"input": [[1, 2, 2, 3, 3, 3]], "output": [1, 2, 3]},
            {"input": [[5, 5, 5]], "output": [5]},
            {"input": [[1, 2, 3]], "output": [1, 2, 3]},
        ]
    },
]

# --- Роуты ---

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            return render_template('register.html', error='Заполни все поля!')
        if len(username) < 3:
            return render_template('register.html', error='Никнейм минимум 3 символа!')
        if len(password) < 4:
            return render_template('register.html', error='Пароль минимум 4 символа!')
        if Player.query.filter_by(username=username).first():
            return render_template('register.html', error='Этот никнейм уже занят!')
        player = Player(
            username=username,
            password=generate_password_hash(password)
        )
        db.session.add(player)
        db.session.commit()
        session['username'] = username
        return redirect(url_for('index'))
    return render_template('register.html', error=None)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        player = Player.query.filter_by(username=username).first()
        if not player or not check_password_hash(player.password, password):
            return render_template('login.html', error='Неверный никнейм или пароль!')
        session['username'] = username
        return redirect(url_for('index'))
    return render_template('login.html', error=None)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/duel/<room_id>')
def duel(room_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('duel.html', room_id=room_id)

@app.route('/leaderboard')
def leaderboard():
    players = Player.query.order_by(Player.rating.desc()).limit(20).all()
    return render_template('leaderboard.html', players=players)

@app.route('/profile/<username>')
def profile(username):
    player = Player.query.filter_by(username=username).first()
    if not player:
        return render_template('profile.html', player=None, username=username, matches=[])
    matches = Match.query.filter(
        (Match.winner == username) | (Match.loser == username)
    ).order_by(Match.played_at.desc()).limit(10).all()
    return render_template('profile.html', player=player, username=username, matches=matches)

# --- Вспомогательные функции ---

def update_ratings(winner_name, loser_name, task_title):
    with app.app_context():
        winner = Player.query.filter_by(username=winner_name).first()
        loser = Player.query.filter_by(username=loser_name).first()
        if winner and loser:
            winner.rating += 25
            winner.wins += 1
            loser.rating = max(0, loser.rating - 25)
            loser.losses += 1
            match = Match(winner=winner_name, loser=loser_name, task_title=task_title)
            db.session.add(match)
            db.session.commit()

# --- Сокет события ---

@socketio.on('find_match')
def find_match(data):
    username = data['username']
    global matchmaking_queue
    matchmaking_queue = [p for p in matchmaking_queue if p['username'] != username]

    if matchmaking_queue:
        opponent = matchmaking_queue.pop(0)
        room_id = str(uuid.uuid4())[:8]
        task = random.choice(TASKS)
        rooms[room_id] = {
            'players': [opponent['username'], username],
            'task': task,
            'finished': [],
        }
        join_room(room_id)
        emit('match_found', {'room_id': room_id}, to=opponent['sid'])
        emit('match_found', {'room_id': room_id})
        socketio.emit('duel_start', {
            'task': task,
            'players': [opponent['username'], username]
        }, to=room_id)
    else:
        matchmaking_queue.append({'username': username, 'sid': request.sid})
        emit('searching')

@socketio.on('cancel_search')
def cancel_search(data):
    global matchmaking_queue
    matchmaking_queue = [p for p in matchmaking_queue if p['username'] != data['username']]
    emit('search_cancelled')

@socketio.on('create_room')
def create_room(data):
    room_id = str(uuid.uuid4())[:8]
    task = random.choice(TASKS)
    rooms[room_id] = {
        'players': [data['username']],
        'task': task,
        'finished': [],
        'creator_sid': request.sid
    }
    join_room(room_id)
    emit('room_created', {'room_id': room_id})

@socketio.on('rejoin_room')
def rejoin_room(data):
    room_id = data['room_id']
    username = data['username']
    if room_id not in rooms:
        emit('error', {'message': 'Комната не найдена!'})
        return
    join_room(room_id)
    room = rooms[room_id]
    if len(room['players']) == 2:
        emit('duel_start', {
            'task': room['task'],
            'players': room['players']
        })

@socketio.on('join_room_event')
def join_room_event(data):
    room_id = data['room_id']
    username = data['username']
    if room_id not in rooms:
        emit('error', {'message': 'Комната не найдена!'})
        return
    room = rooms[room_id]
    if len(room['players']) >= 2:
        emit('error', {'message': 'Комната уже заполнена!'})
        return
    room['players'].append(username)
    join_room(room_id)
    emit('duel_start', {
        'task': room['task'],
        'players': room['players']
    }, to=room_id)

@socketio.on('submit_code')
def submit_code(data):
    room_id = data['room_id']
    code = data['code']
    username = data['username']
    if room_id not in rooms:
        emit('error', {'message': 'Комната не найдена!'})
        return
    room = rooms[room_id]
    task = room['task']
    results = []
    passed = 0
    for test in task['tests']:
        try:
            full_code = code + f"\nresult = solution(*{test['input']})"
            exec_globals = {}
            exec(full_code, exec_globals)
            if exec_globals['result'] == test['output']:
                results.append('✅')
                passed += 1
            else:
                results.append(f"❌ (ожидалось {test['output']}, получили {exec_globals['result']})")
        except Exception as e:
            results.append(f"❌ Ошибка: {str(e)}")
    all_passed = passed == len(task['tests'])
    if all_passed and username not in room['finished']:
        room['finished'].append(username)
        place = len(room['finished'])
        if place == 1 and len(room['players']) == 2:
            other = [p for p in room['players'] if p != username][0]
            update_ratings(username, other, task['title'])
        emit('opponent_finished', {'username': username, 'place': place}, to=room_id)
    emit('test_results', {
        'results': results,
        'passed': passed,
        'total': len(task['tests']),
        'won': all_passed and len(room['finished']) == 1 and room['finished'][0] == username
    })

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)