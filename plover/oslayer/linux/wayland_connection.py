import array
import collections
import os
import selectors
import socket
import struct

from plover import log

WAYLAND_MESSAGE_HEADER_SIZE_BYTES = 8

# Wayland object IDs
DISPLAY_ID = 1
REGISTRY_ID = 2
SYNC_ID = 3
SEAT_ID = 4
KEYBOARD_ID = 5

# Wayland Opcodes
OPCODE_WL_DISPLAY_SYNC = 0
OPCODE_WL_DISPLAY_GET_REGISTRY = 1
OPCODE_WL_CALLBACK_DONE = 0
OPCODE_WL_REGISTRY_GLOBAL = 0
OPCODE_WL_REGISTRY_BIND = 0
OPCODE_WL_SEAT_CAPABILITIES = 0
OPCODE_WL_DISPLAY_ERROR = 0
OPCODE_WL_DISPLAY_DELETE_ID = 1
OPCODE_WL_KEYBOARD_KEYMAP = 0

WL_KEYBOARD_KEYMAP_FORMAT_XKB_V1 = 1


def round_up_power_of_two(value: int, multiple: int):
    """Round `value` up to the nearest multiple of `multiple`.
    `multiple` must be positive and a power of 2"""
    assert (multiple > 0) and ((multiple & (multiple - 1)) == 0), (
        "Multiple must be positive and a power of two"
    )
    return (value + multiple - 1) & ~(multiple - 1)


class WaylandConnection:
    """Context manager for connecting to the Wayland server on the default socket path.

    Useful references:
    - https://wayland-book.com/
    - https://wayland.freedesktop.org/docs/html/ch04.html#sect-Protocol-Wire-Format
    - https://wayland.app/protocols/wayland
    """

    fd_queue: collections.deque[int]
    _wayland_socket: socket.socket
    _shutdown_pipe_read: int
    _shutdown_pipe_write: int
    _selector: selectors.BaseSelector

    def __init__(self):
        self.fd_queue = collections.deque()
        self._shutdown_pipe_read, self._shutdown_pipe_write = os.pipe()
        self._selector = selectors.DefaultSelector()

    def __enter__(self):
        # Find socket path following libwayland (https://wayland-book.com/protocol-design/wire-protocol.html#transports)
        xdg_runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "")
        wayland_display = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
        socket_path = os.path.join(xdg_runtime_dir, wayland_display)

        self._wayland_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._wayland_socket.connect(socket_path)

        self._selector.register(self._wayland_socket, selectors.EVENT_READ)
        self._selector.register(self._shutdown_pipe_read, selectors.EVENT_READ)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._selector.close()
        finally:
            self._wayland_socket.shutdown(socket.SHUT_RDWR)
            self._wayland_socket.close()
            os.close(self._shutdown_pipe_read)
            os.close(self._shutdown_pipe_write)

    def recv_message(self) -> tuple[int, int, int, bytearray]:
        """Receive an event from the Wayland server. Blocks until a complete message is received.

        Returns:
            A tuple of (object_id, length, opcode, event_data_bytes)

        length includes the message header.
        """
        # The only event with fds that we care about is wl_keyboard::keymap which only has one fd
        # In each message, we only need to receive at most one fd
        # TODO: Unless messages with more delay when we received the keymap event fds?
        MAX_FD_COUNT = 1
        event_header_bytes, fds = self._recv_fds_exact(
            WAYLAND_MESSAGE_HEADER_SIZE_BYTES, MAX_FD_COUNT
        )
        self.fd_queue.extend(fds)
        object_id, length_and_opcode = struct.unpack("=II", event_header_bytes)
        length = length_and_opcode >> 16
        assert length % 4 == 0, "Length of message must be a multiple of 4."
        opcode = length_and_opcode & 0xFFFF
        event_data_bytes, fds = self._recv_fds_exact(
            length - WAYLAND_MESSAGE_HEADER_SIZE_BYTES, MAX_FD_COUNT
        )
        self.fd_queue.extend(fds)
        return object_id, length, opcode, event_data_bytes

    def send_message(self, object_id: int, opcode: int, data: bytes | bytearray):
        """Send a request to the Wayland server.

        Args:
            object_id: The ID of the object to send the request to.
            opcode: The opcode of the request.
            data: The data to send with the request.
        """
        length = WAYLAND_MESSAGE_HEADER_SIZE_BYTES + len(data)
        # Wayland messages are streams of 32-bit (4 byte) values
        assert length % 4 == 0, "Length of message must be a multiple of 4."
        # The length field is a 16-bit unsigned integer (the upper 16 bits of the 32-bit value)
        assert length < 2**16, "Length of message must be less than 2^16."
        length_and_opcode = (length << 16) | opcode
        message = struct.pack("=II", object_id, length_and_opcode)
        self._wayland_socket.sendall(message)
        self._wayland_socket.sendall(data)

    def shutdown(self):
        """Signal the Wayland connection to close and for the event loop to exit."""
        os.write(self._shutdown_pipe_write, b"\x00")

    def _recv_fds_exact(self, length: int, fd_count: int):
        """Receive exactly `length` bytes from the Wayland server and up to `fd_count` file descriptors.

        Returns:
            A tuple of (data bytes received, fds received)
        Raises:
            InterruptedError: if the connection is shut down using `WaylandConnection.shutdown()`.
        """
        fds = array.array("i")
        buffer = bytearray(length)
        buffer_view = memoryview(buffer)

        if length < 0:
            raise ValueError("Length must be non-negative.")
        if fd_count < 0:
            raise ValueError("FD count must be non-negative.")

        while length > 0:
            for key, _ in self._selector.select():
                if key.fileobj == self._shutdown_pipe_read:
                    raise InterruptedError()
                # Based on Python3 socket.recvmsg docs (https://docs.python.org/3/library/socket.html#socket.socket.recvmsg)
                n, ancdata, flags, addr = self._wayland_socket.recvmsg_into(
                    [buffer_view], socket.CMSG_LEN(fd_count * fds.itemsize)
                )
                for cmsg_level, cmsg_type, cmsg_data in ancdata:
                    if (
                        cmsg_level == socket.SOL_SOCKET
                        and cmsg_type == socket.SCM_RIGHTS
                    ):
                        # Append data, ignoring any truncated integers at the end.
                        fds.frombytes(
                            cmsg_data[
                                : len(cmsg_data) - (len(cmsg_data) % fds.itemsize)
                            ]
                        )
                # Advance write position in buffer
                buffer_view = buffer_view[n:]
                length -= n

        fds = list(fds)

        return buffer, fds


