# How to Update Server with Fixed Code

## The Issue
Your server is running old code that only accepts POST to /test.
The code on your Windows machine is already fixed.

## Solution: Upload the updated file

### Method 1: Using SCP (from Windows PowerShell)

Run this command from Windows:
```powershell
cd C:\Users\BLG\Desktop\ai_chatbot
scp src/api/app_simple.py root@128.199.144.145:/root/ai_services/ai_chatbot/src/api/app_simple.py
```

Enter your server password when prompted.

### Method 2: Using PowerShell Script

```powershell
.\upload_to_server.ps1
```

### Method 3: Manual Copy-Paste (if SCP doesn't work)

1. Open: `C:\Users\BLG\Desktop\ai_chatbot\src\api\app_simple.py`
2. Copy all content (Ctrl+A, Ctrl+C)
3. On server, run:
   ```bash
   nano /root/ai_services/ai_chatbot/src/api/app_simple.py
   ```
4. Delete all content (Ctrl+K multiple times)
5. Paste new content (right-click or Ctrl+Shift+V)
6. Save (Ctrl+O, Enter, Ctrl+X)

### Method 4: Using Git (if you have a repository)

On server:
```bash
cd /root/ai_services/ai_chatbot
git pull
```

## After Uploading - Restart Server

On your Linux server:
```bash
# Stop current server
pkill -f gunicorn

# Start with new code
cd /root/ai_services/ai_chatbot
gunicorn -c config/gunicorn_config.py src.api.app_simple:app
```

## Verify It Works

Open browser: http://128.199.144.145:5000/test

You should see the chat interface!

## What Changed

The `/test` route now:
- ✅ Accepts GET requests (shows chat interface)
- ✅ Accepts POST requests (processes messages)
- ✅ Has proper static file serving

Before:
```python
@app.route('/test', methods=['POST'])
def test():
    return chat()
```

After:
```python
@app.route('/test', methods=['GET', 'POST'])
def test():
    if request.method == 'GET':
        return send_from_directory(STATIC_FOLDER, 'chat.html')
    return chat()
```
