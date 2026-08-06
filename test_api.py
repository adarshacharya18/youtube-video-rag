import os, json, urllib.request, urllib.error
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
llm_model = os.getenv('GEMINI_MODEL', 'gemini-3.5-flash')
audio_model = os.getenv('GEMINI_AUDIO_MODEL', 'gemini-2.5-flash')
video_model = os.getenv('GEMINI_VIDEO_MODEL', 'veo-3.1')

if not api_key:
    print('❌ GEMINI_API_KEY not found in .env')
    exit(1)

print(f"--- Testing Base LLM API ({llm_model}) ---")
url = f'https://generativelanguage.googleapis.com/v1beta/models/{llm_model}:generateContent?key={api_key}'
data = json.dumps({'contents': [{'parts': [{'text': 'Hello'}]}]}).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        print('✅ Base LLM API is ACTIVE! Your quota is available.')
except urllib.error.HTTPError as e:
    print(f'❌ Base LLM API Error {e.code}: {e.read().decode()}')
except Exception as e:
    print(f'❌ Request failed: {e}')

print("\n--- Testing Gemini Voice/Video APIs via google-genai SDK ---")
try:
    from google import genai
    client = genai.Client(api_key=api_key)
    
    # Test Audio
    print(f"Testing Audio Generation ({audio_model})...")
    try:
        response = client.models.generate_content(
            model=audio_model,
            contents="Testing audio generation.",
            config={
                "response_modalities": ["AUDIO"],
                "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": "achird"}}}
            }
        )
        if hasattr(response, 'candidates') and response.candidates and response.candidates[0].content.parts:
            print("✅ Audio API is ACTIVE! Successfully generated audio response.")
        else:
            print("❌ Audio API succeeded but returned empty content.")
    except Exception as e:
        print(f"❌ Audio API Error: {e}")
        
    # Test Video
    print(f"\nTesting Video Generation ({video_model})...")
    try:
        response = client.models.generate_content(
            model=video_model,
            contents="A serene landscape with a river flowing.",
            config={}
        )
        if hasattr(response, 'candidates') and response.candidates and response.candidates[0].content.parts:
            print("✅ Video API is ACTIVE! Successfully received video generation response.")
        else:
            print("❌ Video API succeeded but returned empty content.")
    except Exception as e:
        print(f"❌ Video API Error: {e}")

except ImportError:
    print("❌ 'google-genai' package is not installed. Please run `pip install google-genai` to test Audio and Video generation APIs.")