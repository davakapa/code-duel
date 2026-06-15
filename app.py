from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid
import random
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret123'

database_url = os.environ.get('DATABASE_URL', 'sqlite:///codeduel.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

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
    # === EASY ===
    {
        "id": 1,
        "title": "Сумма двух чисел",
        "description": "Напиши функцию solution(a, b), которая возвращает сумму двух чисел.",
        "difficulty": "easy",
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
        "difficulty": "easy",
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
        "difficulty": "easy",
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
        "difficulty": "easy",
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
        "difficulty": "easy",
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
        "difficulty": "easy",
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
        "difficulty": "easy",
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
        "difficulty": "easy",
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
        "difficulty": "easy",
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
        "difficulty": "easy",
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
        "difficulty": "easy",
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
        "difficulty": "easy",
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
        "difficulty": "easy",
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
        "difficulty": "easy",
        "tests": [
            {"input": [[1, 2, 2, 3, 3, 3]], "output": [1, 2, 3]},
            {"input": [[5, 5, 5]], "output": [5]},
            {"input": [[1, 2, 3]], "output": [1, 2, 3]},
        ]
    },
    {
        "id": 15,
        "title": "Сортировка пузырьком",
        "description": "Напиши функцию solution(nums), которая сортирует список методом пузырька и возвращает его.",
        "difficulty": "easy",
        "tests": [
            {"input": [[3, 1, 2]], "output": [1, 2, 3]},
            {"input": [[5, 4, 3, 2, 1]], "output": [1, 2, 3, 4, 5]},
            {"input": [[1]], "output": [1]},
        ]
    },
    {
        "id": 16,
        "title": "Среднее арифметическое",
        "description": "Напиши функцию solution(nums), которая возвращает среднее арифметическое списка чисел.",
        "difficulty": "easy",
        "tests": [
            {"input": [[1, 2, 3, 4, 5]], "output": 3.0},
            {"input": [[10, 20]], "output": 15.0},
            {"input": [[7]], "output": 7.0},
        ]
    },
    {
        "id": 17,
        "title": "Подсчёт элементов",
        "description": "Напиши функцию solution(nums, x), которая возвращает количество вхождений x в список nums.",
        "difficulty": "easy",
        "tests": [
            {"input": [[1, 2, 2, 3, 2], 2], "output": 3},
            {"input": [[1, 1, 1], 1], "output": 3},
            {"input": [[1, 2, 3], 5], "output": 0},
        ]
    },
    {
        "id": 18,
        "title": "Сумма цифр",
        "description": "Напиши функцию solution(n), которая возвращает сумму цифр числа n.",
        "difficulty": "easy",
        "tests": [
            {"input": [123], "output": 6},
            {"input": [9999], "output": 36},
            {"input": [0], "output": 0},
        ]
    },
    {
        "id": 19,
        "title": "Перевод в двоичную систему",
        "description": "Напиши функцию solution(n), которая возвращает строку с двоичным представлением числа n без использования bin().",
        "difficulty": "easy",
        "tests": [
            {"input": [2], "output": "10"},
            {"input": [10], "output": "1010"},
            {"input": [1], "output": "1"},
        ]
    },
    {
        "id": 20,
        "title": "Анаграмма",
        "description": "Напиши функцию solution(s1, s2), которая возвращает True если строки являются анаграммами друг друга.",
        "difficulty": "easy",
        "tests": [
            {"input": ["listen", "silent"], "output": True},
            {"input": ["hello", "world"], "output": False},
            {"input": ["abc", "cba"], "output": True},
        ]
    },
    # === MEDIUM ===
    {
        "id": 21,
        "title": "Второй максимум",
        "description": "Напиши функцию solution(nums), которая возвращает второй по величине элемент списка.",
        "difficulty": "medium",
        "tests": [
            {"input": [[1, 2, 3, 4, 5]], "output": 4},
            {"input": [[10, 5, 8]], "output": 8},
            {"input": [[1, 1, 2]], "output": 1},
        ]
    },
    {
        "id": 22,
        "title": "Подстрока",
        "description": "Напиши функцию solution(s, sub), которая возвращает True если sub является подстрокой s. Нельзя использовать оператор in.",
        "difficulty": "medium",
        "tests": [
            {"input": ["hello world", "world"], "output": True},
            {"input": ["python", "java"], "output": False},
            {"input": ["abcdef", "cde"], "output": True},
        ]
    },
    {
        "id": 23,
        "title": "Квадратный корень",
        "description": "Напиши функцию solution(n), которая возвращает целую часть квадратного корня числа n без использования math.sqrt() и **.",
        "difficulty": "medium",
        "tests": [
            {"input": [9], "output": 3},
            {"input": [16], "output": 4},
            {"input": [20], "output": 4},
        ]
    },
    {
        "id": 24,
        "title": "Удалить дубликаты из строки",
        "description": "Напиши функцию solution(s), которая возвращает строку без повторяющихся символов, сохраняя порядок первого появления.",
        "difficulty": "medium",
        "tests": [
            {"input": ["aabbcc"], "output": "abc"},
            {"input": ["hello"], "output": "helo"},
            {"input": ["abcd"], "output": "abcd"},
        ]
    },
    {
        "id": 25,
        "title": "Количество слов",
        "description": "Напиши функцию solution(s), которая возвращает количество слов в строке.",
        "difficulty": "medium",
        "tests": [
            {"input": ["hello world"], "output": 2},
            {"input": ["one two three four"], "output": 4},
            {"input": ["python"], "output": 1},
        ]
    },
    {
        "id": 26,
        "title": "Список квадратов",
        "description": "Напиши функцию solution(n), которая возвращает список квадратов чисел от 1 до n включительно.",
        "difficulty": "medium",
        "tests": [
            {"input": [5], "output": [1, 4, 9, 16, 25]},
            {"input": [3], "output": [1, 4, 9]},
            {"input": [1], "output": [1]},
        ]
    },
    {
        "id": 27,
        "title": "Наибольший общий делитель",
        "description": "Напиши функцию solution(a, b), которая возвращает наибольший общий делитель двух чисел без использования math.gcd().",
        "difficulty": "medium",
        "tests": [
            {"input": [12, 8], "output": 4},
            {"input": [100, 75], "output": 25},
            {"input": [7, 3], "output": 1},
        ]
    },
    {
        "id": 28,
        "title": "Переворот списка",
        "description": "Напиши функцию solution(nums), которая возвращает список в обратном порядке без использования reverse() и срезов [::-1].",
        "difficulty": "medium",
        "tests": [
            {"input": [[1, 2, 3, 4, 5]], "output": [5, 4, 3, 2, 1]},
            {"input": [[10, 20]], "output": [20, 10]},
            {"input": [[42]], "output": [42]},
        ]
    },
    {
        "id": 29,
        "title": "Матрица — транспонирование",
        "description": "Напиши функцию solution(matrix), которая возвращает транспонированную матрицу.",
        "difficulty": "medium",
        "tests": [
            {"input": [[[1, 2], [3, 4]]], "output": [[1, 3], [2, 4]]},
            {"input": [[[1, 2, 3]]], "output": [[1], [2], [3]]},
            {"input": [[[1, 2], [3, 4], [5, 6]]], "output": [[1, 3, 5], [2, 4, 6]]},
        ]
    },
    {
        "id": 30,
        "title": "Поиск пары с суммой",
        "description": "Напиши функцию solution(nums, target), которая возвращает True если в списке есть два числа дающих в сумме target.",
        "difficulty": "medium",
        "tests": [
            {"input": [[1, 2, 3, 4], 7], "output": True},
            {"input": [[1, 2, 3], 10], "output": False},
            {"input": [[5, 5], 10], "output": True},
        ]
    },
    {
        "id": 31,
        "title": "Группировка по чётности",
        "description": "Напиши функцию solution(nums), которая возвращает словарь с ключами 'even' и 'odd', содержащий чётные и нечётные числа списка.",
        "difficulty": "medium",
        "tests": [
            {"input": [[1, 2, 3, 4, 5]], "output": {"even": [2, 4], "odd": [1, 3, 5]}},
            {"input": [[2, 4, 6]], "output": {"even": [2, 4, 6], "odd": []}},
            {"input": [[1, 3]], "output": {"even": [], "odd": [1, 3]}},
        ]
    },
    {
        "id": 32,
        "title": "Самое длинное слово",
        "description": "Напиши функцию solution(s), которая возвращает самое длинное слово в строке. Если таких несколько — первое.",
        "difficulty": "medium",
        "tests": [
            {"input": ["hello world python"], "output": "python"},
            {"input": ["cat dog elephant"], "output": "elephant"},
            {"input": ["one two"], "output": "one"},
        ]
    },
    {
        "id": 33,
        "title": "Матрица — сумма диагонали",
        "description": "Напиши функцию solution(matrix), которая возвращает сумму элементов главной диагонали квадратной матрицы.",
        "difficulty": "medium",
        "tests": [
            {"input": [[[1, 2], [3, 4]]], "output": 5},
            {"input": [[[1, 0, 0], [0, 2, 0], [0, 0, 3]]], "output": 6},
            {"input": [[[5]]], "output": 5},
        ]
    },
    {
        "id": 34,
        "title": "Числа Армстронга",
        "description": "Напиши функцию solution(n), которая возвращает True если n является числом Армстронга. Например 153 = 1³+5³+3³.",
        "difficulty": "medium",
        "tests": [
            {"input": [153], "output": True},
            {"input": [370], "output": True},
            {"input": [123], "output": False},
        ]
    },
    {
        "id": 35,
        "title": "Частота символов",
        "description": "Напиши функцию solution(s), которая возвращает словарь где ключи — символы строки, значения — количество вхождений.",
        "difficulty": "medium",
        "tests": [
            {"input": ["hello"], "output": {"h": 1, "e": 1, "l": 2, "o": 1}},
            {"input": ["aaa"], "output": {"a": 3}},
            {"input": ["ab"], "output": {"a": 1, "b": 1}},
        ]
    },
    {
        "id": 36,
        "title": "Разворот слов",
        "description": "Напиши функцию solution(s), которая переворачивает порядок слов в строке.",
        "difficulty": "medium",
        "tests": [
            {"input": ["hello world"], "output": "world hello"},
            {"input": ["one two three"], "output": "three two one"},
            {"input": ["python"], "output": "python"},
        ]
    },
    {
        "id": 37,
        "title": "Слияние отсортированных списков",
        "description": "Напиши функцию solution(a, b), которая сливает два отсортированных списка в один отсортированный список.",
        "difficulty": "medium",
        "tests": [
            {"input": [[1, 3, 5], [2, 4, 6]], "output": [1, 2, 3, 4, 5, 6]},
            {"input": [[1, 2], [3, 4]], "output": [1, 2, 3, 4]},
            {"input": [[], [1, 2]], "output": [1, 2]},
        ]
    },
    {
        "id": 38,
        "title": "Количество гласных и согласных",
        "description": "Напиши функцию solution(s), которая возвращает список [гласные, согласные].",
        "difficulty": "medium",
        "tests": [
            {"input": ["hello"], "output": [2, 3]},
            {"input": ["python"], "output": [1, 5]},
            {"input": ["aeiou"], "output": [5, 0]},
        ]
    },
    {
        "id": 39,
        "title": "Сумма простых чисел",
        "description": "Напиши функцию solution(n), которая возвращает сумму всех простых чисел до n включительно.",
        "difficulty": "medium",
        "tests": [
            {"input": [10], "output": 17},
            {"input": [20], "output": 77},
            {"input": [5], "output": 10},
        ]
    },
    {
        "id": 40,
        "title": "Поворот списка",
        "description": "Напиши функцию solution(nums, k), которая циклически сдвигает список вправо на k позиций.",
        "difficulty": "medium",
        "tests": [
            {"input": [[1, 2, 3, 4, 5], 2], "output": [4, 5, 1, 2, 3]},
            {"input": [[1, 2, 3], 1], "output": [3, 1, 2]},
            {"input": [[1, 2], 4], "output": [1, 2]},
        ]
    },
    # === HARD ===
    {
        "id": 41,
        "title": "Скобочная последовательность",
        "description": "Напиши функцию solution(s), которая возвращает True если строка содержит правильную скобочную последовательность из (), [], {}.",
        "difficulty": "hard",
        "tests": [
            {"input": ["()[]{}"], "output": True},
            {"input": ["([)]"], "output": False},
            {"input": ["{[]}"], "output": True},
        ]
    },
    {
        "id": 42,
        "title": "Наибольшая подстрока без повторений",
        "description": "Напиши функцию solution(s), которая возвращает длину наибольшей подстроки без повторяющихся символов.",
        "difficulty": "hard",
        "tests": [
            {"input": ["abcabcbb"], "output": 3},
            {"input": ["bbbbb"], "output": 1},
            {"input": ["pwwkew"], "output": 3},
        ]
    },
    {
        "id": 43,
        "title": "Количество островов",
        "description": "Напиши функцию solution(grid), которая считает количество островов в матрице (1 — суша, 0 — вода).",
        "difficulty": "hard",
        "tests": [
            {"input": [[[1,1,0],[0,1,0],[0,0,1]]], "output": 2},
            {"input": [[[1,0,0],[0,0,0],[0,0,1]]], "output": 2},
            {"input": [[[1,1],[1,1]]], "output": 1},
        ]
    },
    {
        "id": 44,
        "title": "Длиннейшая общая подпоследовательность",
        "description": "Напиши функцию solution(s1, s2), которая возвращает длину наибольшей общей подпоследовательности (LCS).",
        "difficulty": "hard",
        "tests": [
            {"input": ["abcde", "ace"], "output": 3},
            {"input": ["abc", "abc"], "output": 3},
            {"input": ["abc", "def"], "output": 0},
        ]
    },
    {
        "id": 45,
        "title": "Задача о рюкзаке",
        "description": "Напиши функцию solution(weights, values, capacity), которая возвращает максимальную стоимость предметов в рюкзаке.",
        "difficulty": "hard",
        "tests": [
            {"input": [[1, 2, 3], [6, 10, 12], 5], "output": 22},
            {"input": [[2, 3], [3, 4], 5], "output": 7},
            {"input": [[1], [10], 1], "output": 10},
        ]
    },
    {
        "id": 46,
        "title": "Генерация скобок",
        "description": "Напиши функцию solution(n), которая возвращает все возможные правильные скобочные последовательности из n пар скобок в виде отсортированного списка.",
        "difficulty": "hard",
        "tests": [
            {"input": [1], "output": ["()"]},
            {"input": [2], "output": ["(())", "()()"]},
            {"input": [3], "output": ["((()))", "(()())", "(())()", "()(())", "()()()"]},
        ]
    },
    {
        "id": 47,
        "title": "Двоичный поиск",
        "description": "Напиши функцию solution(nums, target), которая реализует двоичный поиск и возвращает индекс target, или -1 если не найден.",
        "difficulty": "hard",
        "tests": [
            {"input": [[1, 2, 3, 4, 5], 3], "output": 2},
            {"input": [[1, 2, 3, 4, 5], 6], "output": -1},
            {"input": [[1], 1], "output": 0},
        ]
    },
    {
        "id": 48,
        "title": "Быстрая сортировка",
        "description": "Напиши функцию solution(nums), которая сортирует список алгоритмом QuickSort и возвращает его.",
        "difficulty": "hard",
        "tests": [
            {"input": [[3, 6, 8, 10, 1, 2, 1]], "output": [1, 1, 2, 3, 6, 8, 10]},
            {"input": [[5, 4, 3, 2, 1]], "output": [1, 2, 3, 4, 5]},
            {"input": [[1]], "output": [1]},
        ]
    },
    {
        "id": 49,
        "title": "Числа в спирали",
        "description": "Напиши функцию solution(n), которая возвращает матрицу n×n заполненную числами от 1 до n² по спирали.",
        "difficulty": "hard",
        "tests": [
            {"input": [1], "output": [[1]]},
            {"input": [2], "output": [[1, 2], [4, 3]]},
            {"input": [3], "output": [[1, 2, 3], [8, 9, 4], [7, 6, 5]]},
        ]
    },
    {
        "id": 50,
        "title": "Минимальный путь в матрице",
        "description": "Напиши функцию solution(grid), которая возвращает минимальную сумму пути из верхнего левого в нижний правый угол. Двигаться можно только вправо или вниз.",
        "difficulty": "hard",
        "tests": [
            {"input": [[[1, 3, 1], [1, 5, 1], [4, 2, 1]]], "output": 7},
            {"input": [[[1, 2], [3, 4]]], "output": 7},
            {"input": [[[1]]], "output": 1},
        ]
    },
    {
        "id": 51,
        "title": "Самая длинная возрастающая подпоследовательность",
        "description": "Напиши функцию solution(nums), которая возвращает длину наибольшей строго возрастающей подпоследовательности (LIS).",
        "difficulty": "hard",
        "tests": [
            {"input": [[10, 9, 2, 5, 3, 7, 101, 18]], "output": 4},
            {"input": [[0, 1, 0, 3, 2, 3]], "output": 4},
            {"input": [[7, 7, 7]], "output": 1},
        ]
    },
    {
        "id": 52,
        "title": "Калькулятор",
        "description": "Напиши функцию solution(s), которая вычисляет результат выражения содержащего +, -, *, / и целые числа. Без использования eval().",
        "difficulty": "hard",
        "tests": [
            {"input": ["3+2*2"], "output": 7},
            {"input": ["10/2+3"], "output": 8},
            {"input": ["2+3*4-1"], "output": 13},
        ]
    },
    {
        "id": 53,
        "title": "Перестановки",
        "description": "Напиши функцию solution(nums), которая возвращает все перестановки списка в виде отсортированного списка списков.",
        "difficulty": "hard",
        "tests": [
            {"input": [[1, 2]], "output": [[1, 2], [2, 1]]},
            {"input": [[1, 2, 3]], "output": [[1, 2, 3], [1, 3, 2], [2, 1, 3], [2, 3, 1], [3, 1, 2], [3, 2, 1]]},
            {"input": [[1]], "output": [[1]]},
        ]
    },
    {
        "id": 54,
        "title": "Разбиение на подмножества с равной суммой",
        "description": "Напиши функцию solution(nums), которая возвращает True если список можно разбить на два подмножества с равной суммой.",
        "difficulty": "hard",
        "tests": [
            {"input": [[1, 5, 11, 5]], "output": True},
            {"input": [[1, 2, 3, 5]], "output": False},
            {"input": [[1, 1]], "output": True},
        ]
    },
    {
        "id": 55,
        "title": "Количество способов подняться по лестнице",
        "description": "Напиши функцию solution(n), которая возвращает количество способов подняться на n ступеней если можно делать шаги по 1 или 2 ступени.",
        "difficulty": "hard",
        "tests": [
            {"input": [2], "output": 2},
            {"input": [5], "output": 8},
            {"input": [10], "output": 89},
        ]
    },
    {
        "id": 56,
        "title": "Сжатие строки RLE",
        "description": "Напиши функцию solution(s), которая сжимает строку используя RLE кодирование. Например 'aabbb' → 'a2b3'. Если символ встречается 1 раз — цифра не пишется.",
        "difficulty": "hard",
        "tests": [
            {"input": ["aabbb"], "output": "a2b3"},
            {"input": ["abcd"], "output": "abcd"},
            {"input": ["aaabba"], "output": "a3b2a"},
        ]
    },
    {
        "id": 57,
        "title": "Игра Жизнь",
        "description": "Напиши функцию solution(board), которая делает один шаг симуляции игры Жизнь Конвея. 1 — живая клетка, 0 — мёртвая.",
        "difficulty": "hard",
        "tests": [
            {"input": [[[0,1,0],[0,0,1],[1,1,1],[0,0,0]]], "output": [[0,0,0],[1,0,1],[0,1,1],[0,1,0]]},
            {"input": [[[1,1],[1,0]]], "output": [[1,1],[1,1]]},
            {"input": [[[0,0],[0,0]]], "output": [[0,0],[0,0]]},
        ]
    },
    {
        "id": 58,
        "title": "Топологическая сортировка",
        "description": "Напиши функцию solution(n, edges), которая возвращает один из вариантов топологической сортировки графа с n вершинами.",
        "difficulty": "hard",
        "tests": [
            {"input": [4, [[0,1],[0,2],[1,3],[2,3]]], "output": [0, 1, 2, 3]},
            {"input": [3, [[0,1],[1,2]]], "output": [0, 1, 2]},
            {"input": [2, [[1,0]]], "output": [1, 0]},
        ]
    },
    {
        "id": 59,
        "title": "Регулярное выражение",
        "description": "Напиши функцию solution(s, p), которая реализует сопоставление с шаблоном где '.' соответствует любому символу, '*' — ноль или более предыдущих символов.",
        "difficulty": "hard",
        "tests": [
            {"input": ["aa", "a*"], "output": True},
            {"input": ["ab", ".*"], "output": True},
            {"input": ["aab", "c*a*b"], "output": True},
        ]
    },
    {
        "id": 60,
        "title": "Судоку — проверка",
        "description": "Напиши функцию solution(board), которая возвращает True если доска судоку 9x9 заполнена правильно. 0 означает пустую клетку.",
        "difficulty": "hard",
        "tests": [
            {"input": [[[5,3,4,6,7,8,9,1,2],[6,7,2,1,9,5,3,4,8],[1,9,8,3,4,2,5,6,7],[8,5,9,7,6,1,4,2,3],[4,2,6,8,5,3,7,9,1],[7,1,3,9,2,4,8,5,6],[9,6,1,5,3,7,2,8,4],[2,8,7,4,1,9,6,3,5],[3,4,5,2,8,6,1,7,9]]], "output": True},
            {"input": [[[5,3,4,6,7,8,9,1,2],[6,7,2,1,9,5,3,4,8],[1,9,8,3,4,2,5,6,7],[8,5,9,7,6,1,4,2,3],[4,2,6,8,5,3,7,9,1],[7,1,3,9,2,4,8,5,6],[9,6,1,5,3,7,2,8,4],[2,8,7,4,1,9,6,3,5],[3,4,5,2,8,6,1,7,5]]], "output": False},
            {"input": [[[5,3,0,0,7,0,0,0,0],[6,0,0,1,9,5,0,0,0],[0,9,8,0,0,0,0,6,0],[8,0,0,0,6,0,0,0,3],[4,0,0,8,0,3,0,0,1],[7,0,0,0,2,0,0,0,6],[0,6,0,0,0,0,2,8,0],[0,0,0,4,1,9,0,0,5],[0,0,0,0,8,0,0,7,9]]], "output": True},
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
        player = Player(username=username, password=generate_password_hash(password))
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
    from flask import make_response
    resp = make_response(render_template('leaderboard.html', players=players))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    return resp

@app.route('/profile/<username>')
def profile(username):
    player = Player.query.filter_by(username=username).first()
    if not player:
        return render_template('profile.html', player=None, username=username, matches=[])
    matches = Match.query.filter(
        (Match.winner == username) | (Match.loser == username)
    ).order_by(Match.played_at.desc()).limit(10).all()
    return render_template('profile.html', player=player, username=username, matches=matches)

DIFFICULTY_POINTS = {
    'easy':   {'win': 25,  'loss': 50},
    'medium': {'win': 50,  'loss': 25},
    'hard':   {'win': 100, 'loss': 10},
}

def update_ratings(winner_name, loser_name, task_title, difficulty='easy'):
    try:
        points = DIFFICULTY_POINTS.get(difficulty, DIFFICULTY_POINTS['easy'])
        winner = db.session.query(Player).filter_by(username=winner_name).first()
        loser = db.session.query(Player).filter_by(username=loser_name).first()
        print(f"Found winner: {winner}, loser: {loser}")
        if winner and loser:
            winner.rating = winner.rating + points['win']
            winner.wins = winner.wins + 1
            loser.rating = max(0, loser.rating - points['loss'])
            loser.losses = loser.losses + 1
            match = Match(winner=winner_name, loser=loser_name, task_title=task_title)
            db.session.add(match)
            db.session.flush()
            db.session.commit()
            print(f"Committed! Winner {winner_name} rating: {winner.rating}, Loser {loser_name} rating: {loser.rating}")
            return points['win'], -points['loss']
        else:
            print(f"Player not found! winner={winner_name}, loser={loser_name}")
    except Exception as e:
        db.session.rollback()
        print(f"Rating update error: {e}")
    return 25, -25

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
            difficulty = task.get('difficulty', 'easy')
            try:
                win_pts, loss_pts = update_ratings(username, other, task['title'], difficulty)
                print(f"RATING UPDATE: {username} +{win_pts}, {other} {loss_pts}")
            except Exception as e:
                print(f"RATING ERROR: {e}")
                win_pts, loss_pts = 25, -25
            # Уведомляем победителя
            emit('rating_update', {'change': win_pts})
            # Уведомляем проигравшего
            emit('opponent_finished', {
                'username': username,
                'place': place,
                'rating_change': loss_pts
            }, to=room_id)
        else:
            emit('opponent_finished', {'username': username, 'place': place}, to=room_id)
    emit('test_results', {
        'results': results,
        'passed': passed,
        'total': len(task['tests']),
        'won': all_passed and len(room['finished']) == 1 and room['finished'][0] == username
    })

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)