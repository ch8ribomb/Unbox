# Draws unbox.ico (open box + up arrow). Run once; needs Pillow.
from PIL import Image, ImageDraw
S = 256
im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
brown, dark, light = (214, 152, 78), (160, 104, 44), (236, 190, 120)
d.polygon([(28, 120), (128, 150), (228, 120), (228, 222), (128, 250), (28, 222)], fill=brown)   # box body
d.polygon([(128, 150), (228, 120), (228, 222), (128, 250)], fill=dark)                          # right side
d.polygon([(28, 120), (128, 150), (92, 186), (0, 152)], fill=light)                             # left flap
d.polygon([(228, 120), (128, 150), (164, 186), (256, 152)], fill=(196, 136, 64))                # right flap
blue = (37, 99, 235)
d.polygon([(128, 8), (196, 82), (152, 82), (152, 140), (104, 140), (104, 82), (60, 82)], fill=blue)  # arrow
im.save("unbox.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("unbox.ico written")
