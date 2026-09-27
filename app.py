import gradio as gr
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.transform import from_origin
import os, tempfile, time
from pathlib import Path

def get_props(tif_path):
    try:
        with rasterio.open(tif_path) as src:
            bounds = src.bounds
            return {
                "File": os.path.basename(tif_path),
                "Size": f"{os.path.getsize(tif_path)/1024/1024:.2f} MB",
                "W x H": f"{src.width} x {src.height}",
                "Count/Bands": src.count,
                "Dtype": str(src.dtypes[0]),
                "EPSG": src.crs.to_epsg() if src.crs else "unknown",
                "CRS": str(src.crs),
                "Compression": src.profile.get('compress','none'),
                "BBox": f"{bounds.left:.6f}, {bounds.bottom:.6f}, {bounds.right:.6f}, {bounds.top:.6f}",
                "Transform": str(src.transform)[:80]+"...",
            }
    except Exception as e:
        return {"Error": str(e)}

def compress_reproject_tif(input_file, progress=gr.Progress(track_tqdm=True)):
    logs = []
    def log(msg):
        logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        return "\n".join(logs)

    tmpdir = tempfile.mkdtemp()
    input_path = input_file.name if hasattr(input_file, 'name') else input_file
    orig_name = Path(input_path).stem
    out_name = f"{orig_name}_gprz.tif"
    out_path = os.path.join(tmpdir, out_name)

    try:
        progress(0.05, desc="Baca file...")
        yield log("1. Baca file arrayBuffer"), {}, {}, None
        before = get_props(input_path)
        yield log(f"1. File OK {before.get('W x H')} EPSG:{before.get('EPSG')}"), before, {}, None

        progress(0.2, desc="Cek EPSG & hitung transform ke 4326...")
        with rasterio.open(input_path) as src:
            src_crs = src.crs
            dst_crs = 'EPSG:4326'
            yield log(f"2. EPSG detected = {src_crs} -> 4326"), before, {}, None

            transform, width, height = calculate_default_transform(
                src_crs, dst_crs, src.width, src.height, *src.bounds
            )

            profile = src.profile.copy()
            profile.update({
                'crs': dst_crs,
                'transform': transform,
                'width': width,
                'height': height,
                'compress': 'JPEG',
                'jpeg_quality': 20,
                'tiled': True,
                'BIGTIFF': 'IF_SAFER',
                'photometric': 'YCBCR' if src.count==3 else 'MINISBLACK'
            })
            # Untuk RGB harus YCBCR biar Q20 ngaruh gede
            if src.count >= 3:
                profile.update(dtype='uint8')

            progress(0.4, desc="Baca raster & reproject (paling berat)...")
            yield log(f"3. Reproject {src.width}x{src.height} -> {width}x{height} + JPEG Q20"), before, {}, None

            with rasterio.open(out_path, 'w', **profile) as dst:
                for i in range(1, src.count+1):
                    progress(0.4 + 0.5 * (i/src.count), desc=f"Reproject band {i}/{src.count}")
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src_crs,
                        dst_transform=transform,
                        dst_crs=dst_crs,
                        resampling=Resampling.bilinear
                    )
                    yield log(f"4. Band {i} reproject DONE"), before, {}, None

        progress(0.9, desc="Baca hasil...")
        after = get_props(out_path)
        yield log(f"5. Selesai! Before {before.get('Size')} -> After {after.get('Size')}"), before, after, None

        progress(1.0, desc="Auto download...")
        yield log(f"6. Auto download {out_name}"), before, after, out_path

    except Exception as e:
        err = f"❌ ERROR: {str(e)}"
        yield log(err), before if 'before' in locals() else {}, {}, None

# === UI GLASS ===
css = """
:root{--pink:#ffd6e0;--blue:#c1e7ff;--mint:#c7f5d9;--lav:#e2d1f9;}
body{background: radial-gradient(1200px 600px at 30% -10%, var(--pink), transparent), radial-gradient(1000px 500px at 90% 10%, var(--blue), transparent), radial-gradient(900px 600px at 50% 110%, var(--mint), #fcf6f8)!important;}
.gradio-container{max-width:1050px!important; margin:auto;}
.glass{background:rgba(255,255,255,0.75)!important; backdrop-filter: blur(18px); border-radius:28px!important; border:1px solid #fff!important; box-shadow:0 20px 60px rgba(0,0,0,0.08)!important; padding:24px!important;}
.drop{border:2.5px dashed #d8cfe0!important; border-radius:22px!important; background: linear-gradient(180deg,rgba(255,214,224,0.45),rgba(193,231,255,0.35))!important;}
#logbox{ background:#1e1e2a!important; color:#c7f5d9!important; font-family:Consolas,monospace!important; font-size:12px; border-radius:14px; max-height:280px; overflow:auto; white-space:pre-wrap; }
"""

with gr.Blocks(css=css, title="GeoTIFF Compressor 4326 Q20") as demo:
    gr.Markdown("# 🧁 GeoTIFF → 4326 Compressor Q20 - GPRZ\nDrop.tif → auto cek EPSG → force 4326 → JPEG Q20 → download `_gprz.tif`")
    with gr.Column(elem_classes="glass"):
        file_in = gr.File(label="📦 Drop.tif di sini", elem_classes="drop", file_types=[".tif",".tiff"])
        with gr.Row():
            before_json = gr.JSON(label="BEFORE (ORIGINAL)")
            after_json = gr.JSON(label="AFTER (4326 + Q20)")
        logbox = gr.Textbox(label="PROGRESS & LOG", lines=12, elem_id="logbox")
        out_file = gr.File(label="⬇️ Auto download _gprz.tif", interactive=False)

    file_in.upload(compress_reproject_tif, inputs=file_in, outputs=[logbox, before_json, after_json, out_file])

demo.launch(server_name="0.0.0.0", server_port=7860)