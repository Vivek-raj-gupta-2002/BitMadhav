from django.urls import re_path
from AgentApp import consumers

websocket_urlpatterns = [
    re_path(r"^ws/media-stream/$", consumers.MediaStreamConsumer.as_asgi()),
]
