from django.urls import path
from .views import incoming_call, reservation_details, cancel_reservation

urlpatterns = [
    path('incoming-call', incoming_call, name='incoming-call'),
    path('reservation/<str:phone_number>/<int:reservation_id>/', reservation_details, name='get-reservation'),
    path('reservation/cancel/<str:phone_number>/<int:reservation_id>/', cancel_reservation, name='cancel-reservation'),

]