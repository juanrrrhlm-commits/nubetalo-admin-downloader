import os
import time
import gc
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QLocalSocket
from nubetalo.ipc import InstanceServer, channel_name


def test_existing_instance_receives_sources(tmp_path):
    app = QApplication.instance() or QApplication([])
    received = []
    server = InstanceServer(tmp_path, received.append)
    socket = QLocalSocket()
    socket.connectToServer(channel_name(tmp_path))
    assert socket.waitForConnected(1000)
    socket.write(b'["https://example.com/test.bin"]\n')
    socket.flush()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        app.processEvents()
        if received:
            break
        time.sleep(.005)
    assert received == [['https://example.com/test.bin']]
    socket.disconnectFromServer()
    server.close()
    del server, socket
    gc.collect()
    # Process deferred socket deletion before another window/animation starts.
    from PySide6.QtTest import QTest
    QTest.qWait(100)
