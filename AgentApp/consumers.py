from channels.generic.websocket import AsyncWebsocketConsumer
import os
import base64
import json
import websockets
import asyncio
from urllib.parse import parse_qs
from django.conf import settings
from AgentApp import models
from asgiref.sync import sync_to_async

# Configuration variables from Django settings
OPENAI_API_KEY = settings.OPENAI_API_KEY
ENDPOINT = settings.ENDPOINT

# System message to guide the AI's tone and behavior
SYSTEM_MESSAGE = """
You are BitMadhav, an AI assistant for a restaurant located at **Gopur Square, Indore, India**. Your responsibilities include:

1. **Table Reservations**:
   - Accept reservations only between **5:00 PM and 9:00 PM** (17:00 to 21:00) and at least **1 hour from the current time**.
   - Allow bookings **only for today or tomorrow**.
   - **Details for reservations**:
        - Name
        - date
        - time
        - number of guests
   - Ensure **no overlapping reservations** within **1 to 1.5 hours** of any confirmed booking.  
     Example: If a reservation is made at 6:00 PM, other bookings between **5:00 PM and 7:30 PM** are not allowed.

2. **Information Collection**:
   - Customer Name (e.g., John Doe)
   - Reservation Date & Time (within the allowed hours for today or tomorrow)
   - Guest Count (number of people)

3. **Validation & Confirmation**:
   - Check for **existing reservations** to prevent overlaps.
   - If the requested time is available, **confirm the booking** and share the reservation details.
   - If unavailable, **suggest alternative time slots** within open hours.

4. **Common Restaurant Inquiries**:
   - Handle questions about:
     - **Operating hours**: 11:00 AM – 10:00 PM (Reservations: 5:00 PM – 9:00 PM)
     - **Location**: Gopur Square, Indore, India
     - **Currency**: INR
     - **Contact details**: Available upon request
     - **Special offers**: Seasonal discounts and group offers available
     - **Reservation policies**: Advance booking required within allowed hours

5. **Menu**:
   - **Starters**:
     - Paneer Tikka (₹250)
     - Veg Manchurian (₹220)
     - Chicken Tandoori (₹350)
   - **Main Course**:
     - Butter Chicken (₹400)
     - Paneer Butter Masala (₹320)
     - Dal Tadka (₹180)
     - Veg Biryani (₹280)
   - **Breads**:
     - Butter Naan (₹50)
     - Garlic Naan (₹70)
   - **Desserts**:
     - Gulab Jamun (₹120)
     - Ice Cream (₹100)
   - **Beverages**:
     - Masala Chai (₹50)
     - Cold Coffee (₹150)

6. **Language & Tone**:
   - Communicate in **multiple Indian languages**, including **Hinglish**.
   - Always be **polite, clear, and efficient** when assisting customers.

When handling reservations:
1. Confirm the customer’s details clearly.
2. Validate availability.
3. If available, confirm the reservation. Otherwise, suggest the closest available time.
"""


# Voice configuration for OpenAI responses
VOICE = 'alloy'

# Event types to monitor for logging purposes
LOG_EVENT_TYPES = [
    'response.content.done', 'rate_limits.updated', 'response.done',
    'input_audio_buffer.committed', 'input_audio_buffer.speech_stopped',
    'input_audio_buffer.speech_started', 'session.created'
]

