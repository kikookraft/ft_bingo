from app import app, socketio

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5042, debug=False, use_reloader=False)