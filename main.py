from datetime import datetime
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps
from expense_manager import ExpenseManager
from flask_socketio import SocketIO, emit

load_dotenv(dotenv_path='.env')
PORT = int(os.environ.get("PORT", 8080))
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')  # or 'threading' if eventlet not used

expense_manager = ExpenseManager()

def get_manager():
    global expense_manager
    return expense_manager


def get_current_group_code():
    return session.get('group_code')


def group_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        group_code = request.args.get('group') or get_current_group_code()
        if not group_code:
            return redirect(url_for('index'))

        manager = get_manager()
        group = manager.get_group(group_code)
        if not group:
            return redirect(url_for('index'))

        session['group_code'] = group_code
        return f(*args, **kwargs)
    return decorated_function


def participants_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        group_code = get_current_group_code()
        if not group_code:
            return redirect(url_for('index'))

        manager = get_manager()
        group = manager.get_group(group_code)
        if not group or not group.participants:
            return redirect(url_for('index'))

        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/create_room', methods=['POST'])
def create_room():
    manager = get_manager()
    room_name = request.form.get('roomName', '').strip()
    group_code = manager.create_group(room_name)
    session['group_code'] = group_code
    return redirect(url_for('participants'))


@app.route('/join_room', methods=['POST'])
def join_room():
    manager = get_manager()
    group_code = request.form.get('roomCode', '').strip().upper()
    print(f'Got request to join group {group_code}, found: {manager.get_group(group_code)}')

    if manager.get_group(group_code):
        session['group_code'] = group_code
        return redirect(url_for('expenses', group=group_code))  # Redirect to expenses with ?group=CODE
    return redirect(url_for('index'))


@app.route('/participants', methods=['GET'])
@group_required
def participants():
    manager = get_manager()
    group_code = get_current_group_code()
    group = manager.get_group(group_code)

    return render_template('participants.html',
                           group_code=group_code,
                           group_name=group.name,
                           participants=group.participants)


@app.route('/participants', methods=['POST'])
@group_required
def set_participants():
    manager = get_manager()
    group_code = get_current_group_code()
    participants = request.form.getlist('participants[]')

    group = manager.get_group(group_code)
    group.participants = []
    for p in participants:
        p = p.strip()
        if p and p not in group.participants:
            group.participants.append(p)

    return redirect(url_for('expenses', group=group_code))


@app.route('/expenses')
@group_required
@participants_required
def expenses():
    manager = get_manager()
    group_code = get_current_group_code()
    group = manager.get_group(group_code)

    return render_template('expenses.html',
                           group_code=group_code,
                           group_name=group.name,
                           participants=group.participants,
                           expenses=group.expenses)


@app.route('/add_expense', methods=['POST'])
def add_expense():
    manager = get_manager()
    group_code = get_current_group_code()
    data = request.json

    success = manager.add_expense(
        group_code,
        data['description'],
        data['amount'],
        data['payer'],
        data['involved']
    )

    if success:
        socketio.emit('expense_added', {'group': group_code})
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Failed to add expense'})



@app.route('/summary')
@group_required
@participants_required
def summary():
    manager = get_manager()
    group_code = get_current_group_code()
    group = manager.get_group(group_code)
    settlements = manager.get_settlements(group_code)

    return render_template('summary.html',
                           group_code=group_code,
                           group_name=group.name,
                           settlements=settlements)


@app.route('/clear')
@group_required
def clear_group():
    group_code = get_current_group_code()
    manager = get_manager()
    group = manager.get_group(group_code)
    if group:
        group.expenses = []
    return redirect(url_for('expenses', group=group_code))


@app.route('/leave_group')
def leave_group():
    session.pop('group_code', None)
    return redirect(url_for('index'))

@app.route('/delete_expense/<expense_id>', methods=['DELETE'])
@group_required
def delete_expense(expense_id):
    manager = get_manager()
    group_code = get_current_group_code()

    success = manager.delete_expense(group_code, expense_id)
    if success:
        socketio.emit('expense_added', {'group': group_code})  # refresh all clients
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Expense not found'})

# if __name__ == '__main__':
#     socketio.run(app, debug=True)

if __name__ == '__main__':
    print(f'Server started at {datetime.now()} on port {PORT}')
    socketio.run(app, host='0.0.0.0', port=PORT, allow_unsafe_werkzeug=True)
