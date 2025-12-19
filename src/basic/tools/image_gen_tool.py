"""Tool for generating images using Google Gemini's generate_content API."""

from __future__ import annotations

import asyncio
import io
import logging
import os
from typing import Any

import google.genai as genai

from .base import Tool
from ..utils import upload_file_to_llamacloud

logger = logging.getLogger(__name__)


class ImageGenTool(Tool):
    """Tool for generating images using Google Gemini's generate_content API."""

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
            "Generate images based on a text description using Google Gemini's generate_content API. "
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

    async def _generate_single_image(self, prompt: str, request_num: int, total: int):
        """Generate a single image asynchronously.

        Args:
            prompt: Text description of the image to generate
            request_num: Current request number (1-indexed for logging)
            total: Total number of images being generated

        Returns:
            PIL Image object if successful, None otherwise
        """
        try:
            # Run the synchronous generate_content call in a thread pool
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model="gemini-2.5-flash-image",
                contents=[prompt],
            )

            # Extract image from response parts
            for part in response.parts:
                if part.inline_data is not None:
                    image = part.as_image()
                    return image

            logger.warning(
                f"No image found in response for request {request_num}/{total}"
            )
            return None

        except Exception as e:
            logger.error(
                "Error generating image for request %d/%d: %s",
                request_num,
                total,
                str(e),
            )
            return None

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
                    - warning (str, optional): Warning message if fewer images were generated
                      than requested.

                On error:
                    - success (bool): False.
                    - error (str): Description of the error that occurred.
                    - prompt (str, optional): The prompt that was attempted, if available.
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

            # Generate images concurrently using asyncio.gather
            # Create tasks for all image generation requests
            tasks = [
                self._generate_single_image(prompt, i + 1, number_of_images)
                for i in range(number_of_images)
            ]

            # Run all tasks concurrently and collect results
            results = await asyncio.gather(*tasks)

            # Filter out None values (failed generations)
            generated_images = [img for img in results if img is not None]

            if not generated_images:
                return {
                    "success": False,
                    "error": "No images were generated. The prompt may have been filtered.",
                }

            # Check if we got the expected number of images
            actual_count = len(generated_images)
            if actual_count < number_of_images:
                logger.warning(
                    f"Requested {number_of_images} images but only received {actual_count}"
                )

            # Process single image case
            if number_of_images == 1:
                image_data = generated_images[0]
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
            for i, image_data in enumerate(generated_images, start=1):
                img_bytes = self._image_to_bytes(image_data)

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
