"""Render a portable vertical video from a JSON storyboard and existing narration."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'04_自动化生产流水线'))
from workspace_paths import ffmpeg


def render(spec_path,output):
    spec_path=Path(spec_path).resolve();spec=json.loads(spec_path.read_text(encoding='utf-8'))
    def asset(s):
        p=Path(s)
        if not p.is_absolute():p=(spec_path.parent/p).resolve()
        if not p.is_file():raise FileNotFoundError(p)
        return p
    audio=asset(spec['audio']);shots=spec['shots']
    if not shots:raise ValueError('Storyboard is empty')
    output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    width=int(spec.get('width',1080));height=int(spec.get('height',1920));fps=int(spec.get('fps',25))
    exe=ffmpeg()
    with tempfile.TemporaryDirectory(prefix='scys-render-') as t:
        temp=Path(t);clips=[]
        for i,s in enumerate(shots):
            image=asset(s['image']);duration=float(s['duration'])
            if duration<=0:raise ValueError('Shot duration must be positive')
            dest=temp/f'{i:04d}.mp4';clips.append(dest)
            vf=f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1'
            subprocess.run([exe,'-nostdin','-hide_banner','-loglevel','error','-y','-loop','1','-i',str(image),'-t',str(duration),'-vf',vf,'-r',str(fps),'-c:v','libx264','-preset','veryfast','-pix_fmt','yuv420p',str(dest)],check=True)
        listing=temp/'clips.txt';listing.write_text(''.join("file '"+p.as_posix()+"'\n" for p in clips),encoding='utf-8')
        if 'subtitles' in spec:
            shutil_path=asset(spec['subtitles'])
            import shutil
            shutil.copyfile(shutil_path,temp/'subtitles.srt')
            opts=['-vf','subtitles=subtitles.srt','-c:v','libx264','-preset','veryfast']
        else:opts=['-c:v','copy']
        subprocess.run([exe,'-nostdin','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-i',str(audio),'-map','0:v:0','-map','1:a:0',*opts,'-c:a','aac','-shortest','-movflags','+faststart',str(output)],cwd=temp,check=True)
    print(output)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('storyboard');ap.add_argument('--output',required=True);a=ap.parse_args();render(a.storyboard,a.output)
