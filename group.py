from datetime import datetime

class Group:
    def __init__(self, code, name, created_by=None):
        self.code = code
        self.name = name
        self.created_by = created_by
        self.created_at = datetime.now()
        self.participants = []
        self.expenses = []