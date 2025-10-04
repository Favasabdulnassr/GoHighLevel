from django.shortcuts import render, redirect
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.http import JsonResponse
import requests
from .models import IntegrationToken,CustomField


CLIENT_ID = settings.CLIENT_ID
CLIENT_SECRET = settings.CLIENT_SECRET
REDIRECT_URI = settings.REDIRECT_URI


def Login(request):
    return render(request,"loginButton.html")


def authorize(request):
    scope = (
        "contacts.readonly%20"
        "contacts.write%20"
        "locations/customFields.readonly%20"
        "locations/customValues.write%20"
        "locations/customFields.write"
    )
    url=(
        f"https://marketplace.gohighlevel.com/oauth/chooselocation?"
        f"response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope={scope}"
    )
    return redirect(url)


def callback(request):
    code = request.GET.get("code")
    if not code:
        return JsonResponse({"error": "No code provided"}, status=400)

    return render(request, "form.html", {"code": code})



def submit_location(request):
    print("submit_location called with method:", request.method)

    if request.method == "POST":
        code = request.POST.get("code")
        location_id = request.POST.get("location_id")
        print(f"Received code: {code}")
        print(f"Received location_id: {location_id}")

        # Step 1: Exchange code for tokens
        token_url = "https://services.leadconnectorhq.com/oauth/token"
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
        }
        print(" Sending token exchange request to:", token_url)

        token_response = requests.post(token_url, data=data)
        print("Token response status code:", token_response.status_code)

        tokens = token_response.json()
        print(" Token response JSON:", tokens)

        if "access_token" not in tokens:
            print("Access token missing in response!")
            return render(request, "form.html", {"error": "Failed to get tokens"})

        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        expires_in = tokens.get("expires_in", 3600)
        expires_at = timezone.now() + timedelta(seconds=expires_in)
        print("Token exchange successful")

        # Step 2: Save IntegrationToken
        integration, created = IntegrationToken.objects.update_or_create(
            location_id=location_id,
            defaults={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
            },
        )
        print("Token saved to DB. Created new:", created)

        # Step 3: Fetch Custom Fields
        url = f"https://services.leadconnectorhq.com/locations/{location_id}/customFields?model=all"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Version": "2021-07-28",
        }
        print(" Fetching custom fields from:", url)

        response = requests.get(url, headers=headers)
        print("Custom fields response status code:", response.status_code)

        try:
            data = response.json()
            print("Custom fields JSON response:", data)
        except Exception as e:
            print("Error :", e)
            return render(request, "form.html", {"error": "Invalid JSON response"})

        if response.status_code == 200 and "customFields" in data:
            print("Custom fields fetched successfully:", len(data["customFields"]))

            # Delete existing
            deleted_count, _ = CustomField.objects.filter(location=integration).delete()
            print(f"Deleted {deleted_count} old custom fields for this location")

            # Save new fields
            for field in data["customFields"]:
                print(f"Saving field: {field.get('name')} ({field.get('fieldKey')})")
                CustomField.objects.create(
                    location=integration,
                    field_id=field.get("id"),
                    name=field.get("name"),
                    field_key=field.get("fieldKey"),
                    data_type=field.get("dataType"),
                    model=field.get("model"),
                )

            print("All custom fields saved successfully")
            return redirect("list_custom_fields", location_id=location_id)

        else:
            print("Failed to fetch custom fields or empty response")
            return render(request, "form.html", {"error": "Failed to fetch custom fields"})

    print("Request method not POST, rendering form")
    return render(request, "form.html")



def list_custom_fields(request, location_id):
    try:
        integration = IntegrationToken.objects.get(location_id=location_id)
    except IntegrationToken.DoesNotExist:
        return render(request, "custom_fields.html", {"message": "Integration not found"})

    custom_fields = integration.custom_fields.all()
    return render(request, "custom_fields.html", {"custom_fields": custom_fields})
