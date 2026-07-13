import os
from app import create_app

# Instantiate the Flask app using development configurations
app = create_app(os.environ.get('FLASK_CONFIG', 'development'))

if __name__ == '__main__':
    # Defaulting to 127.0.0.1 for local development, or 0.0.0.0 if running in containers
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', 5000))
    
    app.run(host=host, port=port, debug=app.debug)
