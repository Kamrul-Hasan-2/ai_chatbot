"""
AI Chatbot - Main Runner
This script properly sets up paths and runs the application
"""
import sys
import os

# Add project root and src to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, project_root)
sys.path.insert(0, src_path)

# Change to project root directory
os.chdir(project_root)

print("=" * 60)
print("🤖 AI Chatbot - Starting Application")
print("=" * 60)
print(f"📁 Project Root: {project_root}")
print(f"🐍 Python Path Updated")
print("=" * 60)

# Import and run the Flask app
try:
    # Use the SIMPLE chatbot following your roadmap
    from src.api.app_simple import app, initialize
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Initialize chatbot system
    print("\n🔄 Initializing simple chatbot system...")
    initialize()
    
    # Get port from environment or use default
    port = int(os.getenv('PORT', 5000))
    
    print("\n" + "=" * 60)
    print("🎉 Server Ready!")
    print("=" * 60)
    print(f"🌐 Web Interface: http://localhost:{port}/")
    print(f"🔧 Health Check: http://localhost:{port}/health")
    print(f"📖 API Docs: http://localhost:{port}/")
    print("=" * 60)
    print("\n⏸️  Press CTRL+C to stop the server\n")
    
    # Run Flask application
    app.run(host='0.0.0.0', port=port, debug=False)
    
except ImportError as e:
    print("\n❌ Error: Failed to import required modules")
    print(f"Details: {e}")
    print("\n💡 Solutions:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Check if all files are in the correct location")
    print("3. Review PROJECT_STRUCTURE.md for proper structure")
    sys.exit(1)
    
except Exception as e:
    print(f"\n❌ Error starting server: {e}")
    print("\n💡 Check:")
    print("1. .env file exists and has required values")
    print("2. Port is not already in use")
    print("3. All dependencies are installed")
    import traceback
    traceback.print_exc()
    sys.exit(1)
