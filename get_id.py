import urllib.request
import re

url = "https://www.youtube.com/@vaibhavsisinty"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    match = re.search(r'"browseId":"(UC[a-zA-Z0-9_-]+)"', html)
    if match:
        print(f"CHANNEL_ID: {match.group(1)}")
    else:
        print("Channel ID not found in HTML")
except Exception as e:
    print(f"Error: {e}")
