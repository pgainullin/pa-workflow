"""Demo script to test the ImageGen tool."""

import asyncio
import os
from unittest.mock import MagicMock, patch

# Set environment variables
os.environ.setdefault("GEMINI_API_KEY", "demo-key")
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "demo-llama-key")
os.environ.setdefault("LLAMA_CLOUD_PROJECT_ID", "demo-project")


async def main():
    """Demo the ImageGen tool."""
    from basic.tools import ImageGenTool

    print("=" * 60)
    print("Image Generation Tool Demo")
    print("=" * 60)
    print()

    # Mock the genai client to avoid actually calling the API
    with patch("basic.tools.image_gen_tool.genai.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_image = MagicMock()
        mock_generated_image = MagicMock()
        mock_generated_image.image = mock_image
        mock_generated_image.rai_filtered_reason = None

        mock_response = MagicMock()
        mock_response.generated_images = [mock_generated_image]

        mock_client.models.generate_images = MagicMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        # Mock BytesIO and upload
        mock_buffer = MagicMock()
        mock_buffer.getvalue = MagicMock(return_value=b"fake_image_data")

        with patch("io.BytesIO", return_value=mock_buffer):
            with patch(
                "basic.tools.image_gen_tool.upload_file_to_llamacloud"
            ) as mock_upload:
                mock_upload.return_value = "file-demo-image-123"

                # Initialize the tool
                tool = ImageGenTool()
                print(f"Tool name: {tool.name}")
                print(f"Tool description: {tool.description}")
                print()

                # Test 1: Generate a single image
                print("Test 1: Generate a single image")
                print("-" * 60)
                prompt = "A beautiful sunset over snow-capped mountains"
                print(f"Prompt: {prompt}")
                result = await tool.execute(prompt=prompt)
                print(f"Success: {result['success']}")
                print(f"File ID: {result.get('file_id', 'N/A')}")
                print()

                # Test 2: Generate multiple images
                print("Test 2: Generate multiple images")
                print("-" * 60)
                # Mock multiple images
                mock_images = []
                for i in range(3):
                    mock_img = MagicMock()
                    mock_gen_img = MagicMock()
                    mock_gen_img.image = mock_img
                    mock_gen_img.rai_filtered_reason = None
                    mock_images.append(mock_gen_img)
                mock_response.generated_images = mock_images
                mock_upload.side_effect = ["file-1", "file-2", "file-3"]

                prompt = "A playful kitten with a ball of yarn"
                print(f"Prompt: {prompt}")
                print(f"Number of images: 3")
                result = await tool.execute(prompt=prompt, number_of_images=3)
                print(f"Success: {result['success']}")
                print(f"File IDs: {result.get('file_ids', 'N/A')}")
                print(f"Count: {result.get('count', 'N/A')}")
                print()

                # Test 3: Error handling - missing prompt
                print("Test 3: Error handling - missing prompt")
                print("-" * 60)
                result = await tool.execute()
                print(f"Success: {result['success']}")
                print(f"Error: {result.get('error', 'N/A')}")
                print()

                # Test 4: Error handling - invalid number_of_images
                print("Test 4: Error handling - invalid number_of_images")
                print("-" * 60)
                result = await tool.execute(prompt="test", number_of_images=10)
                print(f"Success: {result['success']}")
                print(f"Error: {result.get('error', 'N/A')}")
                print()

    print("=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
