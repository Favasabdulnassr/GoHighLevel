from django.shortcuts import render, redirect
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.http import JsonResponse
import requests
from django.contrib import messages
import uuid
import json
import requests
from .models import IntegrationToken, CustomField
from django.template.loader import render_to_string
from .utils import get_valid_access_token
from .models import IntegrationToken,CustomField
from .utils import get_valid_access_token
from django.views.decorators.http import require_GET
from xhtml2pdf import pisa
from PIL import Image
import base64
from io import BytesIO
import os





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
        "medias.write%20"
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
        logo_file = request.FILES.get("logo")
   

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
                "logo": logo_file if logo_file else None,
            },
        )
        print("Token saved to DB. Created new:", created)

        return redirect("Onboard:fetch_custom_fields", location_id=location_id)

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

    return redirect("Onboard:list_custom_fields", location_id=location_id)



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
            return redirect("Onboard:list_custom_fields", location_id=location_id)

        is_checked = True if action == "check" else False

        CustomField.objects.filter(id__in=field_ids).update(is_checked=is_checked)
        messages.success(request, f"{'Checked' if is_checked else 'Unchecked'} {len(field_ids)} custom field(s).")

    return redirect("Onboard:list_custom_fields", location_id=location_id)















def CustomField_PdF_Upload(request, location_id, opportunity_id):
    
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
    try:
        opp_json = resp.json()
    except Exception as e:
        opp_json = {}
    if resp.status_code != 200:
        return JsonResponse({"error": "Failed to fetch opportunity"}, status=resp.status_code)

    opp_data = opp_json.get("opportunity", {})
    opp_custom_fields = opp_data.get("customFields", [])
    contact_id = opp_data.get("contactId")

    contact_custom_fields = []
    if contact_id:
        contact_url = f"https://services.leadconnectorhq.com/contacts/{contact_id}?locationId={location_id}"
        contact_resp = requests.get(contact_url, headers=headers)
        try:
            contact_json = contact_resp.json()
        except Exception as e:
            contact_json = {}
        if contact_resp.status_code == 200:
            contact_data = contact_json.get("contact", {})
            contact_custom_fields = contact_data.get("customFields", [])

    def get_field_value(field_data, field_id, model_type):
        """Extract clean value from custom field, handling file uploads specially"""
        if model_type == "opportunity":
            field_value = next((f.get("fieldValue", "") for f in field_data if f.get("id") == field_id), "")
        else:  
            field_value = next((f.get("value", "") for f in field_data if f.get("id") == field_id), "")
        
        if isinstance(field_value, dict):
            for key, value in field_value.items():
                if isinstance(value, dict) and "documentId" in value:
                    file_url = value.get("url", "")
                    original_name = value.get("meta", {}).get("originalname", "")
                    
                    if file_url and original_name:
                        return f"File: {original_name}"
                    elif file_url:
                        return f"View File"
                    else:
                        return "File Uploaded"
            
            return str(field_value)
        
        return field_value if field_value else ""

    checked_fields = CustomField.objects.filter(location=integration, is_checked=True)
    pdf_data = [["Name", "Value"]]
    
    for field in checked_fields:
        value = get_field_value(
            opp_custom_fields if field.model == "opportunity" else contact_custom_fields,
            field.field_id,
            field.model
        )
        pdf_data.append([field.name, value])

    logo_base64 = None
    if integration.logo:
        try:
            img = Image.open(integration.logo.path)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            max_width, max_height = 160, 60
            img_ratio = img.width / img.height
            target_ratio = max_width / max_height
            if img_ratio > target_ratio:
                new_width = max_width
                new_height = int(max_width / img_ratio)
            else:
                new_height = max_height
                new_width = int(max_height * img_ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            img.save(buffer, format='PNG', optimize=True)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            logo_base64 = f"data:image/png;base64,{img_str}"
            print("Logo processed successfully")
        except Exception as e:
            print(f"Error processing logo: {e}")

    html_string = render_to_string(
        "pdf_customValue.html",
        {
            "integration": integration,
            "pdf_data": pdf_data[1:],
            "generated_at": timezone.now(),
            "logo_base64": logo_base64,
        }
    )

    pdf_dir = os.path.join(settings.MEDIA_ROOT, "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_filename = f"custom_fields_{opportunity_id}.pdf"
    full_path = os.path.join(pdf_dir, pdf_filename)

    with open(full_path, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(src=html_string, dest=pdf_file)
        if pisa_status.err:
            print("Error generating PDF:", pisa_status.err)
            return JsonResponse({"error": "Failed to generate PDF"}, status=500)

    upload_url = "https://services.leadconnectorhq.com/medias/upload-file"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
    }

    with open(full_path, "rb") as f:
        files = {
            "file": (pdf_filename, f, "application/pdf")
        }
        data = {
            "hosted": "false",
            "name": pdf_filename,
        }
        upload_resp = requests.post(upload_url, headers=headers, files=files, data=data)

    try:
        upload_json = upload_resp.json()
    except Exception as e:
        upload_json = {}
    if upload_resp.status_code != 201:
        return JsonResponse({"error": "Failed to upload PDF"}, status=upload_resp.status_code)

    file_url = upload_json.get("url")
    file_id = upload_json.get("fileId")
    if not file_url:
        return JsonResponse({"error": "No file URL returned"}, status=500)

    if contact_id:
        update_contact_url = f"https://services.leadconnectorhq.com/contacts/{contact_id}"
        
        location_fields_url = f"https://services.leadconnectorhq.com/locations/{location_id}/custom-fields"
        fields_resp = requests.get(location_fields_url, headers=headers)
        
        pdf_field_id = None
        pdf_field_key = None
        fields_data = {}
        
        if fields_resp.status_code == 200:
            fields_data = fields_resp.json()
            
            for field in fields_data.get("customFields", []):
                
                if field.get("dataType") == "FILE_UPLOAD" and "pdf" in field.get("name", "").lower():
                    pdf_field_id = field.get("id")
                    pdf_field_key = field.get("key")
                    break
                elif field.get("dataType") == "FILE_UPLOAD" and not pdf_field_id:
                    pdf_field_id = field.get("id")
                    pdf_field_key = field.get("key")
                    print(f"Found generic file upload field: {field.get('name')} with ID: {pdf_field_id}")
        else:
            print(f"Failed to fetch location custom fields. Status: {fields_resp.status_code}")
            print(f"Response: {fields_resp.text}")
        
        if not pdf_field_id and contact_custom_fields:
            for field in contact_custom_fields:
                field_id = field.get("id")
                field_value = field.get("value")

                if isinstance(field_value, dict) and any(
                    isinstance(v, dict) and "documentId" in v 
                    for v in field_value.values()
                ):
                    pdf_field_id = field_id
                    
                    for loc_field in fields_data.get("customFields", []):
                        if loc_field.get("id") == field_id:
                            pdf_field_key = loc_field.get("key")
                            break
                    break
        
        if not pdf_field_id:
            return JsonResponse({
                "error": "No FILE_UPLOAD custom field found. Please create one in your CRM settings.",
                "message": "PDF was uploaded but not attached to contact"
            }, status=400)

        file_uuid = str(uuid.uuid4())
        
        field_value = {
            file_uuid: {
                "meta": {
                    "fieldname": pdf_field_key or pdf_field_id,
                    "originalname": pdf_filename,
                    "encoding": "7bit",
                    "mimetype": "application/pdf",
                    "uuid": file_uuid,
                    "size": os.path.getsize(full_path) if os.path.exists(full_path) else 0
                },
                "url": file_url,
                "documentId": file_id
            }
        }
        
        custom_field_entry = {
            "id": pdf_field_id,
            "field_value": field_value
        }
        
        if pdf_field_key:
            custom_field_entry["key"] = pdf_field_key
        
        contact_payload = {
            "customFields": [custom_field_entry]
        }
        
     
        
        contact_resp = requests.put(
            update_contact_url, 
            headers={**headers, "Content-Type": "application/json"}, 
            json=contact_payload
        )
        
  
        
        try:
            contact_json = contact_resp.json()
            
            # Check if the file was actually added to custom fields
            updated_contact = contact_json.get("contact", {})
            updated_custom_fields = updated_contact.get("customFields", [])
            
            file_added = False
            for field in updated_custom_fields:
                if field.get("id") == pdf_field_id:
                    field_value = field.get("value", {})
                    if isinstance(field_value, dict) and file_id in str(field_value):
                        file_added = True
                        print(f"SUCCESS: File added to custom field {pdf_field_id}")
                        break
            
            if not file_added:
                print("WARNING: File may not have been added to custom fields")
                print(f"Updated custom fields: {json.dumps(updated_custom_fields, indent=2)}")
                
        except Exception as e:
            contact_json = {}
            print(f"Failed to parse contact update response: {e}")
            
        if contact_resp.status_code != 200:
            return JsonResponse({
                "error": "Failed to update contact", 
                "details": contact_resp.text,
                "status_code": contact_resp.status_code
            }, status=contact_resp.status_code)

    try:
        os.remove(full_path)
    except Exception as e:
        print(f"Failed to remove temporary PDF file: {e}")

    return JsonResponse({
        "message": "PDF generated, uploaded, and contact updated successfully",
        "pdf_url": file_url,
        "file_id": file_id,
        "contact_id": contact_id,
        "field_id": pdf_field_id
    })