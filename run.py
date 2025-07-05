#!/usr/bin/env python3
"""
Simple startup script for the RecipLan Backend
"""
import os
import sys
from app import create_app

def main():
    """Main entry point for the application"""
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("⚠️  Warning: .env file not found!")
        print("Please create a .env file based on env_example.txt")
        print("See README.md for setup instructions")
        return
    
    # Create and run the Flask app
    app = create_app()
    
    # Get configuration from environment
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    
    print(f"🚀 Starting RecipLan Backend on {host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/health")
    print(f"🔧 Debug Mode: {debug_mode}")
    
    try:
        app.run(host=host, port=port, debug=debug_mode)
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 