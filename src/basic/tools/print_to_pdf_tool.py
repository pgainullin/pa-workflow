"""Tool for converting text to PDF."""

from __future__ import annotations

import io
import logging
import re
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Table, TableStyle, Paragraph, SimpleDocTemplate, Spacer, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

from .base import Tool
from ..utils import upload_file_to_llamacloud, download_file_from_llamacloud

logger = logging.getLogger(__name__)

# Register CJK font
try:
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    DEFAULT_FONT = 'STSong-Light'
except Exception as e:
    logger.warning(f"Could not register CJK font: {e}")
    DEFAULT_FONT = 'Helvetica'


class PrintToPDFTool(Tool):
    """Tool for converting text to PDF."""

    # PDF layout constants
    PDF_MARGIN_INCHES = 1  # 1 inch margins
    PDF_MARGIN_POINTS = 72  # 72 points = 1 inch
    PDF_LINE_SPACING = 15  # Points between lines
    PDF_MAX_LINE_WIDTH = 468  # Max width in points (letter width - 2*margin)
    PDF_FONT_SIZE = 12  # Default font size
    PDF_FONT_NAME = DEFAULT_FONT  # Default font (STSong-Light if available)

    @property
    def name(self) -> str:
        return "print_to_pdf"

    @property
    def description(self) -> str:
        return (
            "Convert text content to a PDF file. "
            "Input: text, filename (optional). "
            "Output: file_id (LlamaCloud file ID of generated PDF)"
        )

    def _is_markdown_table_row(self, line: str) -> bool:
        """Check if a line looks like a markdown table row.
        
        Args:
            line: Line to check
            
        Returns:
            True if the line appears to be a markdown table row
        """
        stripped = line.strip()
        # Table rows start and end with |, and contain at least one | in the middle
        return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 3
    
    def _is_separator_row(self, cells: list[str]) -> bool:
        """Check if a table row is a separator row (contains only dashes, spaces, and colons).
        
        Args:
            cells: List of cell values
            
        Returns:
            True if this is a separator row
        """
        return all(
            all(c in "-: " for c in cell) and ("-" in cell or not cell)
            for cell in cells
        )
    
    def _parse_markdown_table(self, lines: list[str], start_idx: int) -> tuple[list[list[str]], int]:
        """Parse a markdown table from the given lines.
        
        Args:
            lines: List of all lines
            start_idx: Index of the first table row
            
        Returns:
            Tuple of (table_data as list of rows, index after the table)
        """
        table_data = []
        idx = start_idx
        
        while idx < len(lines) and self._is_markdown_table_row(lines[idx]):
            line = lines[idx].strip()
            # Remove leading and trailing |
            if line.startswith("|"):
                line = line[1:]
            if line.endswith("|"):
                line = line[:-1]
            
            # Split by | and clean up cells
            cells = [cell.strip() for cell in line.split("|")]
            
            # Skip separator rows
            if not self._is_separator_row(cells):
                table_data.append(cells)
            
            idx += 1
        
        return table_data, idx
    
    def _create_pdf_table(self, table_data: list[list[str]], page_width: float) -> Table:
        """Create a ReportLab Table from parsed markdown table data.
        
        Args:
            table_data: List of rows, each row is a list of cell values
            page_width: Available page width in points
            
        Returns:
            ReportLab Table object or None if table_data is empty or invalid
        """
        if not table_data:
            return None
        
        # Normalize table: ensure all rows have the same number of columns
        # Find the maximum number of columns across all rows (filter out empty rows)
        non_empty_rows = [row for row in table_data if row]
        if not non_empty_rows:
            return None
        
        num_cols = max(len(row) for row in non_empty_rows)
        
        # Pad shorter rows with empty cells to match num_cols
        normalized_table_data = []
        for row in table_data:
            if len(row) < num_cols:
                # Pad with empty strings
                padded_row = row + [""] * (num_cols - len(row))
                normalized_table_data.append(padded_row)
            else:
                normalized_table_data.append(row)
        
        # Calculate column widths based on content and available space
        # Use available width minus margins
        available_width = page_width - (2 * self.PDF_MARGIN_POINTS)
        col_width = available_width / num_cols
        
        # Create table with Paragraph objects for text wrapping
        styles = getSampleStyleSheet()
        cell_style = ParagraphStyle(
            'CellStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
            fontName=self.PDF_FONT_NAME,
        )
        
        # Convert cells to Paragraphs for automatic wrapping
        table_with_paragraphs = []
        for row in normalized_table_data:
            paragraph_row = []
            for cell in row:
                # Handle empty cells
                if not cell:
                    cell = " "
                
                # Truncate overly long cells to prevent ReportLab LayoutError (row > page height)
                # A single row cannot span multiple pages in ReportLab's standard Table
                if len(cell) > 3000:
                    logger.warning(f"Truncating long table cell ({len(cell)} chars) to prevent PDF layout error")
                    cell = cell[:3000] + "... (truncated)"
                
                # Create paragraph directly with UTF-8 text
                paragraph_row.append(Paragraph(cell, cell_style))
            table_with_paragraphs.append(paragraph_row)
        
        # Create table
        table = Table(table_with_paragraphs, colWidths=[col_width] * num_cols)
        
        # Style the table with better contrast for accessibility
        if len(table_with_paragraphs) >= 2:
            # Apply header styling only if there is at least a header and one data row
            table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey),  # Header row background
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),  # Header row text (white on dark grey for contrast)
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), self.PDF_FONT_NAME),  # Header row font
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),  # Grid lines
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ])
        else:
            # No header row, apply uniform styling
            table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.beige),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ])
        table.setStyle(table_style)
        
        return table
    
    def _wrap_text(self, text: str, canvas_obj, max_width: float) -> list[str]:
        """Wrap text to fit within the specified width.

        Args:
            text: Text to wrap
            canvas_obj: ReportLab canvas object for measuring text width
            max_width: Maximum width in points

        Returns:
            List of wrapped lines
        """
        words = text.split(" ")
        lines = []
        current_line = ""

        for word in words:
            # Test if adding this word would exceed the width
            test_line = current_line + (" " if current_line else "") + word
            text_width = canvas_obj.stringWidth(
                test_line, self.PDF_FONT_NAME, self.PDF_FONT_SIZE
            )

            if text_width <= max_width:
                current_line = test_line
            else:
                # Current line is full, save it and start a new line
                if current_line:
                    lines.append(current_line)
                    current_line = word
                else:
                    # Single word is too long, we need to break it
                    logger.warning(
                        f"Truncating extremely long word in PDF output: '{word}' to '{word[:100]}'"
                    )
                    lines.append(word[:100])  # Fallback: truncate extremely long words
                    current_line = ""

        # Add the last line
        if current_line:
            lines.append(current_line)

        return lines if lines else [""]

    async def execute(self, **kwargs) -> dict[str, Any]:
        """Convert text to PDF and upload to LlamaCloud.

        Args:
            **kwargs: Keyword arguments including:
                - text: Text to convert to PDF (required)
                - filename: Output filename (optional, default: "output.pdf")

        Returns:
            Dictionary with 'success' and 'file_id' or 'error'
        """
        text = kwargs.get("text")
        filename = kwargs.get("filename", "output.pdf")

        if not text:
            return {"success": False, "error": "Missing required parameter: text"}

        try:
            # Create PDF in memory
            pdf_buffer = io.BytesIO()
            
            # Use SimpleDocTemplate for better handling of tables and flowing content
            doc = SimpleDocTemplate(
                pdf_buffer,
                pagesize=letter,
                leftMargin=self.PDF_MARGIN_POINTS,
                rightMargin=self.PDF_MARGIN_POINTS,
                topMargin=self.PDF_MARGIN_POINTS,
                bottomMargin=self.PDF_MARGIN_POINTS,
            )
            
            # Build story (list of flowable elements)
            story = []
            styles = getSampleStyleSheet()
            normal_style = styles['Normal']
            normal_style.fontName = self.PDF_FONT_NAME
            heading_style = styles['Heading1']
            heading_style.fontName = self.PDF_FONT_NAME
            
            # Split text into lines
            input_lines = text.split("\n")
            width, height = letter
            
            i = 0
            while i < len(input_lines):
                line = input_lines[i]
                
                # Check if this is the start of a markdown table
                if self._is_markdown_table_row(line):
                    # Parse the entire table
                    table_data, next_idx = self._parse_markdown_table(input_lines, i)
                    
                    if table_data:
                        # Create and add the table to the story
                        pdf_table = self._create_pdf_table(table_data, width)
                        if pdf_table:
                            story.append(pdf_table)
                            story.append(Spacer(1, 12))  # Add some space after the table
                    
                    i = next_idx
                    continue
                
                # Check for markdown images: ![alt text](file_id)
                img_match = re.match(r"^!\[(.*?)\]\((.*?)\)$", line.strip())
                if img_match:
                    alt_text = img_match.group(1)
                    file_id = img_match.group(2)
                    
                    try:
                        # Download image from LlamaCloud
                        logger.info(f"Downloading image for PDF: {file_id}")
                        image_bytes = await download_file_from_llamacloud(file_id)
                        img_io = io.BytesIO(image_bytes)
                        
                        # Create Image flowable
                        img = Image(img_io)
                        
                        # Constrain image width to page width
                        avail_width = width - (2 * self.PDF_MARGIN_POINTS)
                        img_width = img.drawWidth
                        img_height = img.drawHeight
                        
                        if img_width > avail_width:
                            ratio = avail_width / img_width
                            img.drawWidth = avail_width
                            img.drawHeight = img_height * ratio
                            
                        story.append(img)
                        story.append(Spacer(1, 12))
                        
                    except Exception as e:
                        logger.error(f"Failed to embed image {file_id} in PDF: {e}")
                        # Fallback to text representation
                        story.append(Paragraph(f"[Image: {alt_text} - Failed to load]", normal_style))
                        story.append(Spacer(1, 6))
                    
                    i += 1
                    continue

                # Check for markdown headers
                if line.strip().startswith("#"):
                    # Count the # symbols to determine heading level
                    header_level = len(line) - len(line.lstrip("#"))
                    header_text = line.lstrip("#").strip()
                    
                    if header_text:
                        # Use appropriate heading style
                        if header_level == 1:
                            story.append(Paragraph(header_text, heading_style))
                        else:
                            # For other header levels, use bold text with appropriate size
                            # Map header levels to font sizes: H2=14, H3=12, H4=11, H5=10, H6+=10
                            header_font_sizes = {2: 14, 3: 12, 4: 11}
                            font_size = header_font_sizes.get(header_level, 10)
                            
                            # Use unique style name to avoid conflicts
                            bold_style = ParagraphStyle(
                                f'BoldHeading{header_level}',
                                parent=normal_style,
                                fontName=self.PDF_FONT_NAME,
                                fontSize=font_size,
                                spaceAfter=6,
                            )
                            story.append(Paragraph(header_text, bold_style))
                        story.append(Spacer(1, 6))
                else:
                    # Regular text line
                    if line.strip():
                        story.append(Paragraph(line, normal_style))
                    else:
                        # Empty line - add space
                        story.append(Spacer(1, 6))
                
                i += 1
            
            # Build the PDF
            doc.build(story)

            # Get PDF bytes
            pdf_bytes = pdf_buffer.getvalue()

            # Upload to LlamaCloud
            file_id = await upload_file_to_llamacloud(pdf_bytes, filename)

            return {"success": True, "file_id": file_id}
        except Exception as e:
            logger.exception("Error creating PDF")
            return {"success": False, "error": str(e)}
