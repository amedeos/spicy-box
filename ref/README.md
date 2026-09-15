# Reference photographs

Two sets of pictures: the tubes the carousel was designed around, so the
defaults in `src/spicy_box/params.py` can be traced back to something real, and
the part as it came off the printer.

## The tubes the measurements came from

Re-shoot these if the tube set ever changes.

| Photograph | What it establishes |
| --- | --- |
| `body-diameter-on-calipers.jpg` | Calipers across the tube body read **19.95 mm**, rounded to 20.0 in `tube_dia`. This is the measurement the pocket diameter is derived from. |
| `tube-length-and-flat-bottom.jpg` | One tube laid diagonally over the box shows the full length (**~180 mm** of body) and, at the lower end, that the bottom is **flat with a rounded edge** — which is why the pockets have flat floors. |
| `tubes-in-original-box.jpg` | The set as it was stored: five tubes lying down in a wooden box. It also shows that the **cap sits flush** with the body and that the paper label wraps around the upper part, so the widest rigid part of a tube is the body rather than the cap. |

That wooden box is the problem this project solves. To use one tube you have to
open the lid and slide it out sideways, which is awkward mid-cooking. Hence a
holder that stands them upright.

## The printed result

| Photograph | What it shows |
| --- | --- |
| `printed-carousel.jpg` | The finished part in PLA, holding the set. The opening low on the front face is a window, pointed at the top so it prints without support. It measures 25 mm, which is what a `band_height` of 40 mm leaves on a 73 mm body — `--band-height 30` would make it 35 mm. |
| `printed-carousel-and-coupon.jpg` | The same part with the calibration coupon in front of it, its five holes labelled 0.4 to 1.6. Trying a tube in each is how `clearance` was settled at 0.7 mm. |

Both were shot on the bed of a Prusa MK4, printed in PLA at 0.2 mm layers,
upright and without support.