class MediaStreamConsumer(AsyncWebsocketConsumer):
    """
    This consumer manages real-time WebSocket communication between:
    1. Twilio (for receiving audio and sending AI responses)
    2. OpenAI (for processing audio input and generating audio output)
    """

    async def connect(self):
        """
        Handles the WebSocket connection initialization.
        Input: None
        Output: Accepts WebSocket connection and starts communication with OpenAI.
        """

        await self.accept()

        try:
            # Establish connection with OpenAI real-time WebSocket
            self.openai_ws = await websockets.connect(
                ENDPOINT,
                additional_headers={
                    "api-key": OPENAI_API_KEY,
                }
            )
            await self.send_session_update()  # Send initial session settings to OpenAI

            self.stream_sid = None  # Initialize stream ID for Twilio
            self.caller_number = None

            # Start background task to process OpenAI responses
            self.openai_task = asyncio.create_task(self.send_to_twilio())
        except Exception as e:
            print(f"Error establishing OpenAI WebSocket: {e}")

    async def receive(self, text_data):
        """
        Handles incoming messages from the WebSocket (e.g., Twilio audio stream).
        Input: JSON payload from Twilio WebSocket.
        Output: Forwards audio to OpenAI WebSocket if available.
        """
        try:
            data = json.loads(text_data)  # Parse incoming JSON data
            event = data.get("event")

            if event == "start":
                # print(data['start'][''])
                # Capture the stream ID when a new audio stream starts
                self.stream_sid = data['start']['streamSid']
                callid = data['start']['callSid']
                self.caller_number = await self.get_phone_number(callid)

            elif event == "media" and self.openai_ws.state:
                # Forward audio payload to OpenAI for processing
                audio_append = {
                    "type": "input_audio_buffer.append",
                    "audio": data['media']['payload']
                }
                await self.openai_ws.send(json.dumps(audio_append))

        except (json.JSONDecodeError, KeyError) as e:
            # Handle errors and notify the client
            await self.send_json({"event": "error", "message": str(e)})

    async def send_to_twilio(self):
        """
        Listens for OpenAI responses and forwards audio to Twilio.
        Input: Messages from OpenAI WebSocket.
        Output: Audio payload sent to Twilio WebSocket.
        """
        try:
            async for openai_message in self.openai_ws:
                response = json.loads(openai_message)  # Parse OpenAI response

                # Ignore logging events
                if response['type'] in LOG_EVENT_TYPES:
                    continue

                if response['type'] == 'response.audio_transcript.done' and response.get('transcript'):
                    print(response)

                # Handle audio output from OpenAI
                if response['type'] == 'response.audio.delta' and response.get('delta'):
                    
                    try:
                        # Convert audio to base64 and send to Twilio
                        audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                        audio_delta = {
                            "event": "media",
                            "streamSid": self.stream_sid,
                            "media": {
                                "payload": audio_payload
                            }
                        }
                        await self.send_json(audio_delta)
                    except Exception as e:
                        print(f"Error processing audio data: {e}")

        except Exception as e:
            print(f"Error in send_to_twilio: {e}")

    async def send_session_update(self):
        """
        Sends session configuration to OpenAI to define input/output settings.
        Input: None
        Output: Sends session update to OpenAI WebSocket.
        """
        session_update = {
            "type": "session.update",
            "session": {
                "turn_detection": {"type": "server_vad"},
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "voice": VOICE,
                "instructions": SYSTEM_MESSAGE,
                "modalities": ["text", "audio"],
                "temperature": 0.8,
            }
        }
        if self.openai_ws.state:
            await self.openai_ws.send(json.dumps(session_update))

    async def disconnect(self, close_code):
        """
        Handles the cleanup when a WebSocket connection is closed.
        Input: Close code from the WebSocket.
        Output: Closes OpenAI connection and cancels background tasks.
        """
        print("WebSocket disconnected.")

        # Close OpenAI WebSocket if open
        if hasattr(self, 'openai_ws') and self.openai_ws.state:
            await self.openai_ws.close()

        # Cancel OpenAI response processing task if active
        if hasattr(self, 'openai_task') and not self.openai_task.done():
            self.openai_task.cancel()
            try:
                await self.openai_task
            except asyncio.CancelledError:
                print("OpenAI listener task cancelled successfully.")

    async def send_json(self, message):
        """
        Sends a JSON message over the WebSocket.
        Input: Python dictionary to be sent.
        Output: JSON-encoded message sent to the client.
        """
        await self.send(text_data=json.dumps(message))

    @sync_to_async
    def get_phone_number(self, callSid):
        return models.Sid.objects.get(callsid = callSid).phone_number
