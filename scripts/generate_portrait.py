import os
import cv2
import numpy as np
from PIL import Image
from rembg import remove

def generate_ascii_portrait():
    input_path = "assets/avatar.jpg"
    output_svg = "portrait.svg"
    
    if not os.path.exists(input_path):
        print(f"Avatar not found at {input_path}")
        return

    # Load image and remove background using lightweight u2netp
    from rembg import new_session
    input_image = Image.open(input_path)
    session = new_session("u2netp")
    output_image = remove(input_image, session=session)
    
    # Convert to grayscale numpy array
    img_gray = cv2.cvtColor(np.array(output_image.convert("L")), cv2.COLOR_GRAY2BGR)
    gray = cv2.cvtColor(img_gray, cv2.COLOR_BGR2GRAY)
    
    # Bilateral filter for smoothing skin while keeping edges
    filtered = cv2.bilateralFilter(gray, 9, 75, 75)
    
    # CLAHE for local contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(filtered)
    
    # Darkening curve: (v / 255) ^ 1.7
    normalized = enhanced.astype(np.float32) / 255.0
    curved = np.power(normalized, 1.7)
    final_gray = (curved * 255).astype(np.uint8)
    
    # ASCII ramp
    ramp = " .`:-=+*cs#%@"
    ramp_len = len(ramp)
    
    cols = 90
    h, w = final_gray.shape
    aspect = h / w
    rows = int(cols * aspect * 0.48)
    
    resized = cv2.resize(final_gray, (cols, rows), interpolation=cv2.INTER_AREA)
    
    ascii_lines = []
    for row in resized:
        line = ""
        for pixel in row:
            idx = int((pixel / 255.0) * (ramp_len - 1))
            char = ramp[idx]
            if char == " ":
                char = "&nbsp;"
            elif char == "<":
                char = "&lt;"
            elif char == ">":
                char = "&gt;"
            elif char == "&":
                char = "&amp;"
            line += char
        ascii_lines.append(line)
        
    # Generate SVG with typing animation (SMIL)
    char_w = 7.74
    char_h = 16.0
    svg_w = cols * char_w + 40
    svg_h = rows * 13.2 + 40
    
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="100%" style="background-color: #0d1117; border-radius: 6px;">',
        '<style>',
        "@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');",
        '.txt { font-family: "JetBrains Mono", monospace; font-size: 12.9px; fill: #c9d1d9; }',
        '.cursor { fill: #58a6ff; }',
        '</style>',
        f'<rect width="100%" height="100%" fill="#0d1117" rx="6"/>',
        f'<g transform="translate(20, 25)">'
    ]
    
    for i, line in enumerate(ascii_lines):
        y = i * 13.2 + 12
        clip_id = f"c{i}"
        duration = 0.09
        begin_time = i * duration
        
        svg_parts.append(f'<clipPath id="{clip_id}">')
        svg_parts.append(f'<rect x="0" y="-10" width="0" height="18">')
        svg_parts.append(f'<animate attributeName="width" from="0" to="{cols * char_w}" dur="0.5s" begin="{begin_time:.2f}s" fill="freeze"/>')
        svg_parts.append(f'</rect>')
        svg_parts.append(f'</clipPath>')
        
        svg_parts.append(f'<text x="0" y="{y}" class="txt">{line}</text>')
        svg_parts.append(f'<text x="0" y="{y}" class="txt" clip-path="url(#{clip_id})" fill="#58a6ff">{line}</text>')
        
        # Cursor dot riding edge
        svg_parts.append(f'<rect x="0" y="{y-11}" width="6" height="14" class="cursor" opacity="0">')
        svg_parts.append(f'<set attributeName="opacity" to="1" begin="{begin_time:.2f}s"/>')
        svg_parts.append(f'<animate attributeName="x" from="0" to="{cols * char_w}" dur="0.5s" begin="{begin_time:.2f}s" fill="freeze"/>')
        svg_parts.append(f'<set attributeName="opacity" to="0" begin="{begin_time + 0.5}s"/>')
        svg_parts.append(f'</rect>')

    svg_parts.append('</g>')
    svg_parts.append('</svg>')
    
    os.makedirs(os.path.dirname(output_svg) if os.path.dirname(output_svg) else '.', exist_ok=True)
    with open(output_svg, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_parts))
    print(f"Portrait SVG successfully generated at {output_svg}")

if __name__ == "__main__":
    generate_ascii_portrait()