def wayland_keymap_event_loop(connection: WaylandConnection) -> tuple[int, int]:
    """Get the keymap from the Wayland server.
    See https://wayland.app/protocols/wayland for the opcodes and arguments

    Returns a tuple of (keymap_fd, keymap_size) as returned by the Wayland server.
    """
    # wl_display::get_registry
    # display id: DISPLAY_ID
    # opcode: 1
    # new id for registry: REGISTRY_ID
    connection.send_message(
        DISPLAY_ID, OPCODE_WL_DISPLAY_GET_REGISTRY, struct.pack("=I", REGISTRY_ID)
    )

    # wl_display::sync
    # display id: DISPLAY_ID
    # opcode: 0
    # new_id for callback: SYNC_ID
    connection.send_message(
        DISPLAY_ID, OPCODE_WL_DISPLAY_SYNC, struct.pack("=I", SYNC_ID)
    )

    # Read all wl_display::get_registry events
    while True:
        object_id, length, opcode, event_data_bytes = connection.recv_message()
        if object_id == SYNC_ID:
            if opcode != OPCODE_WL_CALLBACK_DONE:
                raise RuntimeError(f"Expected wl_callback::done opcode 0, got {opcode}")
            break
        elif object_id == REGISTRY_ID and opcode == OPCODE_WL_REGISTRY_GLOBAL:
            # wl_registry::global
            name, interface_length = struct.unpack("=II", event_data_bytes[:8])
            # -1 to skip null terminator
            interface = event_data_bytes[8 : 8 + interface_length - 1].decode("utf-8")
            version_start_index = round_up_power_of_two(8 + interface_length, 4)
            version = struct.unpack(
                "=I", event_data_bytes[version_start_index : version_start_index + 4]
            )[0]
            log.debug(
                "Global: name=%d, interface=%s, version=%d", name, interface, version
            )

            if interface == "wl_seat":
                seat_name = event_data_bytes
                # Bind to seat using wl_registry::bind
                # opcode 0
                # the new_id arg follows custom serialization rules (interface name, version, id). See the representation of new_id in https://wayland.freedesktop.org/docs/html/ch04.html#sect-Protocol-Wire-Format
                # new id for seat: SEAT_ID
                data = seat_name + struct.pack("=I", SEAT_ID)
                connection.send_message(REGISTRY_ID, OPCODE_WL_REGISTRY_BIND, data)
        else:
            log.debug("Ignoring event for object %d, opcode %d", object_id, opcode)

    # Read wl_seat events
    has_keyboard = False
    while True:
        object_id, length, opcode, event_data_bytes = connection.recv_message()
        if object_id == SEAT_ID and opcode == OPCODE_WL_SEAT_CAPABILITIES:
            # wl_seat::capabilities
            if length != WAYLAND_MESSAGE_HEADER_SIZE_BYTES + 4:
                raise RuntimeError(
                    f"Expected wl_seat::capabilities message to be {WAYLAND_MESSAGE_HEADER_SIZE_BYTES + 4} bytes, got {length}"
                )

            capabilities = struct.unpack("=I", event_data_bytes[:4])[0]
            log.debug("wl_seat capabilities: %s", capabilities)
            has_keyboard = capabilities & 2
            break
        elif object_id == DISPLAY_ID and opcode == OPCODE_WL_DISPLAY_ERROR:
            # wl_display::error
            raise RuntimeError(f"Wayland error: {repr(event_data_bytes)}")
        elif object_id == DISPLAY_ID and opcode == OPCODE_WL_DISPLAY_DELETE_ID:
            # wl_display::delete_id
            if length != WAYLAND_MESSAGE_HEADER_SIZE_BYTES + 4:
                raise RuntimeError(
                    f"Expected wl_display::delete_id message to be {WAYLAND_MESSAGE_HEADER_SIZE_BYTES + 4} bytes, got {length}"
                )
            id_num = struct.unpack("=I", event_data_bytes)[0]
            if id_num == SEAT_ID:
                raise RuntimeError("wl_seat was destroyed unexpectedly")
            elif id_num == KEYBOARD_ID:
                raise RuntimeError("wl_keyboard was destroyed unexpectedly")
        else:
            log.debug("Ignoring event for object %d, opcode %d", object_id, opcode)

    if not has_keyboard:
        raise RuntimeError("Wayland seat has no keyboard")

    # wl_seat::get_keyboard
    connection.send_message(SEAT_ID, 1, struct.pack("=I", KEYBOARD_ID))

    # Wait for and process wl_keyboard::keymap
    while True:
        object_id, length, opcode, event_data_bytes = connection.recv_message()
        if object_id == KEYBOARD_ID and opcode == OPCODE_WL_KEYBOARD_KEYMAP:
            # wl_keyboard::keymap
            if length != WAYLAND_MESSAGE_HEADER_SIZE_BYTES + 8:
                raise RuntimeError(
                    f"Expected wl_keyboard::keymap message to be {WAYLAND_MESSAGE_HEADER_SIZE_BYTES + 8} bytes, got {length}"
                )

            keymap_format, keymap_size = struct.unpack("=II", event_data_bytes)
            if keymap_format != WL_KEYBOARD_KEYMAP_FORMAT_XKB_V1:
                raise RuntimeError(f"Unsupported keymap format: {keymap_format}")

            try:
                fd = connection.fd_queue.popleft()
            except IndexError:
                raise RuntimeError("No keymap fd received")

            return fd, keymap_size
        elif object_id == DISPLAY_ID and opcode == OPCODE_WL_DISPLAY_ERROR:
            # wl_display::error
            raise RuntimeError(f"Wayland error: {repr(event_data_bytes)}")
        else:
            log.debug("Ignoring event for object %d, opcode %d", object_id, opcode)
