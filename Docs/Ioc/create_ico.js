const fs = require('fs');
const path = require('path');

// ICO file format builder
// Based on https://en.wikipedia.org/wiki/ICO_(file_format)

function createICO(pngBuffers) {
    const iconCount = pngBuffers.length;

    // ICONDIR structure (6 bytes)
    const iconDir = Buffer.alloc(6);
    iconDir.writeUInt16LE(0, 0);  // Reserved (must be 0)
    iconDir.writeUInt16LE(1, 2);  // Type (1 = ICO)
    iconDir.writeUInt16LE(iconCount, 4);  // Number of images

    // ICONDIRENTRY structures (16 bytes each)
    const iconDirEntries = [];
    let imageDataOffset = 6 + (iconCount * 16);

    for (let i = 0; i < iconCount; i++) {
        const pngBuffer = pngBuffers[i].buffer;
        const size = pngBuffers[i].size;

        const entry = Buffer.alloc(16);
        entry.writeUInt8(size === 256 ? 0 : size, 0);  // Width (0 = 256)
        entry.writeUInt8(size === 256 ? 0 : size, 1);  // Height (0 = 256)
        entry.writeUInt8(0, 2);  // Color palette (0 = no palette)
        entry.writeUInt8(0, 3);  // Reserved
        entry.writeUInt16LE(1, 4);  // Color planes
        entry.writeUInt16LE(32, 6);  // Bits per pixel
        entry.writeUInt32LE(pngBuffer.length, 8);  // Image data size
        entry.writeUInt32LE(imageDataOffset, 12);  // Offset to image data

        iconDirEntries.push(entry);
        imageDataOffset += pngBuffer.length;
    }

    // Combine all parts
    const icoBuffer = Buffer.concat([
        iconDir,
        ...iconDirEntries,
        ...pngBuffers.map(p => p.buffer)
    ]);

    return icoBuffer;
}

async function main() {
    const pngDir = path.join(__dirname, 'icons', 'png');
    const icoDir = path.join(__dirname, 'icons', 'ico');
    const icoPath = path.join(icoDir, 'vidflow.ico');

    // Sizes to include in ICO
    const sizes = [16, 32, 48, 256];
    const pngBuffers = [];

    console.log('Reading PNG files...');
    for (const size of sizes) {
        const pngPath = path.join(pngDir, `vidflow-${size}x${size}.png`);
        if (fs.existsSync(pngPath)) {
            const buffer = fs.readFileSync(pngPath);
            pngBuffers.push({ size, buffer });
            console.log(`Loaded ${size}x${size} PNG (${buffer.length} bytes)`);
        } else {
            console.error(`Warning: ${size}x${size} PNG not found`);
        }
    }

    if (pngBuffers.length === 0) {
        console.error('No PNG files found. Please run generate_icons.js first.');
        return;
    }

    console.log('\nCreating ICO file...');
    const icoBuffer = createICO(pngBuffers);

    // Create ico directory if needed
    if (!fs.existsSync(icoDir)) {
        fs.mkdirSync(icoDir, { recursive: true });
    }

    fs.writeFileSync(icoPath, icoBuffer);
    console.log(`\nICO file created: ${icoPath}`);
    console.log(`File size: ${(icoBuffer.length / 1024).toFixed(2)} KB`);
    console.log('\nIcon generation complete!');
}

main().catch(console.error);
