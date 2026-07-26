# Hardware Communication

This page covers the details of communication protocols Plover uses to capture
keyboard or steno writer input.

## Keyboard Capture & Output

Three implementations of keyboard capture and output are currently available:

- The **Windows** implementation installs low-level event hooks to listen for
  key presses, and the Win32 API's [`SendInput`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput) to generate keystrokes.

- The **macOS** implementation uses Quartz's Event Services API: [event taps](https://developer.apple.com/documentation/coregraphics/1454426-cgeventtapcreate)
  to listen for key presses, and [keyboard events](https://developer.apple.com/documentation/coregraphics/1456564-cgeventcreatekeyboardevent)
  to generate keystrokes.

- For **Linux** and **BSD**, there are two implementations. If the display server is `x11`, an implementation based on Xlib's `xinput` is used to
  listen for key presses, and `xtest.fake_input` to generate keystrokes. For all other display servers, for example `wayland`, an implementation based
  on `evdev` is used to listen for key presses, and `uinput` to generate keystrokes. The `uinput` implementation needs to know the keyboard layout of the
  system, which can be configured in the Plover `Output` configuration tap.

Before implementing new keyboard capture and output mechanisms for a new
platform, make sure to set up the [platform layer](platform_layer) for your
platform.

### Capture

New keyboard capture methods can be implemented as a subclass of
{class}`Capture<plover.machine.keyboard_capture.Capture>`; your implementation
should translate platform-specific events into calls to
{meth}`key_down<plover.machine.keyboard_capture.Capture.key_down>` and {meth}`key_up<plover.machine.keyboard_capture.Capture.key_up>`.

```python
class MyKeyboardCapture(Capture):
    def start(self):
        self._thread = threading.Thread(target=self._run)
        self._thread.start()

    def _run(self):
        while True:
            key, pressed = ...  # wait for key event

            if pressed:
                self.key_down(key)
            else:
                self.key_up(key)
```

Plover's engine handles translating these calls into steno strokes, as well as
handling keymaps and arpeggiation.

### Output

New keyboard emulation methods can be implemented as a subclass of
{class}`Output<plover.output.Output>`. It _must_ implement all of the methods
specified, by translating them to platform-specific input calls.

```python
class MyKeyboardEmulation(Output):
    def send_backspaces(self, num): ...

    def send_string(self, s): ...

    def send_key_combination(self, combo): ...
```

## Serial Protocols

Plover supports communicating with hobbyist, student, and professional steno
writers through a serial interface. The most common protocols are Gemini PR
for hobbyist writers and Stentura for Stenograph writers, but custom protocols
may be implemented.

The {class}`SerialStenotypeBase<plover.machine.base.SerialStenotypeBase>` class
handles all of the connection establishment and configuration; when
implementing a new serial interface, you only need to define your key layout
and implement a way to parse each packet.

```python
class MySerialMachine(SerialStenotypeBase):
    KEYS_LAYOUT = """
    ...
  """

    def run(self): ...
```

## USB-based Protocols

```{todo}
Complete this section.
```

## Other Protocols

```{todo}
Complete this section.
```
