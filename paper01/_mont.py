import glob, os, subprocess, sys
from PIL import Image
pdf = sys.argv[1]
os.makedirs("_thumb", exist_ok=True)
for f in glob.glob("_thumb/*.png"): os.remove(f)
subprocess.run(["pdftoppm", "-r", "28", "-png", pdf, "_thumb/p"], check=True)
fs = sorted(glob.glob("_thumb/p*.png"))
ims = [Image.open(f) for f in fs]
w, h = ims[0].size
cols = 7
rows = (len(ims) + cols - 1) // cols
M = Image.new("RGB", (cols * (w + 6), rows * (h + 6)), "gray")
for i, im in enumerate(ims):
    M.paste(im, ((i % cols) * (w + 6), (i // cols) * (h + 6)))
M.save("_montage.png")
print(len(ims), "pages")
