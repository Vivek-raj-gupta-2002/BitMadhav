from rest_framework.decorators import api_view
from rest_framework.response import Response
from twilio.twiml.voice_response import VoiceResponse

@api_view(['POST'])
def handle_incoming_call(request):
    response = VoiceResponse()
    response.say("Welcome to BitMadhav.")
    
    return Response(str(response), content_type='text/xml')