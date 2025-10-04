# utils.py
from datetime import timedelta
from django.utils import timezone
import requests
from .models import IntegrationToken
from django.conf import settings

CLIENT_ID = settings.CLIENT_ID
CLIENT_SECRET = settings.CLIENT_SECRET

def get_valid_token(location_id):
    try:
        token_obj = IntegrationToken.objects.get(location_id=location_id)
    except IntegrationToken.DoesNotExist:
        return None

    if timezone.now() >= token_obj.expires_at:
        # Refresh token
        token_url = "https://services.leadconnectorhq.com/oauth/token"
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": token_obj.refresh_token,
        }
        resp = requests.post(token_url, data=data).json()
        if "access_token" not in resp:
            return None
        token_obj.access_token = resp["access_token"]
        token_obj.refresh_token = resp.get("refresh_token", token_obj.refresh_token)
        token_obj.expires_at = timezone.now() + timedelta(seconds=resp.get("expires_in", 3600))
        token_obj.save()

    return token_obj.access_token
