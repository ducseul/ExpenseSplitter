from datetime import datetime, timedelta
import os


class Group:
    def __init__(self, code, name, created_by=None):
        self.code = code
        self.name = name
        self.created_by = created_by
        self.created_at = datetime.now()
        self.last_activity = datetime.now()  # Track last activity time
        self.participants = []
        self.expenses = []
        # Get TTL from environment variable with default of 60 days
        self.ttl_days = int(os.environ.get('GROUP_TTL', 60))
        self.inactivity_days = int(os.environ.get('GROUP_INACTIVE_MAX', 7))

    def update_activity(self):
        """Update the last activity timestamp to now"""
        self.last_activity = datetime.now()

    def days_since_activity(self):
        """Return the number of days since the last activity"""
        now = datetime.now()
        days = (now - self.last_activity).days
        return days

    def is_inactive(self):
        """Check if the group is inactive (no expenses added for 7 days)"""
        return self.days_since_activity() >= self.inactivity_days

    def is_close_to_inactive(self):
        """Check if the group is close to being marked inactive (< 3 days)"""
        days_left = self.inactivity_days - self.days_since_activity()
        return 0 < days_left <= 3

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

    def __str__(self):
        return f"Group {self.code} - {self.name} with {len(self.participants)} participants and {len(self.expenses)} expenses"