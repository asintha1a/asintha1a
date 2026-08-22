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

    # 1. Ultra-High-Quality Image Processing
    input_image = Image.open(input_path)
    session = new_session("u2netp")
    output_image = remove(input_image, session=session)
    
    img_np = np.array(output_image)
    if img_np.shape[2] == 4:
        alpha = img_np[:, :, 3] / 255.0
        img_gray = cv2.cvtColor(img_np[:, :, :3], cv2.COLOR_RGB2GRAY)
        img_gray = (img_gray * alpha).astype(np.uint8)
    else:
        img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    # Advanced Contrast & Detail Enhancement
    # Dual-pass CLAHE for extreme feature definition
    clahe1 = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe1.apply(img_gray)
    clahe2 = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    enhanced = clahe2.apply(enhanced)
    
    # Bilateral filter for high-frequency noise reduction while keeping edges sharp
    filtered = cv2.bilateralFilter(enhanced, 5, 50, 50)
    
    # Unsharp Masking for crisp details
    gaussian = cv2.GaussianBlur(filtered, (0, 0), 1.5)
    sharpened = cv2.addWeighted(filtered, 1.8, gaussian, -0.8, 0)
    
    # Gamma adjustment for professional tonal range
    normalized = sharpened.astype(np.float32) / 255.0
    curved = np.power(normalized, 0.85)
    final_gray = (curved * 255).astype(np.uint8)
    
    # Professional dense ramp for realistic shading
    ramp = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~i!lI;:,^`'. "
    ramp = ramp[::-1]
    ramp_len = len(ramp)
    
    cols = 180 # Ultra-high detail
    h, w = final_gray.shape
    aspect = h / w
    rows = int(cols * aspect * 0.48)
    
    resized = cv2.resize(final_gray, (cols, rows), interpolation=cv2.INTER_LANCZOS4)
    
    ascii_lines = []
    for row in resized:
        line = ""
        for pixel in row:
            if pixel < 5:
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
        
    # 2. Rebuilt Animation Engine: Synchronized Scanline Reveal
    char_w = 5.4
    char_h = 9.0
    svg_w = cols * char_w + 40
    svg_h = rows * char_h + 40
    
    total_duration = 5.0 # Professional reveal speed
    
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="100%" style="background-color: #0d1117; border-radius: 6px;">',
        '<style>',
        '.txt { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace; font-size: 7.5px; fill: #c9d1d9; }',
        '.scanline { fill: #58a6ff; filter: drop-shadow(0 0 4px #58a6ff); }',
        '</style>',
        f'<rect width="100%" height="100%" fill="#0d1117" rx="6"/>',
        # Define a clipPath that reveals the content top-down
        '<defs>',
        '<clipPath id="reveal-clip">',
        f'<rect x="0" y="0" width="{svg_w}" height="0">',
        f'<animate attributeName="height" from="0" to="{svg_h}" dur="{total_duration}s" begin="0s" fill="freeze" />',
        '</rect>',
        '</clipPath>',
        '</defs>',
        f'<g transform="translate(20, 25)" clip-path="url(#reveal-clip)">'
    ]
    
    # Add all text lines (they are hidden by the clipPath until revealed)
    for i, line in enumerate(ascii_lines):
        y = i * char_h + 7
        svg_parts.append(f'<text x="0" y="{y}" class="txt" xml:space="preserve">{line}</text>')
        
    svg_parts.append('</g>')
    
    # Add the blue scanline bar that physically "draws" the lines
    svg_parts.append(f'<g transform="translate(20, 25)">')
    svg_parts.append(f'<rect x="0" y="0" width="{cols * char_w}" height="2" class="scanline" opacity="0">')
    svg_parts.append(f'<set attributeName="opacity" to="1" begin="0s"/>')
    svg_parts.append(f'<animate attributeName="y" from="0" to="{rows * char_h}" dur="{total_duration}s" begin="0s" fill="freeze"/>')
    svg_parts.append(f'<animate attributeName="opacity" from="1" to="0" dur="0.3s" begin="{total_duration}s" fill="freeze"/>')
    svg_parts.append('</rect>')
    svg_parts.append('</g>')

    svg_parts.append('</svg>')
    
    with open(output_svg, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_parts))
    print(f"Synchronized Live-Reveal Portrait SVG generated at {output_svg}")

if __name__ == "__main__":
    generate_ascii_portrait()
