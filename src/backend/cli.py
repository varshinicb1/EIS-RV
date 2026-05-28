#!/usr/bin/env python3
"""
RĀMAN Studio Backend CLI
Command-line interface for starting the backend server
"""

import sys
import argparse


def main():
    """Main entry point for the backend server"""
    parser = argparse.ArgumentParser(description='RĀMAN Studio Backend Server')
    parser.add_argument('--host', type=str, default='127.0.0.1',
                        help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8000,
                        help='Port to bind to (default: 8000)')
    parser.add_argument('--log-level', type=str, default='info',
                        choices=['critical', 'error', 'warning', 'info', 'debug', 'trace'],
                        help='Log level (default: info)')
    parser.add_argument('--no-access-log', action='store_true',
                        help='Disable access log')
    
    args = parser.parse_args()
    
    # Import the FastAPI app
    try:
        from src.backend.api.server import app
    except ImportError:
        # Fallback for PyInstaller bundled version
        import server
        app = server.app
    
    # Start uvicorn server
    import uvicorn
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        access_log=not args.no_access_log,
        reload=False
    )


if __name__ == '__main__':
    main()
