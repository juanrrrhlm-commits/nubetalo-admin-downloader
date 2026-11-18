"""Same-user named pipe for OS file associations; never a TCP control port."""
import hashlib
import json
from PySide6.QtCore import QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def channel_name(data_dir):
    return 'NubetaloDownloader-' + hashlib.sha256(str(data_dir.resolve()).casefold().encode()).hexdigest()[:24]


def forward(data_dir, sources):
    socket = QLocalSocket()
    socket.connectToServer(channel_name(data_dir))
    if not socket.waitForConnected(1500):
        return False
    socket.write((json.dumps(sources) + '\n').encode('utf-8'))
    socket.flush()
    socket.waitForBytesWritten(1000)
    socket.disconnectFromServer()
    return True


class InstanceServer(QObject):
    def __init__(self, data_dir, receive):
        super().__init__()
        self.receive = receive
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        name = channel_name(data_dir)
        QLocalServer.removeServer(name)
        if not self.server.listen(name):
            raise OSError('Cannot initialize local file-association channel')
        self.server.newConnection.connect(self.accept)
        self.buffers = {}

    def accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self.buffers[socket] = bytearray()
            socket.readyRead.connect(lambda s=socket: self.read(s))
            socket.disconnected.connect(lambda s=socket: self.discard(s))
            self.read(socket)

    def read(self, socket):
        if socket not in self.buffers:
            return
        buffer = self.buffers[socket]
        buffer.extend(bytes(socket.readAll()))
        if len(buffer) > 1024 * 1024:
            socket.abort()
            return
        if b'\n' in buffer:
            try:
                sources = json.loads(buffer.split(b'\n', 1)[0])
                if isinstance(sources, list) and len(sources) <= 100 and all(isinstance(x, str) and len(x) <= 16384 for x in sources):
                    self.receive(sources)
            except (ValueError, UnicodeError):
                pass
            socket.disconnectFromServer()

    def discard(self, socket):
        if socket not in self.buffers:
            return
        self.buffers.pop(socket, None)
        # Break callbacks capturing this socket before deferred native deletion.
        # Otherwise a later Qt event loop can visit a dead Python/C++ closure.
        socket.readyRead.disconnect()
        socket.disconnected.disconnect()
        socket.deleteLater()

    def close(self):
        self.server.close()
        for socket in list(self.buffers):
            self.discard(socket)
            socket.abort()
