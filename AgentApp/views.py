from django.http import HttpResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
from django.conf import settings

def incoming_call(request):
    """
    Returns TwiML for an incoming call:
      - Says a greeting.
      - Opens a WebSocket Media Stream to our Channels consumer.
    """
    response = VoiceResponse()
    response.say("Welcome to BitMadhav! How May I help you Today!", voice="alice")
    
    # Use your domain (or ngrok during development)
    host = request.get_host()
    connect = Connect()
    connect.stream(url=f"wss://{host}/ws/media-stream/")
    response.append(connect)
    
    return HttpResponse(str(response), content_type="application/xml")
