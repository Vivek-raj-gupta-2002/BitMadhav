from django.http import HttpResponse
from rest_framework.decorators import api_view
from twilio.twiml.voice_response import VoiceResponse

@api_view(['POST'])
def handle_incoming_call(request):
    response = VoiceResponse()
    response.say("Welcome to BitMadhav.")
    
    xml_response = str(response).strip()  # Ensure no leading/trailing spaces
    return HttpResponse(xml_response, content_type='application/xml')
