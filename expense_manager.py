import random
import string
import uuid
from datetime import datetime

from group import Group

class ExpenseManager:
    def __init__(self):
        self.groups = {}

    def create_group(self, name, created_by=None):
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6)).upper()
            if code not in self.groups:
                break

        group = Group(code, name, created_by)
        self.groups[code] = group
        return code

    def get_group(self, code):
        return self.groups.get(code)

    def add_participant(self, group_code, name):
        group = self.get_group(group_code)
        if group and name not in group.participants:
            group.participants.append(name)
            return True
        return False

    def add_expense(self, group_code, description, amount, payer, involved):
        group = self.get_group(group_code)
        if group:
            group.expenses.append({
                'id': str(uuid.uuid4()),
                'description': description,
                'amount': float(amount),
                'payer': payer,
                'involved': involved,
                'timestamp': datetime.now()
            })
            return True
        return False

    def calculate_balances(self, group_code):
        group = self.get_group(group_code)
        if not group:
            return {}

        balances = {p: 0.0 for p in group.participants}
        for expense in group.expenses:
            payer = expense['payer']
            balances[payer] += expense['amount']
            share = expense['amount'] / len(expense['involved'])
            for person in expense['involved']:
                balances[person] -= share
        return balances

    def get_settlements(self, group_code):
        group = self.get_group(group_code)
        if not group:
            return []

        balances = self.calculate_balances(group_code)
        settlements = []
        debtors = {k: v for k, v in balances.items() if v < 0}
        creditors = {k: v for k, v in balances.items() if v > 0}

        for debtor, debt in list(debtors.items()):
            while debt < -0.01 and creditors:
                try:
                    creditor = next(k for k, v in creditors.items() if v > 0.01)
                    credit = creditors[creditor]
                    amount = min(-debt, credit)
                    amount = round(amount, 2)

                    settlements.append({
                        'from': debtor,
                        'to': creditor,
                        'amount': amount
                    })

                    debt += amount
                    debtors[debtor] = debt
                    creditors[creditor] -= amount

                    if creditors[creditor] < 0.01:
                        del creditors[creditor]
                except StopIteration:
                    break

        return settlements

    def delete_expense(self, group_code, expense_id):
        group = self.get_group(group_code)
        if not group:
            return False

        before = len(group.expenses)
        group.expenses = [e for e in group.expenses if e['id'] != expense_id]
        return len(group.expenses) < before