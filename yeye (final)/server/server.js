// server/server.js
const express = require('express');
const http = require('http');
const socketIO = require('socket.io');
const app = express();
const server = http.createServer(app);
const io = socketIO(server);

// Serve static files from the public directory
app.use(express.static('public'));

io.on('connection', (socket) => {
  console.log('New client connected');

  // Handle joining a room
  socket.on('join-room', (roomId) => {
    socket.join(roomId);
    socket.roomId = roomId;
    console.log(`Client joined room: ${roomId}`);
    socket.to(roomId).emit('user-connected', socket.id);
  });

  // Relay signals to peers in the same room
  socket.on('signal', (data) => {
    const { roomId, signalData } = data;
    socket.to(roomId).emit('signal', {
      signalData,
      senderId: socket.id,
    });
  });

  // Handle disconnect
  socket.on('disconnect', () => {
    console.log('Client disconnected');
    socket.to(socket.roomId).emit('user-disconnected', socket.id);
  });
});

const PORT = 3000;
server.listen(PORT, () => console.log(`Server running on port ${PORT}`));
