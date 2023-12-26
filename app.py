from flask import Flask, render_template, session, request, redirect, url_for
from flask_socketio import SocketIO, send, join_room, leave_room
from flask_cors import CORS
import random
import string
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
cors = CORS(app, resources={r"/socket.io/*": {"origins": "http://k-roomchat.azurewebsites.net"}})

app.config["SQLALCHEMY_DATABASE_URI"] = "MyDatabaseURL"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['SECRET_KEY']="YOUR SECRET KEY"

db = SQLAlchemy(app)
migrate = Migrate(app, db)

socketio = SocketIO(app,async_mode="threading", cors_allowed_origins="*")

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(4), unique=True, nullable=False)
    members = db.Column(db.Integer, default=0)
    messages = db.relationship('Message', backref='room', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sender = db.Column(db.String(50), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'))

def generate_code():
    letters = string.ascii_lowercase
    random_combination = ''.join(random.choice(letters) for _ in range(4))
    return random_combination


@app.route("/",methods=["GET","POST"])

def index():
    session.clear()
    name= session.get("name", None)
    code = session.get("code", None)
    if request.method == "POST":
        name = request.form["user_name"]

        if "checked" in request.form:
            checked = True
            code = generate_code()
            new_room = Room(code=code)
            db.session.add(new_room)
            print("room created")
            db.session.commit()
            
        else:
            checked = False
            code = request.form["room-code"]

            existing_room = Room.query.filter_by(code=code).first()
            if existing_room is None:
                print('invalid code')
                return render_template("login.html", error="Invalid Code", checked=checked)
            
        session["code"] = code
        session["name"] = name
            
        return redirect(url_for("room"))
    else:
        return render_template("login.html")

@app.route("/room", methods=["GET","POST"])

def room():
    
    
        code = session.get("code")
        name = session.get("name")
        
        if code is None:
            return redirect(url_for("index"))

        room = Room.query.filter_by(code=code).first()
        if room is None:
            print("code not in rooms")
            return redirect(url_for("index"))
        return render_template("room.html", code=code, name=name, messages=room.messages)

@socketio.on("message")
def message_sent(msg):
    print("Message received")
    try:
        code = session.get("code")

        if code:
            sender = session.get("name")
            room = Room.query.filter_by(code=code).first()

            if room:
                
                new_message = Message(content=msg["data"], sender=sender, room=room)
                db.session.add(new_message)
                db.session.commit()

                content = {
                    "sender": sender,
                    "message": msg["data"],
                    "timestamp": str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    "sent_by": sender
                }

                socketio.start_background_task(socketio.emit, "message_from_server", content, room=code)
                print("Message sent to the frontend")
                

    except Exception as e:
        print(f"Error processing message: {e}")
    
    
@socketio.on("connect")
def connect():
    print("joined room")
    code = session.get("code")
    name = session.get("name")
    
    if code:
        join_room(code)
        send({"sender": name, "message": " joined the chat", "sent_by": "server"}, to=code)

        room = Room.query.filter_by(code=code).first()
        if room:
            room.members += 1
    
            db.session.commit()
    
@socketio.on("disconnect")

def disconnect():
    print("left room")
    name = session.get("name")
    code = session.get("code")
    
    
    room = Room.query.filter_by(code=code).first()
    if code:
        leave_room(code)
        send({"sender": name, "message": " left the chat", "sent_by": "server"}, to=code)

        if room:
            room.members -= 1

            if room.members <= 1:
                db.session.delete(room)
            
            db.session.commit()

if __name__=="__main__":
    socketio.run(app)

