// public/script.js
const socket = io();
let peerConnection;
let dataChannel;
const configuration = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    // {
    //   urls: 'turn:<TURN_SERVER_IP>:3478',
    //   username: 'username',
    //   credential: 'password',
    // },
  ],
};

const roomIdInput = document.getElementById('roomId');
const joinButton = document.getElementById('joinButton');
const connectedDiv = document.getElementById('connected');
const statusParagraph = document.getElementById('status');
const sendFileButton = document.getElementById('sendFile');
const fileInput = document.getElementById('fileInput');

let roomId;
let isInitiator = false;

joinButton.onclick = () => {
  roomId = roomIdInput.value;
  if (roomId) {
    socket.emit('join-room', roomId);
    statusParagraph.textContent = `Joined room: ${roomId}`;
    console.log(`Joined room: ${roomId}`);
    connectedDiv.style.display = 'block';
  } else {
    alert('Please enter a room ID');
  }
};

socket.on('user-connected', (userId) => {
  console.log(`User connected: ${userId}`);
  isInitiator = true;
  startPeerConnection(userId);
});

socket.on('signal', async (data) => {
  const { signalData, senderId } = data;

  if (!peerConnection) {
    startPeerConnection(senderId);
  }

  if (signalData.type === 'offer') {
    await peerConnection.setRemoteDescription(new RTCSessionDescription(signalData));
    const answer = await peerConnection.createAnswer();
    await peerConnection.setLocalDescription(answer);
    socket.emit('signal', {
      roomId,
      signalData: peerConnection.localDescription,
    });
  } else if (signalData.type === 'answer') {
    await peerConnection.setRemoteDescription(new RTCSessionDescription(signalData));
  } else if (signalData.candidate) {
    await peerConnection.addIceCandidate(new RTCIceCandidate(signalData.candidate));
  }
});


function displayReceivedFile() {
  const receivedFileSection = document.getElementById('receivedFileSection');
  const fileDisplay = document.getElementById('fileDisplay');
  const downloadButton = document.getElementById('downloadButton');

  // Create a blob from the received data
  const blob = new Blob([receivedFileData], { type: receivedFileType });
  const url = URL.createObjectURL(blob);

  // Display the file content if it's an image or text
  if (receivedFileType.startsWith('image/')) {
    const img = document.createElement('img');
    img.src = url;
    img.alt = receivedFileName;
    img.style.maxWidth = '100%';
    fileDisplay.innerHTML = '';
    fileDisplay.appendChild(img);
  } else if (receivedFileType.startsWith('text/')) {
    blob.text().then((text) => {
      const pre = document.createElement('pre');
      pre.textContent = text;
      fileDisplay.innerHTML = '';
      fileDisplay.appendChild(pre);
    });
  } else {
    fileDisplay.innerHTML = '<p>File received. Click the button below to download.</p>';
  }

  // Set up the download button
  downloadButton.onclick = () => {
    const a = document.createElement('a');
    a.href = url;
    a.download = receivedFileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  // Show the received file section
  receivedFileSection.style.display = 'block';
  statusParagraph.textContent = 'File received';
}


function startPeerConnection(userId) {
  peerConnection = new RTCPeerConnection(configuration);

  peerConnection.onicecandidate = ({ candidate }) => {
    if (candidate) {
      socket.emit('signal', {
        roomId,
        signalData: { candidate },
      });
    }
  };

  if (isInitiator) {
    dataChannel = peerConnection.createDataChannel('fileTransfer');
    setupDataChannel();
    createOffer();
  } else {
    peerConnection.ondatachannel = (event) => {
      dataChannel = event.channel;
      setupDataChannel();
    };
  }

  peerConnection.onconnectionstatechange = () => {
    if (peerConnection.connectionState === 'connected') {
      statusParagraph.textContent = 'Connected to peer';
    }
  };
}

async function createOffer() {
  const offer = await peerConnection.createOffer();
  await peerConnection.setLocalDescription(offer);
  socket.emit('signal', {
    roomId,
    signalData: peerConnection.localDescription,
  });
}

function setupDataChannel() {
  dataChannel.onopen = () => {
    console.log('Data channel opened');
  };

  dataChannel.onmessage = receiveFile;
}


sendFileButton.onclick = () => {
  const file = fileInput.files[0];
  if (file) {
    sendFile(file);
  } else {
    alert('Please select a file to send');
  }
};

function sendFile(file) {
  // Send file metadata first
  const fileMetadata = {
    fileName: file.name,
    fileType: file.type,
  };
  dataChannel.send(JSON.stringify({ type: 'file-metadata', data: fileMetadata }));

  // Read and send the file data
  const reader = new FileReader();
  reader.onload = () => {
    dataChannel.send(reader.result);
    statusParagraph.textContent = 'File sent';
  };
  reader.readAsArrayBuffer(file);
}


function receiveFile(event) {
  const data = event.data;

  // Check if data is JSON (metadata) or binary (file data)
  if (typeof data === 'string') {
    const message = JSON.parse(data);
    if (message.type === 'file-metadata') {
      receivedFileName = message.data.fileName || 'received_file';
      receivedFileType = message.data.fileType || '';
    }
  } else {
    // It's the file data
    receivedFileData = data;
    displayReceivedFile();
  }
}
