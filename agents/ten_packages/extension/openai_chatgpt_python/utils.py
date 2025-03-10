from io import BytesIO
from PIL import Image
from typing import List, Tuple, Any

def resize_image_keep_aspect(image: Image.Image, max_size: int = 512) -> Image.Image:
    """Resize an image while maintaining its aspect ratio."""
    width, height = image.size

    if width <= max_size and height <= max_size:
        return image

    aspect_ratio = width / height

    if width > height:
        new_width = max_size
        new_height = int(max_size / aspect_ratio)
    else:
        new_height = max_size
        new_width = int(max_size * aspect_ratio)

    return image.resize((new_width, new_height))


def rgb2base64jpeg(rgb_data: bytes, width: int, height: int) -> bytes:
    """Convert RGB data to JPEG format."""
    # Convert the RGB image to a PIL Image
    pil_image = Image.frombytes("RGBA", (width, height), bytes(rgb_data))
    pil_image = pil_image.convert("RGB")

    # Resize the image while maintaining its aspect ratio
    pil_image = resize_image_keep_aspect(pil_image, 640)

    # Save the image to a BytesIO object in JPEG format
    buffered = BytesIO()
    pil_image.save(buffered, format="JPEG")
    
    return buffered.getvalue()

def filter_images(image_array: List[Any], max_images: int = 10) -> List[Any]:
    """Filter images to maintain a maximum count while preserving temporal distribution."""
    if len(image_array) <= max_images:
        return image_array
    
    result = []
    skip = len(image_array) // max_images
    
    for i in range(0, len(image_array), skip):
        result.append(image_array[i])
        if len(result) == max_images:
            break
    
    return result