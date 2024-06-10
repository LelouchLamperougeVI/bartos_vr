from PIL import Image, ImageDraw
import matplotlib.pyplot as plt

colours = {
    '_b': (0, 0, 255), # 440 nm
    '_l': (0, 137, 255),  # 463 nm
    '_c': (0, 243, 255),  # 487 nm
    '_g': (0, 255, 0),  # 510 nm
}
sz = (240, 240)

im = Image.new('RGB', size=sz)
draw = ImageDraw.Draw(im)
draw.ellipse(xy=[(60, 60), (180, 180)], fill=colours['_c'], width=0)
im = im.resize((480, 480), Image.LANCZOS)

plt.imshow(im)
im.save('test.png')
