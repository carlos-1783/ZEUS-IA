from PIL import Image, ImageDraw
import os

def create_zeus_favicon():
    # Create a new image with transparency
    size = 32
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw a simple Z shape with gradient
    for i in range(size):
        # Draw diagonal line
        draw.line([(i, i), (size-i-1, i)], fill=(255, 255, 255, 255))
        
        # Draw horizontal line
        draw.line([(0, i), (size-1, i)], fill=(255, 255, 255, int(255 * (1 - i/size))))
        
        # Draw vertical line
        draw.line([(i, 0), (i, size-1)], fill=(255, 255, 255, int(255 * (1 - i/size))))
    
    # Save favicon
    favicon_path = os.path.join('static', 'images', 'favicon.ico')
    img.save(favicon_path, format='ICO')
    print(f"Favicon saved to {favicon_path}")

if __name__ == "__main__":
    create_zeus_favicon()
