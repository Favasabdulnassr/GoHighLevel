from django.urls import path
from . import views

urlpatterns = [
    path("",views.Login,name="login"),
    path('authorize/', views.authorize, name='authorize'),
    path("callback/", views.callback, name="callback"),
    path("submit_location/", views.submit_location, name="submit_location"),
    path('list_custom_fields/<str:location_id>/',views.list_custom_fields,name='list_custom_fields')
]
