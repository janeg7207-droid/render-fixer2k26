"""DDS inspection and explicit, non-destructive texture normalization."""
import io
import struct
from PIL import Image

MAX_PIXELS = 4096 * 4096
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def inspect_dds(data):
    if len(data) < 128 or data[:4] != b'DDS ':
        raise ValueError('Not a complete DDS header')
    h = struct.unpack('<31I', data[4:128])
    if h[0] != 124 or h[18] != 32:
        raise ValueError('Invalid DDS header sizes')
    width, height = h[3], h[2]
    if not width or not height or width * height > MAX_PIXELS:
        raise ValueError('Image exceeds the supported 16-megapixel limit or has invalid dimensions')
    fourcc = data[84:88]
    offset, dxgi = 128, None
    if fourcc == b'DX10':
        if len(data) < 148:
            raise ValueError('Truncated DX10 header')
        dxgi, dimension, misc, array, alpha_mode = struct.unpack('<5I', data[128:148])
        if dimension != 3 or array != 1 or misc & 4 or alpha_mode not in (0, 1):
            raise ValueError('Only single 2D textures with straight or unspecified alpha are supported')
        offset = 148
    if h[27] or h[5] > 1 or h[1] & 0x800000:
        raise ValueError('Cubemaps, volumes and texture arrays are not supported')
    mips = h[6] or 1
    if mips > max(width, height).bit_length():
        raise ValueError('Invalid mipmap count')
    block = 8 if fourcc in (b'DXT1', b'ATI1', b'BC4U') or dxgi in (70, 71, 72, 79, 80, 81) else 16
    compressed = fourcc in (b'DXT1', b'DXT3', b'DXT5', b'ATI1', b'ATI2', b'BC4U', b'BC5U') or dxgi in range(70, 85) or dxgi in (94, 95, 96, 97, 98, 99)
    expected = sum(((max(1, width >> n) + 3) // 4) * ((max(1, height >> n) + 3) // 4) * block if compressed else ((max(1, width >> n) * h[21] + 7) // 8) * max(1, height >> n) for n in range(mips))
    if compressed and len(data) - offset < expected:
        raise ValueError('Truncated DDS texture payload')
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        alpha = im.convert('RGBA').getchannel('A').getextrema()
    warnings = []
    if fourcc == b'DX10':
        warnings.append('DX10 header: confirm your importer supports this format')
    if width & (width - 1) or height & (height - 1):
        warnings.append('Non-power-of-two dimensions: compare against a working game texture')
    if width != height:
        warnings.append('Non-square texture: verify expected render dimensions')
    if mips == 1:
        warnings.append('Single mip level: compare against a working game texture')
    return dict(width=width, height=height, format=f'DX10 / DXGI {dxgi}' if dxgi else fourcc.decode('ascii', 'replace').strip('\0') or f'Uncompressed {h[21]}-bit', mips=mips, bytes=len(data), alpha=alpha[0] < 255, warnings=warnings)


def header(width, height, mips):
    values = [0] * 31
    values[:7] = [124, 0xa1007, height, width, ((width + 3) // 4) * ((height + 3) // 4) * 16, 0, mips]
    values[18:22] = [32, 4, int.from_bytes(b'DXT5', 'little'), 0]
    values[26] = 0x1008 | (0x400000 if mips > 1 else 0)
    return b'DDS ' + struct.pack('<31I', *values)


def normalize(data, size=0, mipmaps=False):
    info = inspect_dds(data) if data[:4] == b'DDS ' else None
    if size not in (0, 512, 1024, 2048):
        raise ValueError('Unsupported output size')
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > MAX_PIXELS:
            raise ValueError('Image exceeds the supported 16-megapixel limit')
        im = source.convert('RGBA')
    if size and im.size != (size, size):
        # Fit on a transparent square without stretching or cropping.
        im.thumbnail((size, size), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (size, size))
        canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2))
        im = canvas
    width, height = im.size
    levels = max(width, height).bit_length() if mipmaps else 1
    # Reuse compatible BC3 payload when no resize or mip generation is required.
    # DXGI 77 is BC3_UNORM; sRGB and premultiplied formats must not be relabeled.
    dxgi = struct.unpack_from('<I', data, 128)[0] if info and data[84:88] == b'DX10' else None
    if info and (info['width'], info['height']) == im.size and info['mips'] == levels and (data[84:88] == b'DXT5' or dxgi == 77):
        offset = 148 if dxgi else 128
        count = sum(((max(1, width >> n) + 3) // 4) * ((max(1, height >> n) + 3) // 4) * 16 for n in range(levels))
        payload = data[offset:offset + count]
        operation = 'Rebuilt legacy DXT5 header; compressed image data preserved'
    else:
        if dxgi in (72, 75, 78, 99):
            raise ValueError('sRGB DDS conversion requires a confirmed color-space profile; use a known-good reference')
        chunks = []
        for n in range(levels):
            level = im if n == 0 else im.resize((max(1, width >> n), max(1, height >> n)), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            level.save(buf, format='DDS', pixel_format='DXT5')
            chunks.append(buf.getvalue()[128:])
        payload = b''.join(chunks)
        operation = 'Encoded legacy DXT5 (lossy BC3 compression)'
    result = header(width, height, levels) + payload
    inspect_dds(result)
    return result, dict(operation=operation, width=width, height=height, mips=levels)
