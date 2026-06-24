import asyncio
import json
import cv2
import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCIceCandidate
from fractions import Fraction
import websockets
from pynput.keyboard import Controller, Key
import sys
from PIL import ImageGrab
from concurrent.futures import ThreadPoolExecutor
from pynput.mouse import Controller as MouseController, Button
import pyautogui

keyboard = Controller()
mouse = MouseController()

class ScreenShareTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.counter = 0
        # Pool de un solo hilo para capturar la pantalla sin congelar los WebSockets
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def recv(self):
        pts, time_base = self.counter, Fraction(1, 30)
        self.counter += 1
        
        try:
            # Capturar pantalla usando PIL de forma asíncrona y no bloqueante
            loop = asyncio.get_event_loop()
            screenshot = await loop.run_in_executor(self._executor, ImageGrab.grab)
            frame_rgb = np.array(screenshot)
            
            # Convertir formato de color (RGBA o RGB -> BGR)
            if len(frame_rgb.shape) >= 3 and frame_rgb.shape[2] == 4:
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGBA2BGR)
            else:
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                
            # Redimensionar a 720p para transmisión fluida
            frame_resized = cv2.resize(frame_bgr, (1280, 720))
        except Exception as e:
            # Fallback en caso de que falten permisos de grabación en macOS
            frame_resized = np.zeros((720, 1280, 3), dtype=np.uint8)
            cv2.putText(frame_resized, "ERROR DE CAPTURA DE PANTALLA", (80, 250), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            cv2.putText(frame_resized, "Por favor, otorga permisos de Grabacion de Pantalla", (80, 320), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame_resized, "a Terminal / Python en Configuracion del Sistema.", (80, 370), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame_resized, f"Detalle: {str(e)[:50]}", (80, 450), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)

        from av import VideoFrame
        new_frame = VideoFrame.from_ndarray(frame_resized, format="bgr24")
        new_frame.pts = pts
        new_frame.time_base = time_base
        return new_frame

async def main_loop():
    uri = "ws://localhost:8080"
    pc = None
    while True:
        try:
            print("[PYTHON] Conectando al servidor de señales...")
            async with websockets.connect(uri, ping_interval=None) as websocket:
                await websocket.send(json.dumps({"type": "register-host"}))
                print("[PYTHON OK] Registrado como Host. Esperando señales del cliente...")

                async for message in websocket:
                    data = json.loads(message)
                    
                    if data.get("type") == "offer":
                        print("[PYTHON] ¡Oferta recibida de la laptop!")
                        
                        if pc:
                            try:
                                await pc.close()
                            except Exception:
                                pass
                        
                        pc = RTCPeerConnection()
                        pc.addTrack(ScreenShareTrack())

                        # --- CORRECCIÓN CLAVE: Envío correcto de candidatos ICE hacia index.html ---
                        @pc.on("icecandidate")
                        async def on_icecandidate(candidate):
                            if candidate:
                                try:
                                    # Generamos la cadena de texto cruda clásica que el navegador espera decodificar
                                    candidate_str = f"candidate:{candidate.foundation} {candidate.component} {candidate.protocol} {candidate.priority} {candidate.ip} {candidate.port} typ {candidate.type}"
                                    await websocket.send(json.dumps({
                                        "type": "candidate",
                                        "candidate": {
                                            "candidate": candidate_str,
                                            "sdpMid": candidate.sdpMid if candidate.sdpMid else "0",
                                            "sdpMLineIndex": candidate.sdpMLineIndex if candidate.sdpMLineIndex is not None else 0
                                        }
                                    }))
                                    print(f"[PYTHON] Candidato ICE local enviado: {candidate.ip}:{candidate.port}")
                                except Exception as e:
                                    print(f"[ICE ERROR] No se pudo enviar candidato: {e}")
                        # -------------------------------------------------------------------------
                        
                        # Mapeo compatible con la propiedad .offer de tu index.html
                        offer = RTCSessionDescription(sdp=data["offer"]["sdp"], type=data["offer"]["type"])
                        await pc.setRemoteDescription(offer)
                        
                        answer = await pc.createAnswer()
                        
                        # HACK DE COMPATIBILIDAD DE CÓDEC H.264
                        sdp_lineas = answer.sdp.split("\r\n")
                        sdp_modificado = []
                        for linea in sdp_lineas:
                            if "profile-level-id=" in linea:
                                parts = linea.split("profile-level-id=")
                                linea = parts[0] + "profile-level-id=42e01f"
                            sdp_modificado.append(linea)
                        
                        fixed_sdp = "\r\n".join(sdp_modificado)
                        fixed_sdp = fixed_sdp.replace("a=setup:actpass", "a=setup:passive").replace("a=setup:active", "a=setup:passive")
                        
                        await pc.setLocalDescription(RTCSessionDescription(sdp=fixed_sdp, type=answer.type))
                        
                        # Respondemos estructurando el JSON tal cual lo lee index.html (data.answer)
                        await websocket.send(json.dumps({
                            "type": "answer",
                            "answer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
                        }))
                        print("[PYTHON OK] Respuesta enviada. Transmitiendo video...")

                    elif data.get("type") == "candidate":
                        cand = data.get("candidate")
                        if cand and "candidate" in cand and cand["candidate"] and pc and pc.remoteDescription:
                            try:
                                lines = cand["candidate"].split()
                                if len(lines) >= 8:
                                    c = RTCIceCandidate(
                                        component=int(lines[1]), foundation=lines[0], ip=lines[4],
                                        port=int(lines[5]), priority=int(lines[3]), protocol=lines[2],
                                        type=lines[7], sdpMid=cand.get("sdpMid"), sdpMLineIndex=cand.get("sdpMLineIndex")
                                    )
                                    await pc.addIceCandidate(c)
                                    print("[PYTHON] Candidato ICE del cliente acoplado.")
                            except Exception as e:
                                print(f"[ICE ERROR] Error aplicando candidato remoto: {e}")
                    elif data.get("type") == "mouse-move":
                        screen_width, screen_height = pyautogui.size()
                        x = int(data["x"] * screen_width)
                        y = int(data["y"] * screen_height)
                        mouse.position = (x, y)

                    elif data.get("type") == "mouse-click":
                        button = data.get("button", "left")

                        if button == "right":
                            mouse.click(Button.right, 1)
                        else:
                            mouse.click(Button.left, 1)
                            
                    elif data.get("type") == "input":
                        key_received = data["key"]
                        action = data["action"]
                        key_lower = key_received.lower()
                        
                        special_keys = {
                            "enter": Key.enter,
                            " ": Key.space,
                            "space": Key.space,
                            "backspace": Key.backspace,
                            "tab": Key.tab,
                            "shift": Key.shift,
                            "control": Key.ctrl,
                            "alt": Key.alt,
                            "escape": Key.esc,
                            "arrowup": Key.up,
                            "arrowdown": Key.down,
                            "arrowleft": Key.left,
                            "arrowright": Key.right,
                            "meta": Key.cmd,
                            "capslock": Key.caps_lock
                        }
                        
                        key_to_press = None
                        if key_lower in special_keys:
                            key_to_press = special_keys[key_lower]
                        elif len(key_received) == 1:
                            key_to_press = key_received
                            
                        if key_to_press:
                            try:
                                if action == "keydown":
                                    keyboard.press(key_to_press)
                                elif action == "keyup":
                                    keyboard.release(key_to_press)
                            except Exception as e:
                                print(f"[INPUT ERROR] No se pudo procesar la tecla {key_received}: {e}")

        except (websockets.exceptions.ConnectionClosed, OSError, asyncio.exceptions.IncompleteReadError) as e:
            print(f"\n[ALERTA] Desconexión o fallo de red detectado: {e}. Reiniciando canal...")
            if pc:
                try:
                    await pc.close()
                except Exception:
                    pass
                pc = None
            await asyncio.sleep(1)
        except Exception as e:
            print(f"\n[ERROR inesperado]: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        sys.exit(0)