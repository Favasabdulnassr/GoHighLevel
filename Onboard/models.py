from django.db import models
from django.utils import timezone




class IntegrationToken(models.Model):
    location_id = models.CharField(max_length=100, unique=True)
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField()

    def is_expired(self):
        return timezone.now() >= self.expires_at
    


class CustomField(models.Model):
    location = models.ForeignKey(
        IntegrationToken,
        on_delete=models.CASCADE,
        related_name="custom_fields"  
    )
    field_id = models.CharField(max_length=255)   
    name = models.CharField(max_length=255)
    field_key = models.CharField(max_length=255)
    data_type = models.CharField(max_length=100)
    model = models.CharField(max_length=50)       

    def __str__(self):
        return f"{self.name} ({self.field_key})"


