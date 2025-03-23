import json
import base64
import io
from openai import AzureOpenAI
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

# Azure OpenAI Configuration
VOICE = "alloy"
SYSTEM_MESSAGE = "You are a helpful restaurant assistant. Answer questions about reservations and orders succinctly."

# Initialize AzureOpenAI Clients
client_whisper = AzureOpenAI(api_key=settings.OPENAI_API_KEY, api_version='2024-06-01', azure_endpoint=settings.WISPER_ENDPOINT)
client_chat = AzureOpenAI(api_key=settings.OPENAI_API_KEY, api_version=settings.API_VERSION, azure_endpoint=settings.ENDPOINT)

class MediaStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.stream_sid = None
        self.audio_buffer = bytearray()
        await self.send_json({"event": "connected"})

    async def disconnect(self, close_code):
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
        question = await self.transcribe_audio(self.audio_buffer)
        self.audio_buffer.clear()

        if question:
            answer = await self.generate_answer(question)
            await self.send_audio(answer)

    async def transcribe_audio(self, audio_bytes):
        try:
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "audio.wav"

            response = client_whisper.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                
            )
            return response.text
        except Exception as e:
            await self.send_json({"event": "error", "message": f"Transcription failed: {str(e)}"})
            return ""

    async def generate_answer(self, question):
        try:
            response = client_chat.chat.completions.create(
                model="gpt-4o-realtime-preview",
                messages=[
                    {"role": "system", "content": SYSTEM_MESSAGE},
                    {"role": "user", "content": question}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            await self.send_json({"event": "error", "message": f"Chat generation failed: {str(e)}"})
            return "I'm sorry, I couldn't process your request."

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