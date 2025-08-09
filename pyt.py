import asyncio
from aiohttp import web
import os
import subprocess
import json
import requests


NGROK_AUTHTOKEN = "30vNvjg2k6ExY3y79L7fHmpT3Yc_5PSRRf6yttkNDvgeEUaz9" 

clients = set()
routes = web.RouteTableDef()

@routes.get('/')
async def index(request):
    return web.Response(text=HTML_PAGE, content_type='text/html')

@routes.get('/ws')
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    clients.add(ws)

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            for client in clients:
                if client is not ws:
                    await client.send_str(msg.data)

    clients.remove(ws)
    return ws

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Python P2P Voice Call</title>
</head>
<body>
    <h2>Python WebRTC Voice Call</h2>
    <button onclick="start()">Start</button>
    <button onclick="call()">Call</button>
    <script>
        const pc = new RTCPeerConnection({
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' }  // public STUN server
            ]
        });

        const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");

        ws.onmessage = async (msg) => {
            const data = JSON.parse(msg.data);
            if (data.type === 'offer') {
                await pc.setRemoteDescription(new RTCSessionDescription(data));
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                stream.getTracks().forEach(track => pc.addTrack(track, stream));
                const answer = await pc.createAnswer();
                await pc.setLocalDescription(answer);
                ws.send(JSON.stringify(pc.localDescription));
            } else if (data.type === 'answer') {
                await pc.setRemoteDescription(new RTCSessionDescription(data));
            } else if (data.type === 'candidate') {
                try {
                    await pc.addIceCandidate(new RTCIceCandidate(data.candidate));
                } catch (e) {
                    console.error("ICE Error:", e);
                }
            }
        };

        pc.onicecandidate = (event) => {
            if (event.candidate) {
                ws.send(JSON.stringify({ type: 'candidate', candidate: event.candidate }));
            }
        };

        pc.ontrack = (event) => {
            const audio = new Audio();
            audio.srcObject = event.streams[0];
            audio.play();
        };

        async function start() {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach(track => pc.addTrack(track, stream));
        }

        async function call() {
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            ws.send(JSON.stringify(offer));
        }
    </script>
</body>
</html>
"""

async def start_app():
    app = web.Application()
    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()
    print("[✔] Server started at http://localhost:8080")

    # Download ngrok if needed
    if not os.path.exists("ngrok.exe"):
        print("[✔] Downloading ngrok...")
        subprocess.run(["curl", "-o", "ngrok.zip", "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-stable-windows-amd64.zip"])
        subprocess.run(["powershell", "Expand-Archive", "ngrok.zip", "."], shell=True)

    # Configure ngrok with your authtoken
    subprocess.run(["ngrok.exe", "config", "add-authtoken", NGROK_AUTHTOKEN], shell=True)

    # Start ngrok tunnel
    print("[✔] Starting ngrok tunnel...")
    subprocess.Popen(["ngrok.exe", "http", "8080"], shell=True)

    public_url = None
    while not public_url:
        try:
            r = requests.get("http://127.0.0.1:4040/api/tunnels")
            tunnels = r.json().get("tunnels")
            if tunnels:
                for tunnel in tunnels:
                    if tunnel["proto"] == "https":
                        public_url = tunnel["public_url"]
                        break
        except Exception:
            pass
        await asyncio.sleep(1)

    print(f"🔗 Public URL: {public_url}")
    print("📱 Open this on your phone to connect to your laptop's server")

    await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        asyncio.run(start_app())
    except KeyboardInterrupt:
        print("\n[✘] Server stopped.")
