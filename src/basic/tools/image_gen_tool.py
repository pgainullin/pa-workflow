"""Tool for generating images using Google Gemini's Imagen API."""

from __future__ import annotations

import io
import logging
import os
from typing import Any

import google.genai as genai

from .base import Tool
from ..utils import upload_file_to_llamacloud

logger = logging.getLogger(__name__)


class ImageGenTool(Tool):
    """Tool for generating images using Google Gemini's Imagen API."""

    def __init__(self):
        """Initialize the ImageGenTool.

        Requires GEMINI_API_KEY environment variable to be set.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        self.client = genai.Client(api_key=api_key)

    @property
    def name(self) -> str:
        return "image_gen"

    @property
    def description(self) -> str:
        return (
            "Generate images based on a text description using Google Gemini's Imagen API. "
            "Input: prompt (text description of the image to generate), "
            "number_of_images (optional, default: 1, max: 4). "
            "Output: file_id (single image) or file_ids array with count (multiple images)"
        )

    def _image_to_bytes(self, image) -> bytes:
        """Convert PIL Image to bytes.

        Args:
            image: PIL Image object

        Returns:
            Image data as bytes in PNG format
        """
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format="PNG")
        return img_byte_arr.getvalue()

    async def execute(self, **kwargs) -> dict[str, Any]:
        """Generate an image based on a text prompt.

        Args:
            **kwargs: Keyword arguments including:
                - prompt: Text description of the image to generate (required)
                - number_of_images: Number of images to generate (optional, default: 1, max: 4)

        Returns:
            dict[str, Any]: A dictionary describing the result of the image generation.

                On success:
                    - success (bool): True.
                    - file_id (str): LlamaCloud file ID of the generated image when a single
                      image is generated.
                    - file_ids (list[str]): LlamaCloud file IDs of the generated images when
                      multiple images are generated.
                    - count (int): Number of images that were generated and uploaded.
                    - prompt (str): The prompt used for generation.
                    - rai_reason (str | None): Reason provided by the RAI/safety system if
                      the prompt or output was modified, filtered, or blocked (if applicable).

                On error:
                    - success (bool): False.
                    - error (str): Description of the error that occurred.
                    - prompt (str, optional): The prompt that was attempted, if available.
                    - rai_reason (str | None, optional): Reason provided by the RAI/safety
                      system if the request was blocked or modified (if applicable).
        """
        prompt = kwargs.get("prompt")
        number_of_images = kwargs.get("number_of_images", 1)

        if not prompt:
            return {"success": False, "error": "Missing required parameter: prompt"}

        # Validate number_of_images
        if (
            not isinstance(number_of_images, int)
            or number_of_images < 1
            or number_of_images > 4
        ):
            return {
                "success": False,
                "error": "number_of_images must be an integer between 1 and 4",
            }

        try:
            logger.info(f"Generating {number_of_images} image(s) with prompt: {prompt}")

            # Generate images using Gemini's Imagen API
            response = self.client.models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=prompt,
                config=genai.types.GenerateImagesConfig(
                    number_of_images=number_of_images,
                    include_rai_reason=True,
                ),
            )

            if not response.generated_images:
                return {
                    "success": False,
                    "error": "No images were generated. The prompt may have been filtered.",
                }

            # Check if we got the expected number of images
            actual_count = len(response.generated_images)
            if actual_count < number_of_images:
                logger.warning(
                    f"Requested {number_of_images} images but only received {actual_count}"
                )

            # Process single image case
            if number_of_images == 1:
                image_data = response.generated_images[0].image
                img_bytes = self._image_to_bytes(image_data)

                # Upload to LlamaCloud
                file_id = await upload_file_to_llamacloud(
                    img_bytes, filename="generated_image.png"
                )

                result = {
                    "success": True,
                    "file_id": file_id,
                    "prompt": prompt,
                }

                # Add RAI (Responsible AI) information if available
                if (
                    hasattr(response.generated_images[0], "rai_filtered_reason")
                    and response.generated_images[0].rai_filtered_reason
                ):
                    result["rai_reason"] = response.generated_images[
                        0
                    ].rai_filtered_reason

                # Add warning if fewer images were received than requested
                if actual_count < number_of_images:
                    result["warning"] = (
                        f"Requested {number_of_images} images but only {actual_count} generated"
                    )

                logger.info(
                    f"Successfully generated and uploaded image with file_id: {file_id}"
                )
                return result

            # Process multiple images case
            file_ids = []
            for i, generated_image in enumerate(response.generated_images, start=1):
                img_bytes = self._image_to_bytes(generated_image.image)

                file_id = await upload_file_to_llamacloud(
                    img_bytes, filename=f"generated_image_{i}.png"
                )
                file_ids.append(file_id)

            result = {
                "success": True,
                "file_ids": file_ids,
                "count": len(file_ids),
                "prompt": prompt,
            }

            # Add RAI information from the first image if available
            if (
                hasattr(response.generated_images[0], "rai_filtered_reason")
                and response.generated_images[0].rai_filtered_reason
            ):
                result["rai_reason"] = response.generated_images[0].rai_filtered_reason

            # Add warning if fewer images were received than requested
            if actual_count < number_of_images:
                result["warning"] = (
                    f"Requested {number_of_images} images but only {actual_count} generated"
                )

            logger.info(f"Successfully generated and uploaded {len(file_ids)} image(s)")
            return result

        except Exception as e:
            logger.exception("Error generating image")
            return {"success": False, "error": str(e)}
