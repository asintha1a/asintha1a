import os
import cv2
import numpy as np
from PIL import Image
from rembg import remove, new_session

def generate_ascii_portrait():
    input_path = "assets/avatar.jpg"
    output_svg = "portrait.svg"
    
    if not os.path.exists(input_path):
        print(f"Avatar not found at {input_path}")
        return

    # 1. High-Quality Background Removal
    input_image = Image.open(input_path)
    session = new_session("u2netp")
    output_image = remove(input_image, session=session)
    
    img_np = np.array(output_image)
    if img_np.shape[2] == 4:
        alpha = img_np[:, :, 3] / 255.0
        img_gray = cv2.cvtColor(img_np[:, :, :3], cv2.COLOR_RGB2GRAY)
        # Background is black (0)
        img_gray = (img_gray * alpha).astype(np.uint8)
    else:
        img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    # 2. Advanced Detail Preservation
    # Bilateral filter to keep edges while smoothing noise
    filtered = cv2.bilateralFilter(img_gray, 5, 50, 50)
    
    # Adaptive Histogram Equalization for extreme detail
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(filtered)
    
    # Unsharp mask for edge crispness
    gaussian = cv2.GaussianBlur(enhanced, (0, 0), 2.0)
    sharpened = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)
    
    # 3. Ultra-Dense Mapping
    # Gamma 0.9 for deeper shadows and bright highlights
    normalized = sharpened.astype(np.float32) / 255.0
    curved = np.power(normalized, 0.9)
    final_gray = (curved * 255).astype(np.uint8)
    
    # Professional dense ramp
    ramp = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~i!lI;:,^`'. "
    ramp = ramp[::-1]
    ramp_len = len(ramp)
    
    cols = 160 # Ultra-high resolution
    h, w = final_gray.shape
    aspect = h / w
    rows = int(cols * aspect * 0.48)
    
    resized = cv2.resize(final_gray, (cols, rows), interpolation=cv2.INTER_LANCZOS4)
    
    ascii_lines = []
    for row in resized:
        line = ""
        for pixel in row:
            if pixel < 8:
                char = "&#160;"
            else:
                idx = int((pixel / 255.0) * (ramp_len - 1))
                char = ramp[idx]
                if char == " ": char = "&#160;"
                elif char == "<": char = "&lt;"
                elif char == ">": char = "&gt;"
                elif char == "&": char = "&amp;"
            line += char
        ascii_lines.append(line)
        
    # 4. Top-Down "Live" Scanline Animation
    char_w = 6.0
    char_h = 10.0
    svg_w = cols * char_w + 40
    svg_h = rows * char_h + 40
    
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="100%" style="background-color: #0d1117; border-radius: 6px;">',
        '<style>',
        '.txt { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace; font-size: 8.5px; fill: #c9d1d9; }',
        '.scanline { fill: #58a6ff; opacity: 0.8; }',
        '</style>',
        f'<rect width="100%" height="100%" fill="#0d1117" rx="6"/>',
        f'<g transform="translate(20, 25)">'
    ]
    
    # Animation parameters
    total_duration = 4.0
    row_delay = total_duration / rows
    
    for i, line in enumerate(ascii_lines):
        y = i * char_h + 8
        begin_time = i * row_delay
        
        # Row visibility animation (Top-down)
        svg_parts.append(f'<g opacity="0">')
        svg_parts.append(f'<animate attributeName="opacity" from="0" to="1" dur="0.1s" begin="{begin_time:.3f}s" fill="freeze"/>')
        svg_parts.append(f'<text x="0" y="{y}" class="txt" xml:space="preserve">{line}</text>')
        svg_parts.append(f'</g>')
        
    # Add a "scanline" bar that moves top to bottom
    svg_parts.append(f'<rect x="0" y="0" width="{cols * char_w}" height="2" class="scanline">')
    svg_parts.append(f'<animate attributeName="y" from="0" to="{rows * char_h}" dur="{total_duration}s" begin="0s" fill="freeze"/>')
    svg_parts.append(f'<animate attributeName="opacity" from="0.8" to="0" dur="0.2s" begin="{total_duration}s" fill="freeze"/>')
    svg_parts.append(f'</rect>')

    svg_parts.append('</g>')
    svg_parts.append('</svg>')
    
    with open(output_svg, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_parts))
    print(f"Ultra-High Fidelity Portrait SVG generated at {output_svg}")

if __name__ == "__main__":
    generate_ascii_portrait()
