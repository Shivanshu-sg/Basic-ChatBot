class config:
    SECRET_KEY = 'secret'
    FLASK_DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///database.db'    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = 'a98075bc65403ec304e23207'
    JWT_ALGORITHM = 'HS256'