import os, json, urllib.request, urllib.error
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    print('❌ GEMINI_API_KEY not found in .env')
    exit(1)

url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}'
data = json.dumps({'contents': [{'parts': [{'text': 'Hello'}]}]}).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        print('✅ API is ACTIVE! Your quota is available.')
except urllib.error.HTTPError as e:
    print(f'❌ API Error {e.code}: {e.read().decode()}')
except Exception as e:
    print(f'❌ Request failed: {e}')