import json
import base64
import io
import asyncio
import websockets
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

# Azure OpenAI Configuration
VOICE = "alloy"
SYSTEM_MESSAGE = "You are a helpful restaurant assistant. Answer questions about reservations and orders succinctly."

class MediaStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.stream_sid = None
        self.audio_buffer = bytearray()
        print('Connected....')
        await self.send_json({"event": "connected"})

    async def disconnect(self, close_code):
        print('Disconnected....')
        self.audio_buffer.clear()

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            event = data.get("event")

            if event == "start":
                await self.handle_start(data)
            elif event == "media":
                await self.handle_media(data)
            elif event == "stop":
                await self.handle_stop()
        except (json.JSONDecodeError, KeyError) as e:
            await self.send_json({"event": "error", "message": str(e)})

    async def handle_start(self, data):
        self.stream_sid = data["start"].get("streamSid")
        self.audio_buffer.clear()
        await self.send_json({"event": "start_received", "streamSid": self.stream_sid})

    async def handle_media(self, data):
        payload = data.get("media", {}).get("payload")
        if payload:
            self.audio_buffer.extend(base64.b64decode(payload))

            if len(self.audio_buffer) >= 32000:  # Process audio every ~2 seconds
                await self.process_audio()

    async def handle_stop(self):
        if self.audio_buffer:
            await self.process_audio()
        await self.send_json({"event": "stop_received"})

    async def process_audio(self):
        question = await self.transcribe_and_generate(self.audio_buffer)
        self.audio_buffer.clear()

        if question:
            await self.send_audio(question)

    async def transcribe_and_generate(self, audio_bytes):
        try:
            async with websockets.connect(
                'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17',
                extra_headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "OpenAI-Beta": "realtime=v1"
                }
            ) as openai_ws:

                # Initialize session
                session_update = {
                    "type": "session.update",
                    "session": {
                        "turn_detection": {"type": "server_vad"},
                        "input_audio_format": "pcm_mulaw",
                        "output_audio_format": "pcm_mulaw",
                        "voice": VOICE,
                        "instructions": SYSTEM_MESSAGE,
                        "modalities": ["text", "audio"],
                        "temperature": 0.8,
                    }
                }
                await openai_ws.send(json.dumps(session_update))

                # Send audio data
                audio_payload = base64.b64encode(audio_bytes).decode("utf-8")
                await openai_ws.send(json.dumps({
                    "type": "data",
                    "data": {
                        "audio": audio_payload
                    }
                }))

                # Receive and process the AI's response
                response = await openai_ws.recv()
                response_data = json.loads(response)

                return response_data.get("response", {}).get("text", "")

        except Exception as e:
            await self.send_json({"event": "error", "message": f"Processing failed: {str(e)}"})
            return ""

    async def send_audio(self, text):
        try:
            audio_payload = base64.b64encode(text.encode("utf-8")).decode("utf-8")
            await self.send_json({
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": audio_payload}
            })
        except Exception as e:
            await self.send_json({"event": "error", "message": f"Audio send failed: {str(e)}"})

    async def send_json(self, message):
        await self.send(text_data=json.dumps(message))
