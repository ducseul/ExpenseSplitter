from datetime import datetime
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps
from expense_manager import ExpenseManager
from flask_socketio import SocketIO, emit

load_dotenv(dotenv_path='.env')
PORT = int(os.environ.get("PORT", 8080))

# Default value for GROUP_TTL if not specified in .env
GROUP_TTL = int(os.environ.get("GROUP_TTL", 60))
print(f"Group TTL set to {GROUP_TTL} days")
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
            # Group might be expired or inactive
            flash("This group no longer exists or has been removed due to inactivity.", "danger")
            session.pop('group_code', None)
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

    if group_code is None:
        # Group creation failed due to limit being reached
        flash(
            "We're currently experiencing high traffic. The maximum number of active groups has been reached. Please try again later or join an existing group.",
            "danger")
        return redirect(url_for('index'))

    session['group_code'] = group_code
    return redirect(url_for('participants'))

'''
curl http://{host}:{port}/system_status?admin_key=admin_key_inside_env
'''
@app.route('/system_status', methods=['GET'])
def system_status():
    if request.args.get('admin_key') != os.environ.get('ADMIN_KEY', 'admin'):
        return jsonify({'error': 'Unauthorized'}), 403

    manager = get_manager()
    active_groups = manager.get_total_active_groups()
    capacity = (active_groups / manager.MAX_GROUPS) * 100

    return jsonify({
        'active_groups': active_groups,
        'max_groups': manager.MAX_GROUPS,
        'capacity_percentage': f"{capacity:.1f}%",
        'is_at_capacity': active_groups >= manager.MAX_GROUPS
    })

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

    group.update_activity()  # Update activity timestamp when participants are set

    return redirect(url_for('expenses', group=group_code))


@app.route('/expenses')
@group_required
@participants_required
def expenses():
    manager = get_manager()
    group_code = get_current_group_code()
    group = manager.get_group(group_code)

    # Check for inactivity warning
    if group.is_close_to_inactive():
        days_left = group.inactivity_days - group.days_since_activity()
        flash(f"Warning: This group will be removed in {days_left} days if no new expenses are added.", "warning")

    return render_template('expenses.html',
                           group_code=group_code,
                           group_name=group.name,
                           participants=group.participants,
                           expenses=group.expenses,
                           days_left=group.days_until_expiration(),
                           is_expiring_soon=group.is_expiring_soon(),
                           days_since_activity=group.days_since_activity(),
                           inactivity_limit=group.inactivity_days,
                           is_close_to_inactive=group.is_close_to_inactive(),
                           expiration_date=group.expires_at().strftime('%d %b %Y'))


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

    # Check for inactivity warning
    if group.is_close_to_inactive():
        days_left = group.inactivity_days - group.days_since_activity()
        flash(f"Warning: This group will be removed in {days_left} days if no new expenses are added.", "warning")

    return render_template('summary.html',
                           group_code=group_code,
                           group_name=group.name,
                           settlements=settlements,
                           days_left=group.days_until_expiration(),
                           is_expiring_soon=group.is_expiring_soon(),
                           days_since_activity=group.days_since_activity(),
                           inactivity_limit=group.inactivity_days,
                           is_close_to_inactive=group.is_close_to_inactive(),
                           expiration_date=group.expires_at().strftime('%d %b %Y'))


@app.route('/clear')
@group_required
def clear_group():
    group_code = get_current_group_code()
    manager = get_manager()
    group = manager.get_group(group_code)
    if group:
        group.expenses = []
        group.update_activity()  # Update activity timestamp when expenses are cleared
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

# Schedule regular cleanup
@app.before_request
def cleanup_expired_groups():
    manager = get_manager()
    manager.clean_expired_groups()
    manager.clean_inactive_groups()  # Also clean inactive groups

def check_environment():
    ttl = os.environ.get('GROUP_TTL')
    inactivity_days = os.environ.get('GROUP_INACTIVE_MAX')
    if ttl is None:
        print("Warning: GROUP_TTL not found in environment. Using default value of 60 days.")
    if inactivity_days is None:
        print("Warning: GROUP_INACTIVE_MAX not found in environment. Using default value of 7 days.")

if __name__ == '__main__':
    print(f'Server started at {datetime.now()} on port {PORT}')
    check_environment()
    socketio.run(app, host='0.0.0.0', port=PORT, allow_unsafe_werkzeug=True)