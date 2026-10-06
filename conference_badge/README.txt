CONF BADGE for Tufty 2350
=========================

Install
  1. Plug the Tufty in over USB-C and double-tap RESET. A drive called TUFTY appears.
  2. Copy the conf_badge folder into the apps folder on that drive.
  3. Eject the drive and press RESET. "Conf Badge" is in the menu (orange ML icon).

If it errors on launch, update the badge firmware first (badgewa.re/docs,
"Firmware updates"); this app is written against the v3 Badgeware API.

Controls
  C / DOWN   next screen
  A / UP     previous screen
  B          jump to the QR screen
  HOME       back to the menu
  After a press, page dots and a battery gauge show along the bottom for 1.5s.

Screens
  Every .png / .jpg in conf_badge/assets is a screen, in filename order:
    2_card.png   name, role, QR to leonematt.com
    3_qr.png     big QR for scanning
  Add your PyTorch badge as 1_badge.png so it comes up first:
    pip install pillow
    python fit_image.py your_badge_photo.jpg          (fits inside 320x240)
    python fit_image.py your_badge_photo.jpg --fill   (crops to fill)
  You can also drop a JPG straight in; the app scales it, but fit_image.py
  gives sharper results.

Battery
  1000mAh, roughly a conference day with the backlight on. Bring a USB-C cable.
