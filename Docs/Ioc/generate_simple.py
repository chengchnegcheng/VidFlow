#!/usr/bin/env python3
"""
Simple icon generator without unicode
"""
import os
import sys
from pathlib import Path

def generate_icons_with_pillow():
    """Generate icons using PIL/Pillow"""
    try:
        from PIL import Image
        import cairosvg
    except ImportError:
        print("Installing required packages...")
        import subprocess
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'Pillow', 'cairosvg'])
            from PIL import Image
            import cairosvg
        except:
            print("ERROR: Failed to install dependencies")
            return False

    sizes = [16, 24, 32, 48, 64, 96, 128, 256, 512, 1024]
    svg_file = 'icon.svg'

    if not os.path.exists(svg_file):
        print(f"ERROR: {svg_file} not found")
        return False

    # Create output directory
    output_dir = Path('icons/png')
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating PNG icons...")
    success_count = 0

    for size in sizes:
        try:
            output_file = output_dir / f'vidflow-{size}x{size}.png'

            # Convert SVG to PNG using cairosvg
            png_data = cairosvg.svg2png(
                url=svg_file,
                output_width=size,
                output_height=size
            )

            # Save PNG file
            with open(output_file, 'wb') as f:
                f.write(png_data)

            print(f"Created {size}x{size} PNG")
            success_count += 1
        except Exception as e:
            print(f"Failed to create {size}x{size} PNG: {e}")

    if success_count == 0:
        return False

    # Create ICO file
    print("\nGenerating ICO file...")
    try:
        ico_sizes = [16, 24, 32, 48, 64, 128, 256]
        images = []

        for size in ico_sizes:
            png_file = output_dir / f'vidflow-{size}x{size}.png'
            if png_file.exists():
                img = Image.open(png_file)
                images.append(img)

        if images:
            ico_dir = Path('icons/ico')
            ico_dir.mkdir(parents=True, exist_ok=True)

            images[0].save(
                'icons/ico/vidflow.ico',
                format='ICO',
                sizes=[(img.width, img.height) for img in images]
            )
            print("Created vidflow.ico")
    except Exception as e:
        print(f"Failed to create ICO: {e}")

    print(f"\nSuccess! Generated {success_count} PNG files and 1 ICO file")
    print("Output directory: icons/")
    return True

if __name__ == '__main__':
    try:
        success = generate_icons_with_pillow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
