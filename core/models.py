from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from cryptography.fernet import Fernet, InvalidToken

class Project(models.Model):
    """
    Represents a user's migration project, which groups together
    source and target connections.
    """
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='projects')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Connection(models.Model):
    """
    Stores the connection details for a source or target database.
    Credentials are encrypted at rest.
    """
    class DbType(models.TextChoices):
        POSTGRES = 'postgres', 'PostgreSQL'
        MYSQL = 'mysql', 'MySQL'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='connections')
    name = models.CharField(max_length=255, help_text="A user-friendly name for the connection.")
    db_type = models.CharField(max_length=20, choices=DbType.choices)
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField()
    username = models.CharField(max_length=255)
    password_encrypted = models.TextField(blank=True, help_text="The encrypted password.")
    dbname = models.CharField(max_length=255, verbose_name="Database Name")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_db_type_display()})"

    @staticmethod
    def _get_fernet():
        """Initializes Fernet based on the application's secret key."""
        key = settings.DMIGRATE_FERNET_KEY
        if not key:
            raise ValueError("DMIGRATE_FERNET_KEY environment variable is not set.")
        return Fernet(key.encode())

    def set_password(self, raw_password: str):
        """Encrypts a raw password and stores it."""
        if raw_password:
            self.password_encrypted = self._get_fernet().encrypt(raw_password.encode()).decode()
        else:
            self.password_encrypted = ""

    def get_password(self) -> str | None:
        """Decrypts and returns the raw password."""
        if not self.password_encrypted:
            return None
        try:
            return self._get_fernet().decrypt(self.password_encrypted.encode()).decode()
        except InvalidToken:
            # This can happen if the key changes or the data is corrupted.
            # Handle this case gracefully in the application.
            return None

    @property
    def password(self):
        """A property to get the decrypted password."""
        return self.get_password()

    @password.setter
    def password(self, raw_password: str):
        """A property to set the password, which handles encryption."""
        self.set_password(raw_password)

    class Meta:
        verbose_name_plural = "Connections"
        unique_together = ('project', 'name')
