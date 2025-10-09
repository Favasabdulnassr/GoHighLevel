from django.urls import path
from .import views

app_name = "Updates"
urlpatterns = [
    path('custom-fields/<str:location_id>/update-logo/',views.update_logo,name='update_logo'),
    path("<str:location_id>/sync-latest-fields/", views.sync_latest_fields, name="sync_latest_fields"),

]
