from django.urls import path
from .views import handle_incoming_call

urlpatterns = [
    path('api/incoming-call/', handle_incoming_call, name='incoming-call'),
]