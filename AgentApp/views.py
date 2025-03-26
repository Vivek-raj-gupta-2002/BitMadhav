from django.http import HttpResponse
from .models import Sid
from twilio.twiml.voice_response import VoiceResponse, Connect

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
