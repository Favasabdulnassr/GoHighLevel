from django.urls import path
from . import views

urlpatterns = [
    path("",views.Login,name="login"),
    path('authorize/', views.authorize, name='authorize'),
    path("callback/", views.callback, name="callback"),
    path("submit-location/", views.submit_location, name="submit_location"),
    path("fetch-custom-fields/<str:location_id>/", views.fetch_custom_fields, name="fetch_custom_fields"),
    path("list-custom-fields/<str:location_id>/", views.list_custom_fields, name="list_custom_fields"),
    path("custom-fields/<str:location_id>/toggle/", views.toggle_custom_fields, name="toggle_custom_fields"),
    path('checked-fields/<str:location_id>/', views.get_checked_contact_fields, name='get_checked_contact_fields'),

    ]
