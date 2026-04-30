from flask import Flask, jsonify, render_template_string, request
from flask_socketio import SocketIO, emit, join_room
from flask_cors import CORS
import threading
import uuid

from physics_engine import PhysicsEngine

app = Flask(__name__)
app.config["SECRET_KEY"] = "roulette-secret"
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

active_sessions = {}
session_lock = threading.Lock()


def get_session(session_id):
    with session_lock:
        return active_sessions.get(session_id)


def register_session(session_id, engine):
    with session_lock:
        if session_id in active_sessions:
            return False
        active_sessions[session_id] = engine
        return True


def remove_session(session_id):
    with session_lock:
        return active_sessions.pop(session_id, None)


@app.route("/")
def index():
    names = request.args.get("names", "")
    rank = request.args.get("rank", "")
    session_id = request.args.get("session_id", "")
    return render_template_string(
        HTML_TEMPLATE,
        names=names,
        rank=rank,
        session_id=session_id,
    )


@app.route("/stop_lottery_http", methods=["POST"])
def stop_lottery_http():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    engine = remove_session(session_id)
    if engine:
        engine.stop()
        print(f"Session stopped by admin: {session_id}")
        return jsonify({"success": True}), 200
    return jsonify({"success": False, "message": "Session not found"}), 404


@socketio.on("connect")
def handle_connect():
    print("Client connected")
    emit("connected", {"status": "ready"})


@socketio.on("join")
def on_join(data):
    session_id = data.get("session_id")
    if not session_id:
        return

    join_room(session_id)
    engine = get_session(session_id)
    if engine:
        emit("physics_update", engine.get_state())
    print(f"Client joined room: {session_id}")


@socketio.on("rejoin_session")
def handle_rejoin(data):
    session_id = data.get("session_id")
    if not session_id:
        return

    join_room(session_id)
    engine = get_session(session_id)
    if engine:
        emit("physics_update", engine.get_state())
        emit("session_restored", {"success": True})
        print(f"Client rejoined session: {session_id}")
    else:
        emit("session_restored", {"success": False})
        print(f"Session not found: {session_id}")


@socketio.on("start_lottery")
def handle_start(data):
    names = data.get("names", [])
    session_id = data.get("session_id") or str(uuid.uuid4())

    if not names:
        emit("session_error", {"message": "No participants provided"})
        return

    existing_engine = get_session(session_id)
    if existing_engine:
        emit("session_started", {"session_id": session_id})
        emit("physics_update", existing_engine.get_state())
        print(f"Session {session_id} already running, ignoring duplicate start")
        return

    physics_engine = PhysicsEngine(names)
    if not register_session(session_id, physics_engine):
        engine = get_session(session_id)
        emit("session_started", {"session_id": session_id})
        if engine:
            emit("physics_update", engine.get_state())
        return

    print(f"Starting session {session_id} with {len(names)} participants")
    physics_engine.start()

    def simulation_loop():
        while True:
            state = physics_engine.update()
            socketio.emit("physics_update", state, to=session_id)
            if not physics_engine.is_running and not physics_engine.skill_effects:
                break
            socketio.sleep(0.033)

        remove_session(session_id)
        socketio.emit("session_closed", {"session_id": session_id}, to=session_id)
        print(f"Session cleaned up: {session_id}")

    thread = threading.Thread(target=simulation_loop, daemon=True)
    thread.start()

    emit("session_started", {"session_id": session_id})


@socketio.on("stop_lottery")
def handle_stop(data=None):
    if data and "session_id" in data:
        session_id = data["session_id"]
        engine = get_session(session_id)
        if engine:
            engine.stop()
            print(f"Session stopping requested: {session_id}")
    else:
        print("stop_lottery called without session_id, ignoring")


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected (session kept alive)")


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Pinball Lottery</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #000; overflow: hidden; font-family: sans-serif; }
    #canvas { display: block; }

    .winner-display {
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: rgba(0,0,0,0.9);
      padding: 25px;
      border-radius: 12px;
      border: 3px solid cyan;
      min-width: 280px;
      max-width: 320px;
      max-height: 500px;
      overflow-y: auto;
      display: none;
    }
    .winner-display.show { display: block; }

    .time-accelerate-notice {
      background: rgba(255, 200, 0, 0.95);
      color: #000;
      padding: 10px 16px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: bold;
      text-align: center;
      margin-bottom: 15px;
      display: none;
      animation: pulse 1.5s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.7; }
    }

    .winner-display h3 { color: cyan; margin-bottom: 15px; font-size: 22px; text-align: center; }
    .winner-item {
      padding: 8px;
      margin: 8px 0;
      background: gold;
      color: #000;
      border-radius: 6px;
      font-size: 13px;
      font-weight: bold;
      text-align: center;
      word-break: break-word;
      line-height: 1.3;
    }
    .winner-item-lost {
      padding: 8px;
      margin: 8px 0;
      background: rgba(100, 100, 100, 0.5);
      color: #ccc;
      border-radius: 6px;
      font-size: 13px;
      font-weight: bold;
      text-align: center;
      word-break: break-word;
      line-height: 1.3;
    }

    @media (max-width: 768px) {
      .winner-display {
        top: 5px;
        right: 5px;
        bottom: auto;
        max-width: 150px;
        min-width: 150px;
        max-height: 35vh;
        padding: 8px;
        background: rgba(0,0,0,0.7);
        border-width: 2px;
      }

      .winner-display h3 {
        font-size: 14px;
        margin-bottom: 5px;
      }

      .winner-item, .winner-item-lost {
        font-size: 10px;
        padding: 5px;
        margin: 3px 0;
        line-height: 1.2;
      }

      .time-accelerate-notice {
        font-size: 10px;
        padding: 5px 8px;
        margin-bottom: 5px;
      }
    }
  </style>
  <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
