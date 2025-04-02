import random
import string
import uuid
import os
import pickle
from datetime import datetime

from group import Group

class ExpenseManager:
    def __init__(self):
        self.groups = {}
        self.MAX_GROUPS = int(os.environ.get('MAX_GROUPS', 1000))  # Maximum number of groups allowed

    def create_group(self, name, created_by=None):
        # Clean up expired and inactive groups first
        self.clean_expired_groups()
        self.clean_inactive_groups()

        # Check if we've reached the maximum group limit
        if len(self.groups) >= self.MAX_GROUPS:
            print(f"Currently reaching MAX_GROUPS limit ({self.MAX_GROUPS})")
            return None  # Return None to indicate failure due to limit

        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6)).upper()
            if code not in self.groups:
                break

        group = Group(code, name, created_by)
        self.groups[code] = group
        return code

    def get_group(self, code):
        # Clean up expired and inactive groups before returning
        self.clean_expired_groups()
        self.clean_inactive_groups()
        return self.groups.get(code)

    def get_total_active_groups(self):
        """Return the current number of active groups"""
        self.clean_expired_groups()  # Make sure count is accurate
        self.clean_inactive_groups()
        return len(self.groups)

    def clean_expired_groups(self):
        """Remove all expired groups"""
        expired_codes = [code for code, group in self.groups.items() if group.is_expired()]
        for code in expired_codes:
            del self.groups[code]

    def clean_inactive_groups(self):
        """Remove all inactive groups (no activity for 7 days)"""
        inactive_codes = [code for code, group in self.groups.items() if group.is_inactive()]
        for code in inactive_codes:
            del self.groups[code]

    def add_participant(self, group_code, name):
        group = self.get_group(group_code)
        if group and name not in group.participants:
            group.participants.append(name)
            group.update_activity()  # Update activity timestamp
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
            group.update_activity()  # Update activity timestamp
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
        if len(group.expenses) < before:
            group.update_activity()  # Update activity timestamp on successful delete
            return True
        return False

    # For debugging purposes
    def __str__(self):
        return f"ExpenseManager with {len(self.groups)} active groups"