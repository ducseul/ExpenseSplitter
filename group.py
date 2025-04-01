from datetime import datetime, timedelta
import os


class Group:
    def __init__(self, code, name, created_by=None):
        self.code = code
        self.name = name
        self.created_by = created_by
        self.created_at = datetime.now()
        self.participants = []
        self.expenses = []
        # Get TTL from environment variable with default of 60 days
        self.ttl_days = int(os.environ.get('GROUP_TTL', 60))

    def expires_at(self):
        """Return the expiration date of the group (TTL days after creation)"""
        return self.created_at + timedelta(days=self.ttl_days)

    def days_until_expiration(self):
        """Return the number of days until the group expires"""
        now = datetime.now()
        days = (self.expires_at() - now).days
        return max(0, days)  # Don't return negative days

    def is_expired(self):
        """Check if the group has expired"""
        return self.days_until_expiration() <= 0

    def is_expiring_soon(self):
        """Check if the group is expiring within 14 days"""
        days = self.days_until_expiration()
        return 0 < days <= 14