from django.utils import timezone
from datetime import timedelta
from django.conf import settings
import requests
from .models import IntegrationToken

CLIENT_ID = settings.CLIENT_ID
CLIENT_SECRET = settings.CLIENT_SECRET

def get_valid_access_token(location_id):

    try:
        integration = IntegrationToken.objects.get(location_id=location_id)
    except IntegrationToken.DoesNotExist:
        return None

    if timezone.now() >= integration.expires_at:

        refresh_url = "https://services.leadconnectorhq.com/oauth/token"
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": integration.refresh_token,
        }

        resp = requests.post(refresh_url, data=data)
        resp_data = resp.json()

        if "access_token" not in resp_data:
            return None

        integration.access_token = resp_data["access_token"]
        integration.refresh_token = resp_data.get("refresh_token", integration.refresh_token)
        expires_in = resp_data.get("expires_in", 3600)
        integration.expires_at = timezone.now() + timedelta(seconds=expires_in)
        integration.save()

    return integration.access_token
