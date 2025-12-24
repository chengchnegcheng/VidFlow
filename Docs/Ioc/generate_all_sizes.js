const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

async function generateAllSizes() {
    const svgPath = path.join(__dirname, 'icon.svg');
    const svgBuffer = fs.readFileSync(svgPath);

    const sizes = [16, 24, 32, 48, 64, 96, 128, 256, 512, 1024];
    const pngDir = path.join(__dirname, 'icons', 'png');

    // Create directory
    if (!fs.existsSync(pngDir)) {
        fs.mkdirSync(pngDir, { recursive: true });
    }

    console.log('Generating all PNG sizes...');
    for (const size of sizes) {
        const outputPath = path.join(pngDir, `vidflow-${size}x${size}.png`);
        await sharp(svgBuffer)
            .resize(size, size)
            .png()
            .toFile(outputPath);
        console.log(`Generated ${size}x${size} PNG`);
    }

    console.log('\nAll icons generated successfully!');
}

generateAllSizes().catch(console.error);
