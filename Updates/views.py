from django.shortcuts import get_object_or_404,redirect
from Onboard.models import IntegrationToken,CustomField
import requests
from Onboard.utils import get_valid_access_token
from django.contrib import messages



def update_logo(request,location_id):
    if request.method == "POST":
        logo_file = request.FILES.get("logo")
        if not logo_file:
            return redirect("fetch_custom_fields", location_id=location_id)
        
        integration = get_object_or_404(IntegrationToken,location_id=location_id)
        integration.logo = logo_file
        integration.save()

    return redirect("Onboard:fetch_custom_fields",location_id=location_id)
    





def sync_latest_fields(request, location_id):
   
    access_token = get_valid_access_token(location_id)
    if not access_token:
        messages.error(request, "Failed to get valid access token.")
        return redirect("Onboard:list_custom_fields", location_id=location_id)

    try:
        integration = IntegrationToken.objects.get(location_id=location_id)
    except IntegrationToken.DoesNotExist:
        messages.error(request, "Integration not found for this location.")
        return redirect("Onboard:list_custom_fields", location_id=location_id)

    url = f"https://services.leadconnectorhq.com/locations/{location_id}/customFields?model=all"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        messages.error(request, "Failed to fetch custom fields from GHL.")
        return redirect("Onboard:list_custom_fields", location_id=location_id)

    data = response.json()
    ghl_fields = data.get("customFields", [])


    new_count, updated_count = 0, 0

    for field in ghl_fields:
        field_id = field.get("id")
        name = field.get("name")
        field_key = field.get("fieldKey")
        data_type = field.get("dataType")
        model = field.get("model")

        existing_field = CustomField.objects.filter(location=integration, field_id=field_id).first()

        if existing_field:
            if (
                existing_field.name != name
                or existing_field.field_key != field_key
                or existing_field.data_type != data_type
                or existing_field.model != model
            ):
                existing_field.name = name
                existing_field.field_key = field_key
                existing_field.data_type = data_type
                existing_field.model = model
                existing_field.save(update_fields=["name", "field_key", "data_type", "model"])
                updated_count += 1
        else:
            CustomField.objects.create(
                location=integration,
                field_id=field_id,
                name=name,
                field_key=field_key,
                data_type=data_type,
                model=model,
            )
            new_count += 1

    messages.success(
        request,
        f"Sync complete — {new_count} new fields added, {updated_count} updated."
    )

    return redirect("Onboard:list_custom_fields", location_id=location_id)
