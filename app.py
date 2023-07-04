from flask import Flask, render_template, redirect, request, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, join_room, leave_room
from pymongo.errors import DuplicateKeyError

from db import get_user, save_user, save_room, add_room_members

app = Flask(__name__)

app.secret_key = "chitchat"
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

socketio = SocketIO(app)


#home page
@app.route('/')
def home():
    return render_template('index.html')


#login/logout/signup
@app.route('/login/', methods=['GET', 'POST'])
def login():

    if current_user.is_authenticated:
        return redirect(url_for('home')) 

    err_msg = ''
    if request.method == 'POST':
        username = request.form.get('username')
        password_input = request.form.get('password')
        user = get_user(username)
        if user and user.check_password(password_input):
            login_user(user)
            return redirect(url_for('home'))
        else:
            err_msg = 'Failed to login'
    
    return render_template('login.html', errmsg = err_msg)

@app.route("/logout/")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/signup/",methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    msg_user_exist = ''
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password_input = request.form.get('password')
        try:
            save_user(username, email, password_input)
            user = get_user(username)
            login_user(user)
            return redirect(url_for('home'))
        except DuplicateKeyError:
            msg_user_exist = '!!! User Already Exist !!!'
    
    return render_template('signup.html',msguserexist = msg_user_exist)



#chatrooms
@app.route('/create-room/', methods =['GET','POST'])
@login_required
def create_room():
    message = ''
    if request.method == 'POST':
        room_name = request.form.get('room_name')
        usernames = [username.strip() for username in request.form.get('members').split(',')]

        if len(room_name) and len(usernames):
            room_id = save_room(room_name, current_user.username)
            if current_user.username in usernames:
                usernames.remove(current_user.username)
            add_room_members(room_id, room_name, usernames, current_user.username)
            return redirect(url_for('view_room', room_id=room_id))
        else:
            message = "Failed to create room"
    return render_template('create_room.html', message=message)



@app.route('/chat')
@login_required
def chat():
    username = request.args.get('username')
    roomid = request.args.get('roomid')

    if username and roomid:
        return render_template('chat.html', username=username, roomid=roomid)
    else:
        return redirect(url_for('home'))



#Serverside socketio event handlers
@socketio.on('join_room')
def handle_join_room_event(data):
    app.logger.info("{} has joined the room {}".format(data['username'], data['roomid']))
    join_room(data['roomid'])
    socketio.emit('join_announcement', data)


@socketio.on('send_message')
def handle_send_message_event(data):
    app.logger.info("{} sent message {} to room {}".format(data['username'],data['msg'], data['roomid']))
    socketio.emit('receive_message', data)


@socketio.on('leave_room')
def handle_leave_room_event(data):
    app.logger.info("{} has left the room".format(data['username'], data['roomid']))
    leave_room(data['roomid'])
    socketio.emit('leave_room_announcement', data)


@login_manager.user_loader
def load_user(username):
    return get_user(username)




if __name__ == "__main__":
    socketio.run(app, debug=True)
