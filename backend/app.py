from . import create_app
from .config import Config
import os

app = create_app(Config)

@app.cli.command("init-db")
def init_db():
    """Initialize the database."""
    from .database import db
    db.create_all()
    print("Database initialized!")

@app.cli.command("create-admin")
def create_admin():
    """Create an admin user."""
    from .models import User
    from .database import db
    
    admin = User(
        username=os.getenv('ADMIN_USERNAME', 'admin'),
        email=os.getenv('ADMIN_EMAIL', 'admin@example.com'),
        password=os.getenv('ADMIN_PASSWORD', 'changeme'),
        ethereum_address=os.getenv('ADMIN_ETH_ADDRESS'),
        is_author=True
    )
    
    db.session.add(admin)
    db.session.commit()
    print(f"Admin user created: {admin.username}")

if __name__ == '__main__':
    app.run(
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    )