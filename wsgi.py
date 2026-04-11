from app import create_app, _seed_default_users

app = create_app()
_seed_default_users(app)
