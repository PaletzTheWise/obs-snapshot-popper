This is a script that can be loaded by OBS (Tools -> Scripts). It creates a new hotkey that can be bound. When the user hits the hotkey, displays a snapshot of the configured capture source on the configured display (image) source. This can be configured to only display a snapshot that is sufficiently old ("look-behind"), which can be helpful to prevent inadvertent display of sudden inappropriate content from the capture source. For example the source is chat and somebody posts an offensive message just as you hit the hotkey.

This script uses the obs-screenshot-filter which must be installed separately.

![image](https://github.com/user-attachments/assets/46516f0a-5dc3-4f72-8446-47bb7e1c3812)

Tip: The script respects "Show Transition" and "Hide Transition" configured on the display source. You can find these settings by right-clicking on the source in the OBS source tab.
