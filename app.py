from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json
from physics_engine import PhysicsEngine

app = Flask(__name__)
app.config['SECRET_KEY'] = 'roulette-secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

physics_engine = None

@app.route('/')
def index():
    names = request.args.get('names', '')
    rank = request.args.get('rank', '')
    return render_template_string(HTML_TEMPLATE, names=names, rank=rank)

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('connected', {'status': 'ready'})

@socketio.on('start_lottery')
def handle_start(data):
    global physics_engine
    names = data.get('names', [])
    
    print(f'Starting lottery with {len(names)} participants')
    physics_engine = PhysicsEngine(names)
    physics_engine.start()
    
    import threading
    def simulation_loop():
        while physics_engine.is_running or len(physics_engine.skill_effects) > 0:
            state = physics_engine.update()
            socketio.emit('physics_update', state)
            socketio.sleep(0.016)
    
    thread = threading.Thread(target=simulation_loop)
    thread.daemon = True
    thread.start()

@socketio.on('stop_lottery')
def handle_stop():
    global physics_engine
    if physics_engine:
        physics_engine.stop()

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')
    global physics_engine
    if physics_engine:
        physics_engine.stop()

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>핀볼 추첨</title>
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
      padding: 10px;
      margin: 8px 0;
      background: gold;
      color: #000;
      border-radius: 6px;
      font-size: 18px;
      font-weight: bold;
      text-align: center;
    }
    .winner-item-lost {
      padding: 10px;
      margin: 8px 0;
      background: rgba(100, 100, 100, 0.5);
      color: #ccc;
      border-radius: 6px;
      font-size: 18px;
      font-weight: bold;
      text-align: center;
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
        font-size: 11px;
        padding: 5px;
        margin: 3px 0;
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
    <div class="time-accelerate-notice" id="time-notice">1분 30초 경과 시간 가속</div>
    <h3>순위</h3>
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
      console.log('Connected to server');
      const urlParams = new URLSearchParams(window.location.search);
      const namesParam = urlParams.get('names');
      const rankParam = urlParams.get('rank');
      
      if (namesParam) {
        const names = namesParam.split(',').map(n => n.trim()).filter(n => n);
        totalMarbles = names.length;
        
        if (rankParam) {
          winningRank = parseInt(rankParam);
        } else {
          winningRank = 1;
        }
        
        console.log('Total marbles:', totalMarbles, 'Winning rank:', winningRank);
        socket.emit('start_lottery', { names });
      }
    });
    
    socket.on('physics_update', (state) => {
      if (state.elapsed_time !== undefined) {
        elapsedTime = state.elapsed_time;
        const timeNotice = document.getElementById('time-notice');
        if (elapsedTime > 90 && !lotteryFinished) {
          timeNotice.style.display = 'block';
        } else {
          timeNotice.style.display = 'none';
        }
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
        console.log('Winners start at index:', winnerStartIndex);
      }
      
      if (!lotteryFinished && remainingMarbles === 1 && state.marbles && state.marbles.length > 0) {
        lotteryFinished = true;
        winnerMarble = state.marbles[0];
        console.log('Last marble! Creating particles...');
        
        const finalWinners = [];
        
        for (let i = winnerStartIndex; i < winners.length; i++) {
          finalWinners.push(winners[i].name);
        }
        
        finalWinners.push(winnerMarble.name);
        
        finalWinners.reverse();
        
        console.log('Final winners (1위→10위):', finalWinners);
        
        if (window.parent !== window) {
          window.parent.postMessage({
            type: 'PINBALL_WINNERS',
            winners: finalWinners
          }, '*');
        }
        
        for (let i = 0; i < 200; i++) {
          particles.push(new Particle(canvas.width / 2, canvas.height / 2));
        }
        
        setTimeout(() => {
          console.log('Stopping physics after particles...');
          socket.emit('stop_lottery');
        }, 3000);
      }
      
      updateWinnerDisplay(state);
      render(state);
    });
    
    function animate() {
      particles.forEach(p => p.update(16));
      particles = particles.filter(p => !p.isDestroy);
      requestAnimationFrame(animate);
    }
    animate();
    
    function updateWinnerDisplay(state) {
      const list = document.getElementById('winner-list');
      list.innerHTML = '';
      
      if (lotteryFinished && winnerMarble) {
        const div = document.createElement('div');
        div.className = 'winner-item';
        div.textContent = '1위: ' + winnerMarble.name;
        list.appendChild(div);
      }
      
      for (let i = winners.length - 1; i >= 0; i--) {
        const winner = winners[i];
        const rank = totalMarbles - i;
        const div = document.createElement('div');
        
        if (winnerStartIndex !== -1 && i >= winnerStartIndex) {
          div.className = 'winner-item';
          const winnerRank = winningRank - (i - winnerStartIndex);
          div.textContent = winnerRank + '위: ' + winner.name;
        } else {
          div.className = 'winner-item-lost';
          div.textContent = rank + '위: ' + winner.name;
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
        
        state.walls.forEach(wall => {
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
        
        state.pins.forEach(pin => {
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
        
        state.boxes.forEach(box => {
          ctx.save();
          ctx.translate(box.x, box.y);
          ctx.rotate(box.angle);
          ctx.fillRect(-box.width, -box.height, box.width * 2, box.height * 2);
          ctx.restore();
        });
        ctx.shadowBlur = 0;
      }
      
      if (state.skill_effects) {
        state.skill_effects.forEach(effect => {
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
        state.marbles.forEach(marble => {
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
          ctx.scale(1/camera.zoom, 1/camera.zoom);
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
      
      particles.forEach(particle => {
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
'''

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
