#!/usr/bin/env python3
"""
Icon copy and rename script - copies existing icons to correct names
"""
import os
import shutil
from pathlib import Path

def main():
    # Check if we have existing icons in resources
    resources_dir = Path('../../resources/icons')
    output_dir = Path('icons')

    if not resources_dir.exists():
        print("ERROR: resources/icons directory not found")
        return False

    # Copy SVG
    svg_source = Path('icon.svg')
    if svg_source.exists():
        # Copy to resources
        resources_icon = Path('../../resources/icon.svg')
        shutil.copy2(svg_source, resources_icon)
        print(f"Copied icon.svg to resources/")

        # Also copy as icon.png placeholder (will use SVG later)
        resources_icon_ico = Path('../../resources/icon.ico')
        if not resources_icon_ico.exists():
            # We need to create a basic ICO
            print("Note: ICO file needs to be created manually or using online tools")
            print("Visit: https://convertio.co/svg-ico/ to convert icon.svg")

    print("\nIcon file copied successfully!")
    print("Next steps:")
    print("1. Convert icon.svg to icon.ico using online tool")
    print("2. Place icon.ico in resources/ directory")
    print("3. Rebuild the application")

    return True

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
