import gradio as gr, os, subprocess, tempfile, json
import rasterio
from pathlib import Path

def get_props(p):
    with rasterio.open(p) as src:
        b=src.bounds
        return {
            "File": os.path.basename(p),
            "Size": f"{os.path.getsize(p)/1024/1024:.2f} MB",
            "WxH": f"{src.width}x{src.height}",
            "Bands": src.count,
            "EPSG": str(src.crs),
            "BBox": f"{b.left:.4f},{b.bottom:.4f},{b.right:.4f},{b.top:.4f}",
            "Compress": src.profile.get('compress','none')
        }

def process(file, progress=gr.Progress()):
    tmpdir=tempfile.mkdtemp()
    in_path=file.name
    out_name=Path(in_path).stem+"_gprz.tif"
    out_path=os.path.join(tmpdir,out_name)
    
    logs=[]
    def y(m,b,a): 
        logs.append(m)
        return "\n".join(logs), b, a, None

    before=get_props(in_path)
    yield y(f"✓ Baca {before['WxH']} {before['EPSG']}", before, {}, None)

    # gdalwarp ini yang paling hemat RAM buat 512MB
    cmd=[
        "gdalwarp",
        "-t_srs", "EPSG:4326",
        "-co", "COMPRESS=JPEG",
        "-co", "JPEG_QUALITY=20",
        "-co", "TILED=YES",
        "-co", "PHOTOMETRIC=YCBCR",
        "-r", "bilinear",
        "-overwrite",
        in_path, out_path
    ]
    progress(0.5, "Reproject & Compress Q20 (gdalwarp)...")
    yield y("⏳ Reproject 32750 -> 4326 + JPEG Q20...", before, {}, None)
    
    result=subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode!=0:
        yield y(f"❌ GDAL ERROR:\n{result.stderr}", before, {}, None)
        return

    after=get_props(out_path)
    yield y(f"✅ DONE {before['Size']} -> {after['Size']}\nAuto download {out_name}", before, after, out_path)

css="""
body{background:radial-gradient(800px 400px at 20% 0%,#ffd6e0,transparent),radial-gradient(800px 400px at 90% 10%,#c1e7ff,transparent),#fcf6f8!important}
.gradio-container{max-width:1000px!important}
.glass{background:rgba(255,255,255,0.8)!important;backdrop-filter:blur(18px);border-radius:24px!important;padding:20px!important}
"""

with gr.Blocks(css=css, title="GPRZ Compressor") as demo:
    gr.Markdown("## 🧁 GPRZ TIFF Compressor 4326 Q20")
    with gr.Column(elem_classes="glass"):
        f=gr.File(label="Drop .tif", file_types=[".tif",".tiff"])
        with gr.Row():
            bj=gr.JSON(label="BEFORE")
            aj=gr.JSON(label="AFTER")
        log=gr.Textbox(label="PROGRESS", lines=10)
        out=gr.File(label="Download _gprz.tif")
    f.upload(process, f, [log,bj,aj,out])

if __name__=="__main__":
    port=int(os.environ.get("PORT",7860))
    demo.launch(server_name="0.0.0.0", server_port=port)
