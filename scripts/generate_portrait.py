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

    # 1. Load image and remove background
    input_image = Image.open(input_path)
    session = new_session("u2netp")
    output_image = remove(input_image, session=session)
    
    # Convert to grayscale handling transparency properly
    img_np = np.array(output_image)
    if img_np.shape[2] == 4:
        alpha = img_np[:, :, 3] / 255.0
        img_gray = cv2.cvtColor(img_np[:, :, :3], cv2.COLOR_RGB2GRAY)
        # Make background pure black (0) or pure white (255) depending on design
        # Here background is 0 (black), subject has grayscale values
        img_gray = (img_gray * alpha).astype(np.uint8)
    else:
        img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    # 2. Bilateral filter for smoothing skin while keeping edges
    filtered = cv2.bilateralFilter(img_gray, 9, 75, 75)
    
    # 3. CLAHE for local contrast
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(filtered)
    
    # 4. Curve Adjustment for rich mid-tones
    normalized = enhanced.astype(np.float32) / 255.0
    curved = np.power(normalized, 1.2)
    final_gray = (curved * 255).astype(np.uint8)
    
    # Dense ASCII ramp (darkest to brightest)
    # We want dark background (0) to map to space '&#160;', and lit areas to dense characters
    ramp = " .'`^,:;Il!i~+_-?[]{}1()|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao#MW&8%B@$"
    ramp_len = len(ramp)
    
    cols = 120  # Higher column count for rich detail
    h, w = final_gray.shape
    aspect = h / w
    rows = int(cols * aspect * 0.48)
    
    resized = cv2.resize(final_gray, (cols, rows), interpolation=cv2.INTER_AREA)
    
    ascii_lines = []
    for row in resized:
        line = ""
        for pixel in row:
            # If pixel is near 0 (background), make it space
            if pixel < 10:
                char = "&#160;"
            else:
                idx = int((pixel / 255.0) * (ramp_len - 1))
                char = ramp[idx]
                if char == " ":
                    char = "&#160;"
                elif char == "<":
                    char = "&lt;"
                elif char == ">":
                    char = "&gt;"
                elif char == "&":
                    char = "&amp;"
            line += char
        ascii_lines.append(line)
        
    # Generate SVG with typing animation (SMIL) and safe font stack
    char_w = 7.2
    char_h = 14.0
    svg_w = cols * char_w + 40
    svg_h = rows * 12.0 + 40
    
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="100%" style="background-color: #0d1117; border-radius: 6px;">',
        '<style>',
        '.txt { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace; font-size: 10.5px; fill: #c9d1d9; }',
        '.cursor { fill: #58a6ff; }',
        '</style>',
        f'<rect width="100%" height="100%" fill="#0d1117" rx="6"/>',
        f'<g transform="translate(20, 25)">'
    ]
    
    for i, line in enumerate(ascii_lines):
        y = i * 12.0 + 10
        clip_id = f"c{i}"
        duration = 0.08
        begin_time = i * duration
        
        svg_parts.append(f'<clipPath id="{clip_id}">')
        svg_parts.append(f'<rect x="0" y="-10" width="0" height="16">')
        svg_parts.append(f'<animate attributeName="width" from="0" to="{cols * char_w}" dur="0.4s" begin="{begin_time:.2f}s" fill="freeze"/>')
        svg_parts.append(f'</rect>')
        svg_parts.append(f'</clipPath>')
        
        svg_parts.append(f'<text x="0" y="{y}" class="txt" xml:space="preserve">{line}</text>')
        svg_parts.append(f'<text x="0" y="{y}" class="txt" clip-path="url(#{clip_id})" fill="#58a6ff" xml:space="preserve">{line}</text>')
        
        # Cursor dot riding edge
        svg_parts.append(f'<rect x="0" y="{y-10}" width="5" height="12" class="cursor" opacity="0">')
        svg_parts.append(f'<set attributeName="opacity" to="1" begin="{begin_time:.2f}s"/>')
        svg_parts.append(f'<animate attributeName="x" from="0" to="{cols * char_w}" dur="0.4s" begin="{begin_time:.2f}s" fill="freeze"/>')
        svg_parts.append(f'<set attributeName="opacity" to="0" begin="{begin_time + 0.4}s"/>')
        svg_parts.append(f'</rect>')

    svg_parts.append('</g>')
    svg_parts.append('</svg>')
    
    os.makedirs(os.path.dirname(output_svg) if os.path.dirname(output_svg) else '.', exist_ok=True)
    with open(output_svg, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_parts))
    print(f"High-fidelity Portrait SVG successfully generated at {output_svg}")

if __name__ == "__main__":
    generate_ascii_portrait()
