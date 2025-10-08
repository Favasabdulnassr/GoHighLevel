from django.db import models
from django.utils import timezone




class IntegrationToken(models.Model):
    location_id = models.CharField(max_length=100, unique=True)
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField()
    name = models.CharField(max_length=255,blank=True,null=True)
    phone = models.CharField(max_length=50,blank=True,null=True)
    address = models.TextField(blank=True,null=True)
    website = models.CharField(max_length=255,blank=True,null=True)
    logo = models.ImageField(upload_to="logos/",blank=True,null=True)


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
    is_checked = models.BooleanField(default=False)    

    def __str__(self):
        return f"{self.name} ({self.field_key})"
    



class Pdf(models.Model):
    location = models.ForeignKey(IntegrationToken, on_delete=models.CASCADE)
    opportunity_id = models.CharField(max_length=255)
    data = models.JSONField()  
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PDF Data for Opportunity {self.opportunity_id}"


