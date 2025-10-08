from django.shortcuts import render, redirect
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.http import JsonResponse
import requests
from django.contrib import messages
import uuid
import os
import requests
from .models import IntegrationToken, CustomField, Pdf
from django.template.loader import render_to_string
from .utils import get_valid_access_token
from .models import IntegrationToken,CustomField,Pdf
from .utils import get_valid_access_token
from django.views.decorators.http import require_GET
from xhtml2pdf import pisa




CLIENT_ID = settings.CLIENT_ID
CLIENT_SECRET = settings.CLIENT_SECRET
REDIRECT_URI = settings.REDIRECT_URI


def Login(request):
    
    locations = IntegrationToken.objects.all().order_by("name")
    return render(request,"onBoard.html",{"locations":locations})


def authorize(request):
    scope = (
        "contacts.readonly%20"
        "contacts.write%20"
        "opportunities.readonly%20"
        "locations.readonly%20"
        "locations/customFields.readonly%20"
        "locations/customValues.readonly%20"
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

    if request.method == "POST":
        code = request.POST.get("code")
        location_id = request.POST.get("location_id")
   

        token_url = "https://services.leadconnectorhq.com/oauth/token"
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
        }

        token_response = requests.post(token_url, data=data)
        tokens = token_response.json()

        if "access_token" not in tokens:
            print("Access token missing in response!")
            return render(request, "form.html", {"error": "Failed to get tokens"})

        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        expires_in = tokens.get("expires_in", 3600)
        expires_at = timezone.now() + timedelta(seconds=expires_in)

         # Fetch location details using the access token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Version": "2021-07-28"
        }
        location_url = f"https://services.leadconnectorhq.com/locations/{location_id}"

        loc_resp = requests.get(location_url, headers=headers)
        print('aaaaaaaaaaaaaaaaaaaaaaaaaa',loc_resp.json())
        if loc_resp.status_code != 200:
            return render(request, "form.html", {"error": "Failed to fetch location details"})
        
        loc_data = loc_resp.json().get("location", {})
        
        integration, created = IntegrationToken.objects.update_or_create(
            location_id=location_id,
            defaults={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "name": loc_data.get("name"),
                "phone": loc_data.get("phone"),
                "address": loc_data.get("address"),
                "website": loc_data.get("website"),
            },
        )
        print("Token saved to DB. Created new:", created)

        return redirect("fetch_custom_fields", location_id=location_id)

    return render(request, "form.html")



def fetch_custom_fields(request, location_id):
    access_token = get_valid_access_token(location_id)
    if not access_token:
        return render(request, "form.html", {"error": "Failed to get valid access token"})

    url = f"https://services.leadconnectorhq.com/locations/{location_id}/customFields?model=all"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return render(request, "form.html", {"error": "Failed to fetch custom fields"})

    data = response.json()
    print('ccccccccccccccccccccccccccccccccccccccccccccccccc',data)

    if "customFields" not in data:
        return render(request, "form.html", {"error": "No custom fields found"})

    integration = IntegrationToken.objects.get(location_id=location_id)

    for field in data["customFields"]:

        exists = CustomField.objects.filter(location=integration, field_id=field.get("id")).exists()
        if not exists:
            CustomField.objects.create(
                location=integration,
                field_id=field.get("id"),
                name=field.get("name"),
                field_key=field.get("fieldKey"),
                data_type=field.get("dataType"),
                model=field.get("model"),
            )

    return redirect("list_custom_fields", location_id=location_id)



def list_custom_fields(request, location_id):
    try:
        integration = IntegrationToken.objects.get(location_id=location_id)
    except IntegrationToken.DoesNotExist:
        return render(request, "custom_fields.html", {"message": "Integration not found"})

    custom_fields = integration.custom_fields.all()
    return render(request, "custom_fields.html", {"custom_fields": custom_fields})





def toggle_custom_fields(request, location_id):
    if request.method == "POST":
        field_ids = request.POST.getlist("field_ids")
        action = request.POST.get("action")

        if not field_ids:
            messages.warning(request, "Please select at least one custom field.")
            return redirect("list_custom_fields", location_id=location_id)

        is_checked = True if action == "check" else False

        CustomField.objects.filter(id__in=field_ids).update(is_checked=is_checked)
        messages.success(request, f"{'Checked' if is_checked else 'Unchecked'} {len(field_ids)} custom field(s).")

    return redirect("list_custom_fields", location_id=location_id)




def CustomValue_pdf_view(request, location_id, opportunity_id):

    access_token = get_valid_access_token(location_id)
    if not access_token:
        return JsonResponse({"error": "Failed to get access token"}, status=400)

    try:
        integration = IntegrationToken.objects.get(location_id=location_id)
    except IntegrationToken.DoesNotExist:
        return JsonResponse({"error": "Integration not found"}, status=404)

    headers = {"Authorization": f"Bearer {access_token}", "Version": "2021-07-28"}

    opp_url = f"https://services.leadconnectorhq.com/opportunities/{opportunity_id}"
    resp = requests.get(opp_url, headers=headers)
    if resp.status_code != 200:
        return JsonResponse({"error": "Failed to fetch opportunity"}, status=resp.status_code)

    opp_data = resp.json().get("opportunity", {})
    opp_custom_fields = opp_data.get("customFields", [])

    contact_custom_fields = []
    contact_id = opp_data.get("contactId")
    if contact_id:
        contact_url = f"https://services.leadconnectorhq.com/contacts/{contact_id}?locationId={location_id}"
        contact_resp = requests.get(contact_url, headers=headers)
        if contact_resp.status_code == 200:
            contact_data = contact_resp.json().get("contact", {})
            contact_custom_fields = contact_data.get("customFields", [])

    checked_fields = CustomField.objects.filter(location=integration, is_checked=True)

    pdf_data = [["Name", "Value"]]  
    for field in checked_fields:
        value = ""
        if field.model == "opportunity":
            value = next((f.get("fieldValue", "") for f in opp_custom_fields if f.get("id") == field.field_id), "")
        elif field.model == "contact":
            value = next((f.get("value", "") for f in contact_custom_fields if f.get("id") == field.field_id), "")
        pdf_data.append([field.name, value])

    Pdf.objects.update_or_create(
        location=integration,
        opportunity_id=opportunity_id,
        defaults={"data": pdf_data}
    )


     # Render HTML template
    html_string = render_to_string(
        "pdf_customValue.html",
        {
            "integration": integration,
            "pdf_data": pdf_data[1:],  # skip header row
            "generated_at": timezone.now(),
        }
    )

    # Ensure PDF directory exists
    pdf_dir = os.path.join(settings.MEDIA_ROOT, "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_filename = f"{uuid.uuid4()}.pdf"
    full_path = os.path.join(pdf_dir, pdf_filename)

    # Generate PDF using xhtml2pdf
    with open(full_path, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(src=html_string, dest=pdf_file)
        if pisa_status.err:
            return JsonResponse({"error": "Failed to generate PDF"}, status=500)

    # Build URL
    pdf_url = request.build_absolute_uri(f"{settings.MEDIA_URL}pdfs/{pdf_filename}")

    return JsonResponse({
        "message": "PDF generated successfully",
        "pdf_url": pdf_url
    })