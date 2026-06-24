const http = require('http');
const fs = require('fs');
const path = require('path');
const { WebSocketServer, OPEN } = require('ws');

const server = http.createServer((req, res) => {
    if (req.url === '/' || req.url === '/index.html') {
        const filePath = path.join(__dirname, 'index.html');
        fs.readFile(filePath, (err, data) => {
            if (err) {
                res.writeHead(500);
                res.end('Error cargando index.html');
                return;
            }

            res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
            res.end(data);
        });
    } else {
        res.writeHead(404);
        res.end('Archivo no encontrado');
    }
});

const wss = new WebSocketServer({ server });

let hostSocket = null;
let clientSocket = null;

wss.on('connection', (ws) => {
    console.log('[NODE] Nueva conexión detectada');

    ws.on('message', (message) => {
        try {
            const data = JSON.parse(message);

            if (data.type === 'register-host') {
                hostSocket = ws;
                console.log('--> Host registrado correctamente');
                if (clientSocket && clientSocket.readyState === OPEN) {
                    clientSocket.send(JSON.stringify({ type: 'register-host' }));
                }
                return;
            }

            if (data.type === 'register-client') {
                clientSocket = ws;
                console.log('--> Cliente registrado correctamente');
                if (hostSocket && hostSocket.readyState === OPEN) {
                    hostSocket.send(JSON.stringify({ type: 'client-joined' }));
                    clientSocket.send(JSON.stringify({ type: 'client-joined' }));
                }
                return;
            }

            if (ws === clientSocket && hostSocket && hostSocket.readyState === OPEN) {
                hostSocket.send(JSON.stringify(data));
            } else if (ws === hostSocket && clientSocket && clientSocket.readyState === OPEN) {
                clientSocket.send(JSON.stringify(data));
            }

        } catch (error) {
            console.error('[NODE ERROR]', error.message);
        }
    });

    ws.on('close', () => {
        if (ws === hostSocket) hostSocket = null;
        if (ws === clientSocket) clientSocket = null;
        console.log('[NODE] Alguien se desconectó');
    });
});

server.listen(8080, '0.0.0.0', () => {
    console.log('Servidor web y WebSocket corriendo en puerto 8080');
});