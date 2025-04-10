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
from django.utils.timezone import localdate
from datetime import datetime, timedelta
from openai import AzureOpenAI
from twilio.rest import Client
import requests

# Configuration variables from Django settings
OPENAI_API_KEY = settings.OPENAI_API_KEY
ENDPOINT = settings.ENDPOINT
AZURE_ENDPOINT = settings.AZURE_ENDPOINT
SMS_KEY = settings.SMS_KEY


# System message to guide the AI's tone and behavior
SYSTEM_MESSAGE = """
You are BitMadhav, an AI assistant for a restaurant located at **Gopur Square, Indore, India**. Your responsibilities include:
**Time Standard**: Indian Standard Time(Asia/Kolkata)
Currency: INR
1. **Table Reservations**:
   - Accept reservations only between **5:00 PM and 9:00 PM** (17:00 to 21:00) and at least **1 hour from the current time**.
   - Allow bookings **only for today or tomorrow**.
   - **Details for reservations**:
        - Name
        - date(YYYY-MM-DD)
        - time(HH:MM:SS)
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
2. Validate availability using the information of reservation '**Current Reservations**' only.
3. If available, confirm the reservation. Otherwise, suggest the closest available time.

Note: We are not talking food orders right now!!
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
            self.reservation = {'name': None, 'guests': None, 'date': None, 'time': None, 'phone': None}

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
                self.reservation['phone'] = self.caller_number

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
                    user_data = await self.extract_reservation_details(response.get('transcript'))
                    
                    if user_data != None:

                        if user_data['name'] != '':
                            self.reservation['name'] = user_data['name']

                        if user_data['guests'] != 0:
                            self.reservation['guests'] = user_data['guests']

                        if user_data['date'] != '':
                            self.reservation['date'] = user_data['date']

                        if user_data['time'] != '':
                            self.reservation['time'] = user_data['time']

                    reserv_condition = (
                        self.reservation['name'] not in (None, '')
                        and self.reservation['guests'] not in (None, 0)
                        and self.reservation['date'] not in (None, '')
                        and self.reservation['time'] not in (None, '')
                        and self.reservation['phone'] != None
                    )
                    print(self.reservation)
                    if reserv_condition:
                        table_instance = await sync_to_async(models.Table.objects.create)(**self.reservation)
                        
                        await self.send_sms(table_instance)
                        

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

        reservations = await self.get_reservations()
        updated_session = SYSTEM_MESSAGE + f"\n\nCurrent Reservations:\n{reservations}"
        session_update = {
            "type": "session.update",
            "session": {
                "turn_detection": {"type": "server_vad"},
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "voice": VOICE,
                "instructions": updated_session,
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
    
    @sync_to_async
    def get_reservations(self):
        today = localdate()
        tomorrow = today + timedelta(days=1)
        
        reservations = models.Table.objects.filter(date__in = [today, tomorrow])

        formatted_reservations = "\n".join(
            f"- {r.name}: {r.date} at {r.time} for {r.num_guests} guests"
            for r in reservations
        )
        return formatted_reservations if formatted_reservations else "No reservations yet."

    @sync_to_async
    def extract_reservation_details(self, transcript):
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_ENDPOINT,
            api_key=OPENAI_API_KEY,
            api_version='2025-01-01-preview'  # Use a stable version
        )
        
        response = self.client.chat.completions.create(
            model="gpt-4o",  # Use actual deployed model name from Azure
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract restaurant reservation details (name, guests, date(YYYY-MM-DD), time(HH:MM:SS)) accurately from the given text. "
                        "If a value is missing, return an empty string without making up values. "
                        "Use the Indian Time Asia/Kolkata"
                        "Extract the date if user says today and tommarow according to IST"
                    )
                },
                {"role": "user", "content": transcript}
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "extract_reservation_info",
                        "description": "Extracts reservation details such as name, number of guests, date, time.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Customer's full name if provided, otherwise empty."},
                                "guests": {"type": "integer", "description": "Number of guests if mentioned, otherwise 0."},
                                "date": {"type": "string", "format": "date", "description": "Reservation date (YYYY-MM-DD) if available, otherwise empty."},
                                "time": {"type": "string", "format": "time", "description": "Reservation time (HH:MM) if mentioned, otherwise empty."},
                                "phone": {"type": "string", "description": "Customer's phone number if given, otherwise empty."}
                            },
                            "required": ["name", "guests", "date", "time"]
                        }
                    }
                }
            ],
            tool_choice="auto",  # Let Azure decide when to use the function
        )


        try:
            result = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
            return result
        except Exception as e:
            print(f"Error parsing response: {e}")
            return None

    @sync_to_async  
    def send_sms(self, message_info):
        req_url = 'https://www.fast2sms.com/dev/bulkV2'
        

        view_link = f"https://{settings.HOST}/api/reservation/{message_info.phone}/{message_info.id}/"

        message = (
            f"Reservation Details: {view_link}"
        )

        headers = {
            'cache-control': "no-cache"
        }
        number = message_info.phone.replace('+91', "")

        params = {
            'authorization': settings.SMS_KEY,
            "message": message,
            "language": "english",
            "route": "q",
            "numbers": number,
        }


        response = requests.get(req_url, headers=headers, params=params)

        print("SMS Response:", response.status_code, response.text)
        return response
