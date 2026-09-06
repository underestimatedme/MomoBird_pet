"""Pack generated MomoBird artwork into Codex v1 animation cells."""
from collections import deque
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent
SOURCE = Path('/Users/joey/.codex/generated_images/01a07701-6ef8-76b3-92d1-01c15f2aa45a/exec-b8461c98-66b2-44c0-85ff-b01a05539356.png')
source = Image.open(SOURCE).convert('RGB')
xs = [8, 172, 323, 472, 619, 765, 916, 1072]
ys = [0, 160, 305, 449, 602, 761, 906, 1057, 1200, 1385]
counts = [6, 8, 8, 4, 5, 8, 6, 6, 6]

def cutout(box):
    rgb = np.array(source.crop(box))
    high = rgb.max(axis=2).astype(int)
    low = rgb.min(axis=2).astype(int)
    # Only neutral pixels connected to the crop edge are background.
    eligible = ((high-low) < 12) & (low > 100)
    h, w = eligible.shape
    removed = np.zeros((h, w), dtype=bool)
    queue = deque([(x, y) for y in range(h) for x in (0, w-1)] +
                  [(x, y) for x in range(w) for y in (0, h-1)])
    while queue:
        x, y = queue.popleft()
        if x < 0 or y < 0 or x >= w or y >= h or removed[y, x] or not eligible[y, x]:
            continue
        removed[y, x] = True
        queue.extend(((x-1,y), (x+1,y), (x,y-1), (x,y+1)))
    alpha = np.where(removed, 0, 255).astype('uint8')
    # Keep the main connected silhouette, dropping isolated background remnants.
    seen = removed.copy()
    components = []
    for y, x in zip(*np.where(~removed)):
        if seen[y,x]:
            continue
        component = []
        queue = deque([(int(x), int(y))])
        seen[y,x] = True
        while queue:
            cx, cy = queue.popleft()
            component.append((cx, cy))
            for nx, ny in ((cx-1,cy),(cx+1,cy),(cx,cy-1),(cx,cy+1)):
                if 0 <= nx < w and 0 <= ny < h and not seen[ny,nx]:
                    seen[ny,nx] = True
                    queue.append((nx,ny))
        components.append(component)
    for component in components:
        if len(component) < max(len(c) for c in components) * 0.08:
            for x,y in component:
                alpha[y,x] = 0
    # Close tiny breaks in pale facial contours and fill enclosed transparent holes.
    alpha = np.array(Image.fromarray(alpha).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5)))
    outside = np.zeros((h,w), dtype=bool)
    queue = deque([(x,y) for y in range(h) for x in (0,w-1)] + [(x,y) for x in range(w) for y in (0,h-1)])
    while queue:
        x,y = queue.popleft()
        if not (0 <= x < w and 0 <= y < h) or outside[y,x] or alpha[y,x]:
            continue
        outside[y,x] = True
        queue.extend(((x-1,y),(x+1,y),(x,y-1),(x,y+1)))
    alpha[~outside] = 255
    alpha = np.array(Image.fromarray(alpha).filter(ImageFilter.MinFilter(3)))
    alpha[int(h*0.8):,:][(high-low)[int(h*0.8):,:] < 35] = 0
    rgba = np.dstack((rgb, alpha))
    rgba[alpha == 0,:3] = 0
    result = Image.fromarray(rgba)
    bounds = result.getbbox()
    assert bounds is not None
    return result.crop(bounds)

sheet = Image.new('RGBA', (1536,1872))
for row, count in enumerate(counts):
    frames = [cutout((xs[col],ys[row],xs[col+1],ys[row+1])) for col in range(7)]
    # Uniform scale within each animation retains the generated pose proportions.
    scale = min(156/max(f.width for f in frames), 174/max(f.height for f in frames))
    for col in range(count):
        frame = frames[[2,3,5,6,3,2][col]] if row == 8 else frames[col % len(frames)]
        frame = frame.resize((round(frame.width*scale),round(frame.height*scale)), Image.Resampling.LANCZOS)
        lift = [0,8,18,8,0][col] if row == 4 else 0
        sheet.alpha_composite(frame, (col*192+(192-frame.width)//2, row*208+194-frame.height-lift))

output = ROOT/'spritesheet.png'
sheet.save(output)
manifest = {'displayName':'MomoBird','description':'彩色 MomoBird 动画宠物','spriteVersionNumber':1,'spritesheetPath':'spritesheet.png'}
(ROOT/'pet.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')

# Validate required frames against the app's fixed grid and alpha requirements.
reloaded = Image.open(output)
assert reloaded.size == (1536,1872) and reloaded.mode == 'RGBA'
for row,count in enumerate(counts):
    for col in range(8):
        alpha = np.array(reloaded.crop((col*192,row*208,(col+1)*192,(row+1)*208)).getchannel('A'))
        if col < count:
            assert (alpha == 0).any() and (alpha > 200).any(), (row,col)
            assert not alpha[0,:].any() and not alpha[-1,:].any()
            assert not alpha[:,0].any() and not alpha[:,-1].any()
        else:
            assert not alpha.any()
assert output.stat().st_size < 20*1024*1024
print(f'PASS: {sum(counts)} required frames, transparent margins, empty unused cells, valid manifest; {output.stat().st_size} bytes')
