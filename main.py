from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from extensions import db, jwt, oauth
from models import User, TokenBlocklist, ChatHistory
from Config import config
from chat_code import get_chat_response
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt, current_user, get_jwt_identity
from dotenv import load_dotenv
import os

load_dotenv()

def create_app():
    app = Flask(__name__)
     
    app.config.from_object(config)
    
    db.init_app(app)
    jwt.init_app(app)
    oauth.init_app(app)
    google = oauth.register(
        name = 'google',
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        # authorize_url='https://accounts.google.com/o/oauth2/auth',
        # access_token_url='https://oauth2.googleapis.com/token',
        # userinfo_url='https://openidconnect.googleapis.com/v1/userinfo',
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={'scope': 'openid email profile'}
    )

    @app.route('/', methods=["GET","POST"])
    def base():
        if request.method == "GET":
            return render_template('base_chat.html')
        
        user_message = request.json.get("message")
        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        response = get_chat_response(user_message, "")
        return jsonify({"response": response})
    

    @app.route("/login", methods=["POST", "GET"])
    def login():
        if request.method == "GET":
            return render_template('login.html')
        
        data = request.get_json()
        username = data.get('username')
        email = data['email']
        password = data['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            access_token = create_access_token(identity=user.username)
            refresh_token = create_refresh_token(identity=user.username)
            return jsonify({'access_token': access_token, 'refresh_token': refresh_token})
        else:
            return jsonify({'message': 'Invalid credentials'}), 401
        

    @app.route("/register", methods=["POST", "GET"])
    def register():
        if request.method == "POST":
            data = request.get_json()
            user = User.query.filter_by(username=data.get('username')).first()

            if user:
                return jsonify({'message': 'User already exists'}), 409
            new_user = User(username=data.get('username'), email=data.get('email'))
            new_user.set_password(data.get('password'))
            new_user.save()
            return jsonify({'message': 'User created'}), 201
        else:
            return render_template('register.html')
    
    @app.route("/user_info", methods=["POST"])
    @jwt_required()
    def user_info():
        current_user = get_jwt_identity()
        print(current_user)
        return jsonify({
            'username': current_user,
        }), 200    
        

    @app.route("/chat", methods=["GET", "POST"])
    def chat():
        # Handle GET request without requiring authentication
        if request.method == "GET":
            return render_template('chat.html')

        # Enforce authentication only for POST (messages)
        @jwt_required()
        def handle_chat():
            user_message = request.json.get("message")
            if not user_message:
                return jsonify({"error": "Empty message"}), 400
            
            user_id = get_jwt_identity()
            response = get_chat_response(user_message, user_id)

            chat_entry = ChatHistory(user_id=user_id, message=user_message, response=response)
            db.session.add(chat_entry)
            db.session.commit()

            return jsonify({"response": response})

        return handle_chat()
    

    @app.route("/chat/history", methods=["GET"])
    @jwt_required()
    def chat_history():
        user_id = get_jwt_identity()  # Get logged-in user's ID
        history = ChatHistory.query.filter_by(user_id=user_id).order_by(ChatHistory.timestamp).all()
    
        chat_data = [{"message": chat.message, "response": chat.response, "timestamp": chat.timestamp} for chat in history]
        return jsonify({"chat_history": chat_data})
    
    
    @app.route("/logout", methods=["POST"])
    @jwt_required()
    def logout():
        jwt = get_jwt()
        jti = jwt['jti']
        token = TokenBlocklist(jti=jti)
        token.save()
        return jsonify({'message': 'Logged out'}), 200
    

    #login for google
    @app.route('/login/google')
    def google_login():
        try:
            redirect_uri = url_for('authorize', _external=True)
            return google.authorize_redirect(redirect_uri)
        except Exception as e:
            app.logger.error(f'error occured during login: {e}')
            return "error occured during login", 500
        

    #authorize for google
    @app.route('/authorize/google')
    def authorize():
        try:
            token = google.authorize_access_token()
            userinfo_endpoint = google.server_metadata['userinfo_endpoint']
            resp = google.get(userinfo_endpoint)  # ✅ Correct way to fetch user info
            user_info = resp.json()
            email = user_info.get('email')
            username = user_info.get('name')

            if not email:
                return jsonify({'message': 'Email not found in Google response'}), 400

            user = User.query.filter_by(email=email).first()
            if user is None:
                user = User(username=username, email=email, password=os.urandom(16).hex())
                user.save()

            # ✅ Generate JWT token for authenticated Google user
            access_token = create_access_token(identity=user.username)
            refresh_token = create_refresh_token(identity=user.username)

            # ✅ Store token in session or redirect with token
            return redirect(f"/chat?token={access_token}")


            return redirect(url_for('chat'))
        except Exception as e:
            app.logger.error(f'Error during Google authorization: {e}')
            return jsonify({'message': 'Google authorization failed'}), 500

    #jwt error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_data):
        return jsonify({
            'message': 'token expired',
            'error': 'token_expired'
        }), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            'message': 'invalid token',
            'error': 'invalid_token'
        }), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({
            'message': 'token is missing',
            'error': 'authorization_required'
        }), 401
    
    @jwt.token_in_blocklist_loader
    def token_in_blocklist_callback(jwt_header, jwt_data):
        jti = jwt_data['jti']
        token = TokenBlocklist.query.filter_by(jti=jti).one_or_none()
        return token is not None
    

    with app.app_context():
        db.create_all()
    return app

app = create_app()
if __name__ == '__main__':
    app.run(debug=True)