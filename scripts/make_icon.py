"""Make the BodyTalk icon files from the one master picture, build/icon-source.png.

Run it from the project folder with the pipeline's Python, which already has the image library it
needs:

    pipeline/.venv/Scripts/python.exe scripts/make_icon.py

That writes two things, both from the same master, so they always match:

- build/icon.ico, the Windows icon for the program, the installer and the uninstaller; and
- src/renderer/src/assets/logo.png, the logo in the app's own top bar.

To change the icon, give it a new picture:

    pipeline/.venv/Scripts/python.exe scripts/make_icon.py --from path/to/picture.png

The picture is trimmed to what is actually drawn, ignoring any see-through margin, centred on a
square, and saved as the new master before the icon files are made from it. A picture that is not
square to begin with is not stretched; the spare room is left see-through.

Why each size is made separately. A Windows icon file holds the picture at several sizes, and
Windows picks whichever suits the place it is shown: 16 pixels in a title bar, 32 on the taskbar,
256 on a large desktop. Letting Windows shrink the largest one itself gives a poorer result than
reducing the master carefully to each size here. The smallest sizes are also sharpened a little,
because a detailed picture reduced to 16 or 24 pixels otherwise softens into a blur.
"""

from __future__ import annotations

import io
import struct
import sys
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "build" / "icon-source.png"
ICON = ROOT / "build" / "icon.ico"
LOGO = ROOT / "src" / "renderer" / "src" / "assets" / "logo.png"

#: The master is kept at this size: twice the largest the icon file holds, which is plenty.
MASTER_SIZE = 512

#: The sizes Windows asks for across its usual display scalings.
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)

#: At or below this size, a little sharpening keeps a detailed picture from going soft.
SHARPEN_AT_OR_BELOW = 40

#: The top-bar logo is shown at 32 by 32; four times that covers the sharpest screens.
LOGO_SIZE = 128


def prepare_master(picture: Path) -> None:
    """Trim a supplied picture to its drawn area, square it up, and save it as the master.

    Saved as a fresh image rather than copied, so it holds the pixels and nothing else.
    """
    image = Image.open(picture).convert("RGBA")
    # Anything more than faintly see-through counts as drawn; a soft glow at the edge is kept.
    drawn = image.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if drawn is None:
        sys.exit("That picture is entirely see-through, so there is nothing to make an icon from.")
    art = image.crop(drawn)
    side = max(art.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(art, ((side - art.width) // 2, (side - art.height) // 2), art)
    master = square.resize((MASTER_SIZE, MASTER_SIZE), Image.Resampling.LANCZOS)
    MASTER.parent.mkdir(parents=True, exist_ok=True)
    master.save(MASTER, format="PNG", optimize=True)
    print(f"Saved the master, {MASTER.relative_to(ROOT)}, at {MASTER_SIZE} by {MASTER_SIZE}.")


def at_size(master: Image.Image, size: int) -> Image.Image:
    """The master reduced to one size, sharpened a little if it is one of the small ones."""
    image = master.resize((size, size), Image.Resampling.LANCZOS)
    if size <= SHARPEN_AT_OR_BELOW:
        image = image.filter(ImageFilter.UnsharpMask(radius=0.6, percent=60, threshold=1))
    return image


def write_ico(images: list[Image.Image], target: Path) -> None:
    """Save the sizes as one icon file, each stored as a PNG, which Windows has read since Vista.

    Written out by hand rather than left to the image library, because the library makes the
    smaller sizes by shrinking the largest itself, and the sizes made above would be ignored.
    """
    payloads = []
    for image in images:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        payloads.append(buffer.getvalue())

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    directory = b""
    for image, payload in zip(images, payloads):
        width, height = image.size
        directory += struct.pack(
            "<BBBBHHII",
            width if width < 256 else 0,  # 256 is written as 0, by the format's own rule
            height if height < 256 else 0,
            0,  # no palette
            0,
            1,  # colour planes
            32,  # bits per pixel
            len(payload),
            offset,
        )
        offset += len(payload)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(header + directory + b"".join(payloads))


def main() -> None:
    if "--from" in sys.argv:
        prepare_master(Path(sys.argv[sys.argv.index("--from") + 1]))
    if not MASTER.exists():
        sys.exit(f"There is no master picture yet. Give one with --from, as described at the top.")

    master = Image.open(MASTER).convert("RGBA")
    if master.size != (MASTER_SIZE, MASTER_SIZE):
        sys.exit(f"The master should be {MASTER_SIZE} by {MASTER_SIZE}; make it again with --from.")

    write_ico([at_size(master, size) for size in SIZES], ICON)
    LOGO.parent.mkdir(parents=True, exist_ok=True)
    master.resize((LOGO_SIZE, LOGO_SIZE), Image.Resampling.LANCZOS).save(LOGO, format="PNG", optimize=True)
    print(f"Wrote {ICON.relative_to(ROOT)} with sizes {', '.join(map(str, SIZES))},")
    print(f"and {LOGO.relative_to(ROOT)} at {LOGO_SIZE} by {LOGO_SIZE}.")


if __name__ == "__main__":
    main()
