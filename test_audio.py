import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="Hello world",
    config={"response_modalities": ["AUDIO"]}
)

for part in response.candidates[0].content.parts:
    if part.inline_data:
        print(f"Mime type: {part.inline_data.mime_type}")
        print(f"Data length: {len(part.inline_data.data)}")
        with open("test.wav", "wb") as f:
            f.write(part.inline_data.data)
