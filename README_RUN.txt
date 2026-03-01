===========================================
  🚀 HOW TO RUN THIS PROJECT
===========================================

STEP 1: Install
---------------
Open PowerShell here and run:
  pip install -r requirements.txt


STEP 2: Start Server (Window 1)
--------------------------------
Double-click:
  ✅ RUN_PROJECT.bat

OR run in PowerShell:
  python app_integrated.py

You should see:
  ✓ Running on http://127.0.0.1:5000


STEP 3: Start ngrok (Window 2)
-------------------------------
Download: https://ngrok.com/download

Open NEW PowerShell and run:
  ngrok http 5000

Copy the HTTPS URL:
  Example: https://abc123.ngrok.io


STEP 4: Connect Facebook
-------------------------
Go to: https://developers.facebook.com/apps

Setup Webhook:
  Callback URL: https://abc123.ngrok.io/webhook
  Verify Token: my_verify_token_12345

Subscribe your page!


STEP 5: Test
------------
Message your Facebook Page:
  অর্ডার করবো কিভাবে?

Bot responds in Bengali! ✅


===========================================
  WINDOWS YOU NEED OPEN
===========================================

Window 1: python app_integrated.py
Window 2: ngrok http 5000
Window 3: python mode_manager.py (optional)


===========================================
  TROUBLESHOOTING
===========================================

❌ Webhook verification failed
   → Start server FIRST, then setup webhook

❌ Bot not responding
   → Keep both windows open (server + ngrok)

❌ Import errors
   → pip install --upgrade -r requirements.txt


===========================================
  DOCUMENTATION
===========================================

📖 HOW_TO_RUN.md - Complete detailed guide
📖 RUN_PROJECT.md - Quick 3-minute setup
📖 TWO_MODES_SIMPLE.md - Bot vs Human modes
📖 MODE_MANAGER_GUIDE.md - Manage modes


===========================================
  QUICK COMMANDS
===========================================

Start server:     python app_integrated.py
Start ngrok:      ngrok http 5000
Manage modes:     python mode_manager.py
Stop:             Ctrl+C


Your chatbot features:
✅ Bengali responses
✅ Product search
✅ Human handoff
✅ 24/7 support


Questions? See HOW_TO_RUN.md
