from flask import Flask, render_template, request, redirect, url_for, session
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key'

class ExpenseManager:
    def __init__(self):
        self.participants = []
        self.expenses = []

    def add_participant(self, name):
        if name not in self.participants:
            self.participants.append(name)

    def add_expense(self, description, amount, payer, involved):
        self.expenses.append({
            'description': description,
            'amount': float(amount),
            'payer': payer,
            'involved': involved
        })

    def calculate_balances(self):
        balances = {p: 0.0 for p in self.participants}
        for expense in self.expenses:
            payer = expense['payer']
            if payer not in balances:
                balances[payer] = 0.0
            balances[payer] += expense['amount']
            share = expense['amount'] / len(expense['involved'])
            for person in expense['involved']:
                if person not in balances:
                    balances[person] = 0.0
                balances[person] -= share
        return balances

    def get_settlements(self):
        balances = self.calculate_balances()
        settlements = []
        debtors = {k: v for k, v in balances.items() if v < 0}
        creditors = {k: v for k, v in balances.items() if v > 0}
        for debtor, debt in debtors.items():
            while debt < -0.01:
                creditor, credit = next(iter(creditors.items()))
                amount = min(-debt, credit)
                settlements.append({
                    'from': debtor,
                    'to': creditor,
                    'amount': round(amount, 2)
                })
                debt += amount
                creditors[creditor] -= amount
                if creditors[creditor] < 0.01:
                    del creditors[creditor]
        return settlements

# Initialize manager from session
def get_manager():
    if 'participants' not in session:
        session['participants'] = []
    if 'expenses' not in session:
        session['expenses'] = []
    manager = ExpenseManager()
    manager.participants = session['participants']
    manager.expenses = session['expenses']
    return manager

def participants_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        manager = get_manager()
        if not manager.participants:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/participants', methods=['POST'])
def set_participants():
    manager = get_manager()
    participants = request.form.getlist('participants[]')
    manager.participants = [p.strip() for p in participants if p.strip()]
    session['participants'] = manager.participants
    return redirect(url_for('expenses'))

@app.route('/expenses')
@participants_required
def expenses():
    manager = get_manager()
    return render_template('expenses.html', participants=manager.participants, expenses=manager.expenses)

@app.route('/add_expense', methods=['POST'])
def add_expense():
    manager = get_manager()
    data = request.json
    manager.add_expense(data['description'], data['amount'], data['payer'], data['involved'])
    session['expenses'] = manager.expenses
    return {'status': 'success'}

@app.route('/summary')
@participants_required
def summary():
    manager = get_manager()
    settlements = manager.get_settlements()
    return render_template('summary.html', settlements=settlements)

@app.route('/clear')
def clear():
    session.pop('participants', None)
    session.pop('expenses', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)