"""Render a silent 2D projection of the actual MuJoCo evaluation CSV."""
from __future__ import annotations
import argparse
import csv
import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W,H,FPS = 1280,720,30


def font(size, bold=False):
    candidate = Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc")
    return ImageFont.truetype(str(candidate), size) if candidate.exists() else ImageFont.load_default(size=size)


def dash(draw, p, q, color, width=3, period=14):
    dx=q[0]-p[0]; dy=q[1]-p[1]; length=math.hypot(dx,dy)
    if length == 0: return
    for start in range(0,int(length),period):
        end=min(start+period*.55,length)
        draw.line((p[0]+dx*start/length,p[1]+dy*start/length,
                   p[0]+dx*end/length,p[1]+dy*end/length),fill=color,width=width)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts",type=Path,default=Path("artifacts"))
    parser.add_argument("--ffmpeg",type=Path,required=True)
    args=parser.parse_args()
    with (args.artifacts/"trace_first_episode.csv").open(encoding="utf-8",newline="") as f:
        rows=list(csv.DictReader(f))
    series={name:[r for r in rows if r["policy"]==name] for name in ("zero","ppo")}
    if not series["zero"] or len(series["zero"])!=len(series["ppo"]):
        raise ValueError("Expected matching baseline and PPO traces")
    if any(a["seed"]!=b["seed"] or a["target_rad"]!=b["target_rad"] for a,b in zip(series["zero"],series["ppo"])):
        raise ValueError("Baseline and PPO traces must share the same test condition")
    target=float(series["ppo"][0]["target_rad"]); seed=series["ppo"][0]["seed"]
    n=len(series["ppo"]); duration_sim=n*.02; duration_video=n/FPS
    playback=duration_sim/duration_video
    out=args.artifacts/"joint_sim_comparison.mp4"
    command=[str(args.ffmpeg),"-hide_banner","-loglevel","error","-y","-f","rawvideo","-pix_fmt","rgb24",
             "-s",f"{W}x{H}","-r",str(FPS),"-i","pipe:0","-an","-c:v","libx264","-crf","19",
             "-pix_fmt","yuv420p","-movflags","+faststart",str(out)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        for i in range(n):
            im=Image.new("RGB",(W,H),"#0a111a");d=ImageDraw.Draw(im)
            d.text((46,25),"单关节：谁更接近目标？",font=font(31,True),fill="#f2faf8")
            d.text((48,76),f"MuJoCo 仿真  /  固定初值 {seed}  /  仿真 {duration_sim:.1f} 秒以 {playback:.1f} 倍速呈现",font=font(18),fill="#93a9b7")
            for j,(name,title,color) in enumerate((("zero","零位置基线","#a0b2c1"),("ppo","PPO 策略","#58e0b6"))):
                x0=45+j*615;x1=x0+575
                d.rounded_rectangle((x0,120,x1,525),radius=16,fill="#121e2a",outline="#2a3a4a",width=2)
                d.text((x0+26,140),f"0{j+1} / {title}",font=font(23,True),fill=color)
                cx=x0+286;cy=230;length=165
                q=float(series[name][i]["angle_rad"])
                tx=cx-math.sin(target)*length;ty=cy+math.cos(target)*length
                px=cx-math.sin(q)*length;py=cy+math.cos(q)*length
                dash(d,(cx,cy),(tx,ty),"#e8b96b",4,15)
                d.line((cx,cy,px,py),fill=color,width=13)
                d.ellipse((px-10,py-10,px+10,py+10),fill=color)
                d.ellipse((cx-11,cy-11,cx+11,cy+11),fill="#f1fffa")
                d.text((x0+25,455),f"当前角 {math.degrees(q):+.1f}°",font=font(20,True),fill=color)
                d.text((x0+300,455),f"目标 {math.degrees(target):+.1f}°",font=font(19),fill="#e8b96b")
                d.text((x0+25,488),f"误差 {abs(math.degrees(target-q)):.1f}°",font=font(16),fill="#a8b8c2")
            left,right,top,bottom=78,1203,555,645
            d.line((left,bottom,right,bottom),fill="#465665",width=2)
            d.text((46,535),f"实际角度轨迹   ·   仿真时间 {float(series['ppo'][i]['time_s']):.2f} / {duration_sim:.1f} s",font=font(16),fill="#b6c6ce")
            low=-1.0;high=1.0
            def xy(k,val): return (left+(right-left)*k/(n-1),bottom-(bottom-top)*(val-low)/(high-low))
            dash(d,xy(0,target),xy(n-1,target),"#e8b96b",2,12)
            for name,col in (("zero","#a0b2c1"),("ppo","#58e0b6")):
                points=[xy(k,float(series[name][k]["angle_rad"])) for k in range(i+1)]
                if len(points)>1:d.line(points,fill=col,width=4)
            d.text((47,674),"实线：仿真关节角   /   黄色虚线：目标角",font=font(16),fill="#a7b8c0")
            d.text((863,674),"教学模型 · 非真机",font=font(16,True),fill="#ecbf81")
            if i==min(75,n-1):im.save(args.artifacts/"joint_video_preview.png")
            process.stdin.write(im.tobytes())
        process.stdin.close()
        returncode=process.wait()
    finally:
        if process.poll() is None:
            process.kill();process.wait()
    if returncode:
        raise SystemExit(f"FFmpeg failed with {returncode}")
    print(f"Saved {out} ({duration_video:.2f}s, {n} actual MuJoCo samples, silent)")


if __name__=="__main__":
    main()
