import errno
import socket
import sys

print("EXECUTABLE=%s" % sys.executable)
print("PREFIX=%s" % sys.prefix)
s = socket.socket()
try:
    s.connect(("127.0.0.1", 19099))
    print("CONNECTED")
except OSError as e:
    print(
        "DENIED errno=%s (%s) %s" % (e.errno, errno.errorcode.get(e.errno), e.strerror)
    )
