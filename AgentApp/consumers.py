import os
import json
import base64
import asyncio
import websockets
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

# OpenAI Configuration
VOICE = "alloy"
SYSTEM_MESSAGE = "You are a helpful restaurant assistant. Answer questions about reservations and orders succinctly."

class MediaStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.stream_sid = None
        self.audio_buffer = bytearray()
        await self.send(text_data=json.dumps({"event": "connected"}))

    async def disconnect(self, close_code):
        self.audio_buffer.clear()

    async def receive(self, text_data):
        data = json.loads(text_data)
        event = data.get("event")

        if event == "start":
            await self.handle_start(data)
        elif event == "media":
            await self.handle_media(data)
        elif event == "stop":
            await self.handle_stop()

    async def handle_start(self, data):
        self.stream_sid = data["start"].get("streamSid")
        self.audio_buffer.clear()
        await self.send(text_data=json.dumps({"event": "start_received", "streamSid": self.stream_sid}))

    async def handle_media(self, data):
        payload = data["media"].get("payload")
        if payload:
            self.audio_buffer.extend(base64.b64decode(payload))

            if len(self.audio_buffer) > 16000 * 2:  # Process every 2 seconds
                await self.process_audio()

    async def handle_stop(self):
        if self.audio_buffer:
            await self.process_audio()
        await self.send(text_data=json.dumps({"event": "stop_received"}))

    async def process_audio(self):
        question = await self.transcribe_audio(self.audio_buffer)
        answer = await self.generate_answer(question)
        self.audio_buffer.clear()

        fake_audio_payload = base64.b64encode(answer.encode("utf-8")).decode("utf-8")
        await self.send(json.dumps({
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {"payload": fake_audio_payload}
        }))

    async def transcribe_audio(self, audio_data):
        async with websockets.connect(
            'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01-preview',
            extra_headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:
            await openai_ws.send(audio_data)
            response = await openai_ws.recv()
            return json.loads(response).get("text", "")

    async def generate_answer(self, question):
        async with websockets.connect(
            'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01-preview',
            extra_headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:
            payload = json.dumps({
                "messages": [
                    {"role": "system", "content": SYSTEM_MESSAGE},
                    {"role": "user", "content": question}
                ]
            })
            await openai_ws.send(payload)
            response = await openai_ws.recv()
            return json.loads(response).get("choices", [{}])[0].get("message", {}).get("content", "")
