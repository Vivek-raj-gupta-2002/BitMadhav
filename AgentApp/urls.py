from django.urls import path
from .views import incoming_call

urlpatterns = [
    path('incoming-call', incoming_call, name='incoming-call'),
]