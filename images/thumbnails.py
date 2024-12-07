from PIL import ImageFile, Image


def resize_with_aspect_ratio(image: ImageFile.ImageFile, target_width=300, target_height=300):
    # Calculate target height for 5:8 aspect ratio
    # target_height = int(target_width * (8 / 5))

    """
    Resize the given image while preserving its aspect ratio.

    Args:
        image: The PIL image to be resized.
        target_width: The desired width of the resized image.
        target_height: The desired height of the resized image.

    Returns:
        The resized image.
    """
    original_width, original_height = image.size
    original_ratio = original_width / original_height
    target_ratio = target_width / target_height

    if original_ratio > target_ratio:
        # Image is wider than target, crop width
        new_width = int(original_height * target_ratio)
        left = (original_width - new_width) // 2
        crop_box = (left, 0, left + new_width, original_height)
    else:
        # Image is taller than target, crop height
        new_height = int(original_width / target_ratio)
        top = (original_height - new_height) // 2
        crop_box = (0, top, original_width, top + new_height)

    cropped_image = image.crop(crop_box)

    return cropped_image.resize((target_width, target_height), Image.Resampling.NEAREST)
