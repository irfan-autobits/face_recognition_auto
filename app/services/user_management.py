# final-compre/app/services/user_management.py
import datetime
from flask import current_app as app
import jwt
from app.models.model import Face_recog_User, db
from sqlalchemy.exc import SQLAlchemyError
              
def sign_up_user(email, password):            
    print(f"while saving :: {email} pass :: {password}")
    user = Face_recog_User(email=email, password=password)
    try:
        with app.app_context():
            db.session.add(user)
            db.session.commit()
            return {"message": f"User created and saved successfully as {email}."}, 200
    except Exception as e:
        db.session.rollback()
        return {"error": str(e)}, 500                            
    
def log_in_user(email, password):
    print(f"while login :: {email} pass :: {password}")
    user = Face_recog_User.query.filter_by(email=email, password=password).first()
    if user:
        print(f"User {email} logged in successfully.")
        # Generate JWT token
        token = jwt.encode(
            {'email': email, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
            app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        return {"message": f"User {email} logged in successfully.","token": token}, 200
    else:
        print(f"Invalid email or password.")
        return {"error": "Invalid email or password."}, 401