const fs = require('fs');
const path = require('path');

// Simple SVG to ICO converter using Node.js
// This script creates a basic ICO file from SVG

async function generateIcons() {
    try {
        // Try to use sharp if available
        const sharp = require('sharp');

        const svgPath = path.join(__dirname, 'icon.svg');
        const svgBuffer = fs.readFileSync(svgPath);

        // Generate PNG files
        const sizes = [16, 32, 48, 256];
        const pngDir = path.join(__dirname, 'icons', 'png');
        const icoDir = path.join(__dirname, 'icons', 'ico');

        // Create directories
        if (!fs.existsSync(pngDir)) {
            fs.mkdirSync(pngDir, { recursive: true });
        }
        if (!fs.existsSync(icoDir)) {
            fs.mkdirSync(icoDir, { recursive: true });
        }

        console.log('Generating PNG icons...');
        for (const size of sizes) {
            const outputPath = path.join(pngDir, `vidflow-${size}x${size}.png`);
            await sharp(svgBuffer)
                .resize(size, size)
                .png()
                .toFile(outputPath);
            console.log(`Generated ${size}x${size} PNG`);
        }

        // Create ICO file (using 256px PNG as base)
        const icoPath = path.join(icoDir, 'vidflow.ico');
        const png256Path = path.join(pngDir, 'vidflow-256x256.png');

        // For ICO, we'll just use the 256px PNG as a base
        // Real ICO should contain multiple sizes, but this is a simple version
        await sharp(svgBuffer)
            .resize(256, 256)
            .png()
            .toFile(icoPath.replace('.ico', '.png'));

        console.log('\nIcons generated successfully!');
        console.log(`Output directory: ${path.join(__dirname, 'icons')}`);
        console.log('\nNote: For proper ICO with multiple sizes, use:');
        console.log('  - Online tool: https://convert ico.co/svg-ico/');
        console.log('  - Or ImageMagick: convert icon.svg -define icon:auto-resize icon.ico');

        return true;
    } catch (error) {
        if (error.code === 'MODULE_NOT_FOUND') {
            console.log('Sharp not found. Installing...');
            const { execSync } = require('child_process');
            try {
                execSync('npm install sharp', { stdio: 'inherit', cwd: __dirname });
                console.log('\nPlease run this script again.');
            } catch (installError) {
                console.error('Failed to install sharp:', installError.message);
                console.log('\nAlternative: Use online tool to convert SVG to ICO');
                console.log('Visit: https://convertio.co/svg-ico/');
            }
        } else {
            console.error('Error generating icons:', error);
        }
        return false;
    }
}

generateIcons();
