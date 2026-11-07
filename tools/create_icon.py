"""Generate QuickBox's Windows icon and PNG from simple vector-like shapes."""
from pathlib import Path
from PIL import Image, ImageDraw

size = 1024
image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((40, 40, 984, 984), radius=235, fill="#586fdf")
# An open, neatly folded box; wide strokes remain legible at taskbar sizes.
draw.rounded_rectangle((214, 366, 810, 750), radius=75, fill="#ffffff")
draw.rounded_rectangle((214, 274, 810, 440), radius=60, fill="#e7edff")
draw.rounded_rectangle((448, 490, 576, 545), radius=27, fill="#7186e7")
draw.rounded_rectangle((307, 314, 717, 342), radius=14, fill="#c4d0fb")
output = Path(__file__).resolve().parent.parent / "assets"
output.mkdir(exist_ok=True)
image.resize((256, 256), Image.Resampling.LANCZOS).save(output / "quickbox.png")
image.save(output / "quickbox.ico", sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)])
