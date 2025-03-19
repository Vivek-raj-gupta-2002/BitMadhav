from django.http import HttpResponse
from rest_framework.decorators import api_view
from twilio.twiml.voice_response import VoiceResponse

@api_view(['POST'])
def handle_incoming_call(request):
    response = VoiceResponse()
    response.say("Welcome to BitMadhav.")
    return HttpResponse(str(response), content_type='text/xml')
