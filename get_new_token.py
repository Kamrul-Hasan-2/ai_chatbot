"""
Quick Token Regeneration Script
Helps you get a new Facebook Page Access Token
"""
import webbrowser
import pyperclip
from dotenv import load_dotenv, set_key
import os

print("=" * 70)
print("  🔑 Facebook Page Access Token - Quick Fix")
print("=" * 70)

print("\n📋 Step-by-step guide:\n")

print("1️⃣  I'll open Facebook Developers for you...")
print("   → Opening browser in 3 seconds...\n")

import time
time.sleep(3)

# Open Facebook Developers
webbrowser.open('https://developers.facebook.com/apps')

print("2️⃣  In the browser:")
print("   a) Select your app")
print("   b) Click 'Messenger' in left sidebar")
print("   c) Click 'Settings'")
print("   d) Scroll to 'Access Tokens'")
print("   e) Select your Facebook Page")
print("   f) Click 'Generate Token'")
print("   g) COPY the token (starts with EAA...)")
print()

# Get token from user
print("3️⃣  Paste your NEW token here:")
new_token = input("   Token: ").strip()

if new_token and new_token.startswith('EAA'):
    # Update .env file
    env_path = '.env'
    
    try:
        # Read current .env
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Update PAGE_ACCESS_TOKEN line
        with open(env_path, 'w', encoding='utf-8') as f:
            for line in lines:
                if line.startswith('PAGE_ACCESS_TOKEN='):
                    f.write(f'PAGE_ACCESS_TOKEN={new_token}\n')
                else:
                    f.write(line)
        
        print("\n✅ Token updated successfully in .env file!")
        print("\n4️⃣  Next steps:")
        print("   → Restart your server (Ctrl+C then run again)")
        print("   → Test: python test_messenger_connection.py")
        print("   → Message your Facebook Page to test!")
        print("\n" + "=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error updating .env: {e}")
        print(f"\nManual fix:")
        print(f"1. Open .env file")
        print(f"2. Replace PAGE_ACCESS_TOKEN with: {new_token}")
        print(f"3. Save file")
        print(f"4. Restart server")
        
else:
    print("\n❌ Invalid token!")
    print("   Token should start with 'EAA' and be very long")
    print("\n   Manual fix:")
    print("   1. Open .env file")
    print("   2. Update line 2: PAGE_ACCESS_TOKEN=YOUR_NEW_TOKEN")
    print("   3. Save file")
    print("   4. Restart server")

print("\n" + "=" * 70)
