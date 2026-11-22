# Składa film 1920×1080, 30 fps: jedna scena = jeden plik, potem concat bez ponownego kodowania.
# Użycie: python montaz.py [katalog-roboczy]  (domyślnie /tmp/aedane-wideo). Wymaga ffmpeg.
# Wynik: presentation/wideo-prezentacja-aedane.mp4
import json, os, pathlib, subprocess, sys
D = sys.argv[1] if len(sys.argv) > 1 else '/tmp/aedane-wideo'; BGC = '0xF4F6F8'
REPO = pathlib.Path(__file__).resolve().parents[3]
OUT = str(REPO / 'presentation/wideo-prezentacja-aedane.mp4')
ENC = ['-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-r', '30']
FADE = 0.35

def run(args, out):
    tmp = out[:-4] + '.tmp.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error'] + args + [tmp], check=True)
    os.replace(tmp, out)

def dur(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]))

def phone_scene(name, min_len=0, hold=1.2, maxgap=1.2):
    data = json.load(open(f'{D}/rec/{name}/frames.json'))
    fr = data['frames']; lst = f'{D}/rec/{name}/list.txt'; total = 0
    with open(lst, 'w') as fh:
        for i, (t, f) in enumerate(fr):
            nxt = fr[i + 1][0] if i + 1 < len(fr) else data['end']
            d = min(max(nxt - t, 1 / 30), maxgap)
            if i + 1 == len(fr): d = max(d + hold, min_len - total)
            total += d
            fh.write(f"file '{f}'\nduration {d:.4f}\n")
        fh.write(f"file '{fr[-1][1]}'\n")
    out = f'{D}/out_{name}.mp4'
    flt = (f'[1:v]fps=30,scale=434:940:flags=lanczos,format=rgba[ph];[2:v]format=gray[m];[ph][m]alphamerge[pm];'
           f'[0:v][pm]overlay=300:70:shortest=1,format=yuv420p,'
           f'fade=t=in:st=0:d={FADE}:color={BGC},fade=t=out:st={total - FADE:.3f}:d={FADE}:color={BGC}[v]')
    run(['-loop', '1', '-framerate', '30', '-i', f'{D}/bg_{name}.png', '-f', 'concat', '-safe', '0', '-i', lst,
         '-loop', '1', '-i', f'{D}/mask.png', '-filter_complex', flt, '-map', '[v]', '-t', f'{total:.3f}'] + ENC, out)
    return out

def still_phone(name, img, length):
    out = f'{D}/out_{name}.mp4'
    flt = (f'[1:v]scale=434:940:flags=lanczos,format=rgba[ph];[2:v]format=gray[m];[ph][m]alphamerge[pm];'
           f'[0:v][pm]overlay=300:70,format=yuv420p,loop=-1:1,trim=duration={length},'
           f'fade=t=in:st=0:d={FADE}:color={BGC},fade=t=out:st={length - FADE}:d={FADE}:color={BGC}[v]')
    run(['-framerate', '30', '-i', f'{D}/bg_{name}.png', '-i', img, '-i', f'{D}/mask.png',
         '-filter_complex', flt, '-map', '[v]'] + ENC, out)
    return out

def card(name, length):
    out = f'{D}/out_{name}.mp4'
    run(['-framerate', '30', '-i', f'{D}/bg_{name}.png', '-vf',
         f'format=yuv420p,loop=-1:1,trim=duration={length},fade=t=in:st=0:d=0.5:color={BGC},fade=t=out:st={length - 0.5}:d=0.5:color={BGC}'] + ENC, out)
    return out

parts = [card('intro', 3.5),
         phone_scene('s1', min_len=5.0),
         phone_scene('s2', min_len=8.0),
         phone_scene('s3', min_len=6.5),
         still_phone('g', str(REPO / 'presentation/zrzuty/obywatel-4-trasa-google.jpg'), 5.0),
         phone_scene('s4', min_len=9.0),
         phone_scene('s5', min_len=7.0),
         phone_scene('s6', min_len=8.0),
         card('outro', 5.5)]
with open(f'{D}/parts.txt', 'w') as fh:
    for p in parts: fh.write(f"file '{p}'\n")
run(['-f', 'concat', '-safe', '0', '-i', f'{D}/parts.txt', '-c', 'copy', '-movflags', '+faststart'], OUT)
for p in parts: print(os.path.basename(p), round(dur(p), 2))
print('razem', round(dur(OUT), 1), 's')