</head>
<body>
  <canvas id="canvas"></canvas>
  <div class="winner-display" id="winner-display">
    <div class="time-accelerate-notice" id="time-notice">1 minute elapsed, speeding up</div>
    <h3>Ranking</h3>
    <div id="winner-list"></div>
  </div>

  <script>
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');

    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    window.addEventListener('resize', () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    });

    const socket = io();

    let camera = {
      x: 16,
      y: 20,
      zoom: 10,
      targetY: 20,
      targetZoom: 10
    };

    let winners = [];
    let totalMarbles = 0;
    let winningRank = 0;
    let particles = [];
    let elapsedTime = 0;
    let lotteryFinished = false;
    let winnerMarble = null;
    let winnerStartIndex = -1;
    let currentSessionId = '{{ session_id }}' || null;
    let stopRequested = false;

    class Particle {
      constructor(x, y) {
        this.x = x;
        this.y = y;
        this.elapsed = 0;
        this.lifetime = 3000;

        const force = Math.random() * 250;
        const ang = (Math.random() * 90 - 180) * Math.PI / 180;
        this.fx = Math.cos(ang) * force;
        this.fy = Math.sin(ang) * force;
        this.hue = Math.random() * 360;
        this.isDestroy = false;
      }

      update(deltaTime) {
        this.elapsed += deltaTime;
        this.x += this.fx * (deltaTime / 100);
        this.y += this.fy * (deltaTime / 100);
        this.fy += (10 * deltaTime) / 100;

        if (this.elapsed > this.lifetime) {
          this.isDestroy = true;
        }
      }

      getAlpha() {
        return 1 - Math.pow(this.elapsed / this.lifetime, 2);
      }
    }

    socket.on('connected', () => {
      const urlParams = new URLSearchParams(window.location.search);
      const namesParam = urlParams.get('names');
      const rankParam = urlParams.get('rank');
      const sessionParam = urlParams.get('session_id');

      if (sessionParam) {
        currentSessionId = sessionParam;
        socket.emit('join', { session_id: currentSessionId });
        socket.emit('rejoin_session', { session_id: currentSessionId });
      }

      if (namesParam) {
        const names = namesParam.split(',').map((n) => n.trim()).filter((n) => n);
        totalMarbles = names.length;
        winningRank = rankParam ? parseInt(rankParam, 10) : 1;
        socket.emit('start_lottery', {
          names,
          session_id: currentSessionId
        });
      }
    });

    socket.on('session_started', (data) => {
      currentSessionId = data.session_id;
    });

    socket.on('session_closed', () => {
      stopRequested = true;
    });

    socket.on('physics_update', (state) => {
      if (state.elapsed_time !== undefined) {
        elapsedTime = state.elapsed_time;
        const timeNotice = document.getElementById('time-notice');
        timeNotice.style.display = elapsedTime > 60 && !lotteryFinished ? 'block' : 'none';
      }

      if (state.camera) {
        camera.targetY = state.camera.targetY;
        camera.y += (camera.targetY - camera.y) * 0.05;

        if (state.camera.targetZoom) {
          camera.targetZoom = state.camera.targetZoom;
          camera.zoom += (camera.targetZoom - camera.zoom) * 0.05;
        }
      }

      if (state.winners && state.winners.length > winners.length) {
        winners = state.winners;
      }

      if (state.total_marbles) {
        totalMarbles = state.total_marbles;
      }

      const remainingMarbles = totalMarbles - winners.length;

      if (winnerStartIndex === -1 && remainingMarbles === winningRank) {
        winnerStartIndex = winners.length;
      }

      if (!lotteryFinished && remainingMarbles === 1 && state.marbles && state.marbles.length > 0) {
        lotteryFinished = true;
        winnerMarble = state.marbles[0];

        const finalWinners = [];
        for (let i = winnerStartIndex; i < winners.length; i++) {
          finalWinners.push(winners[i].name);
        }
        finalWinners.push(winnerMarble.name);
        finalWinners.reverse();

        if (window.parent !== window) {
          window.parent.postMessage({
            type: 'PINBALL_WINNERS',
            winners: finalWinners
          }, '*');
        }

        for (let i = 0; i < 200; i++) {
          particles.push(new Particle(canvas.width / 2, canvas.height / 2));
        }

        if (!stopRequested) {
          stopRequested = true;
          setTimeout(() => {
            socket.emit('stop_lottery', { session_id: currentSessionId });
          }, 3000);
        }
      }

      updateWinnerDisplay();
      render(state);
    });

    function animate() {
      particles.forEach((p) => p.update(16));
      particles = particles.filter((p) => !p.isDestroy);
      requestAnimationFrame(animate);
    }
    animate();

    function updateWinnerDisplay() {
      const list = document.getElementById('winner-list');
      list.innerHTML = '';

      if (lotteryFinished && winnerMarble) {
        const div = document.createElement('div');
        div.className = 'winner-item';
        div.textContent = '1st ' + winnerMarble.name;
        list.appendChild(div);
      }

      for (let i = winners.length - 1; i >= 0; i--) {
        const winner = winners[i];
        const rank = totalMarbles - i;
        const div = document.createElement('div');

        if (winnerStartIndex !== -1 && i >= winnerStartIndex) {
          div.className = 'winner-item';
          const winnerRank = winningRank - (i - winnerStartIndex);
          div.textContent = winnerRank + 'th ' + winner.name;
        } else {
          div.className = 'winner-item-lost';
          div.textContent = rank + 'th ' + winner.name;
        }

        list.appendChild(div);
      }

      if (winners.length > 0 || lotteryFinished) {
        document.getElementById('winner-display').classList.add('show');
      }
    }

    function render(state) {
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      if (lotteryFinished && winnerMarble) {
        camera.targetY = winnerMarble.y;
        camera.targetZoom = 35;
      }

      ctx.save();
      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.scale(camera.zoom, camera.zoom);
      ctx.translate(-camera.x, -camera.y);

      if (state.walls) {
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 0.2;
        ctx.shadowBlur = 5;
        ctx.shadowColor = 'white';

        state.walls.forEach((wall) => {
          ctx.beginPath();
          ctx.moveTo(wall[0][0], wall[0][1]);
          for (let i = 1; i < wall.length; i++) {
            ctx.lineTo(wall[i][0], wall[i][1]);
          }
          ctx.stroke();
        });
        ctx.shadowBlur = 0;
      }

      if (state.pins) {
        ctx.fillStyle = 'cyan';
        ctx.shadowBlur = 5;
        ctx.shadowColor = 'cyan';

        state.pins.forEach((pin) => {
          ctx.save();
          ctx.translate(pin.x, pin.y);
          ctx.rotate(pin.angle);
          ctx.fillRect(-pin.width, -pin.height, pin.width * 2, pin.height * 2);
          ctx.restore();
        });
        ctx.shadowBlur = 0;
      }

      if (state.boxes) {
        ctx.fillStyle = 'cyan';
        ctx.shadowBlur = 5;
        ctx.shadowColor = 'cyan';

        state.boxes.forEach((box) => {
          ctx.save();
          ctx.translate(box.x, box.y);
          ctx.rotate(box.angle);
          ctx.fillRect(-box.width, -box.height, box.width * 2, box.height * 2);
          ctx.restore();
        });
        ctx.shadowBlur = 0;
      }

      if (state.skill_effects) {
        state.skill_effects.forEach((effect) => {
          ctx.save();
          ctx.globalAlpha = effect.alpha;
          ctx.strokeStyle = 'white';
          ctx.lineWidth = 1 / camera.zoom;
          ctx.beginPath();
          ctx.arc(effect.x, effect.y, effect.size, 0, Math.PI * 2);
          ctx.stroke();
          ctx.restore();
        });
      }

      if (state.marbles) {
        state.marbles.forEach((marble) => {
          ctx.save();
          ctx.translate(marble.x, marble.y);
          ctx.rotate(marble.angle);

          ctx.fillStyle = 'hsl(' + marble.hue + ', 100%, 70%)';
          ctx.shadowBlur = 10;
          ctx.shadowColor = 'hsl(' + marble.hue + ', 100%, 70%)';
          ctx.beginPath();
          ctx.arc(0, 0, 0.25, 0, Math.PI * 2);
          ctx.fill();
          ctx.shadowBlur = 0;

          ctx.rotate(-marble.angle);
          ctx.scale(1 / camera.zoom, 1 / camera.zoom);
          ctx.fillStyle = '#fff';
          ctx.font = 'bold 12px sans-serif';
          ctx.textAlign = 'center';
          ctx.strokeStyle = '#000';
          ctx.lineWidth = 3;
          ctx.strokeText(marble.name, 0, 20);
          ctx.fillText(marble.name, 0, 20);

          ctx.restore();
        });
      }

      ctx.restore();

      particles.forEach((particle) => {
        ctx.save();
        ctx.globalAlpha = particle.getAlpha();
        ctx.fillStyle = 'hsl(' + particle.hue + ', 50%, 50%)';
        ctx.fillRect(particle.x, particle.y, 20, 20);
        ctx.restore();
      });
    }
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
