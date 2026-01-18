``plover.machine.keyboard_capture`` -- Keyboard capture
================================================================

.. automodule:: plover.machine.keyboard_capture
   :no-members:

.. autoclass:: plover.machine.keyboard_capture.Capture

   .. automethod:: plover.machine.keyboard_capture.Capture.start

   .. automethod:: plover.machine.keyboard_capture.Capture.cancel

   .. automethod:: plover.machine.keyboard_capture.Capture.suppress

   The following methods are available to implementors to hook into the
   keyboard capture system:

   .. automethod:: plover.machine.keyboard_capture.Capture.key_down

   .. automethod:: plover.machine.keyboard_capture.Capture.key_up
