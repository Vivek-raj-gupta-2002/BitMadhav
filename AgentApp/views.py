from django.http import HttpResponse
from django.shortcuts import render, redirect
from .models import Sid, Table
from twilio.twiml.voice_response import VoiceResponse, Connect
from django.shortcuts import render, get_object_or_404

def incoming_call(request):
    """
    Handles incoming calls:
      - Greets the caller.
      - Opens a WebSocket Media Stream to our Channels consumer.
      - Sends the caller's phone number via WebSocket.
    """
    # Capture the caller's phone number
    caller_number = request.GET.get('Caller', 'Unknown')
    call_sid = request.GET.get('CallSid', 'Unknown')
    print(f"Incoming call from: {caller_number}, CallSid: {call_sid}")

    # Create or update the Sid model
    Sid.objects.update_or_create(phone_number=caller_number, defaults={'callsid': call_sid})


    response = VoiceResponse()
    response.say("Welcome to BitMadhav! How may I help you today?", voice="alice")

    # Set up the WebSocket connection and pass caller_number as a query parameter
    connect = Connect()
    host = request.get_host()
    connect.stream(url=f"wss://{host}/ws/media-stream/")
    response.append(connect)

    return HttpResponse(str(response), content_type="application/xml")


def reservation_details(request, phone_number, reservation_id):
    reservation = get_object_or_404(Table, id=reservation_id, phone=phone_number)
    return render(request, 'res.html', {'reservation': reservation})
    
def cancel_reservation(request, reservation_id, phone_number):
    reservation = get_object_or_404(Table, id=reservation_id, phone=phone_number)
    reservation.delete()  # or update a status field instead of deleting
    return render(request, 'cancel_confirmation.html', {
        'reservation_id': reservation_id,
        'phone': phone_number,
    })
