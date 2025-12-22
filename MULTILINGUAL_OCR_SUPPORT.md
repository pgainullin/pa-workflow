# Multi-Language OCR Support Implementation

## Issue
The OCR functionality was struggling with character-based languages, initially reported for Chinese characters, resulting in poor accuracy or meaningless output when processing documents containing non-Latin scripts.

## Root Cause
The LlamaParse configuration didn't specify any language parameter. Without explicit language specification, LlamaParse may not use the appropriate OCR models for character recognition in various languages.

## Solution
Added explicit multi-language support to all LlamaParse initializations with the `language` parameter, specifying support for:
- **English** (`en`)
- **Chinese Simplified** (`ch_sim`)
- **Chinese Traditional** (`ch_tra`)
- **Japanese** (`ja`)
- **Korean** (`ko`)
- **Arabic** (`ar`)
- **Hindi** (`hi`)
- **Thai** (`th`)
- **Vietnamese** (`vi`)

## Implementation Details

### Code Changes

#### 1. Main Workflow (`src/basic/email_workflow.py`)
```python
llama_parser = LlamaParse(
    result_type="markdown",
    language="en,ch_sim,ch_tra,ja,ko,ar,hi,th,vi",  # Multi-language OCR support
)
```

#### 2. Legacy Workflow (`src/basic/email_workflow_old.py`)
```python
llama_parser = LlamaParse(
    result_type="markdown",
    language="en,ch_sim,ch_tra,ja,ko,ar,hi,th,vi",  # Multi-language OCR support
)
```

#### 3. Sheets Tool (`src/basic/tools/sheets_tool.py`)
```python
if self.llama_parser is None:
    self.llama_parser = LlamaParse(
        result_type="markdown",
        language="en,ch_sim,ch_tra,ja,ko,ar,hi,th,vi",  # Multi-language OCR support
    )
```

### Documentation Updates

#### README.md
- Updated **Document Processing** feature description to mention multi-language OCR support for all supported languages
- Updated **Parse** tool description to list major supported languages
- Updated **Sheets** tool description to mention multi-language OCR support

#### AGENTS.md
- Updated all three LlamaParse configuration examples:
  - Cost-Effective Mode
  - Agentic Mode (Default)
  - Agentic Plus Mode
- Added `language="en,ch_sim,ch_tra,ja,ko,ar,hi,th,vi"` parameter to all examples

## How LlamaParse Language Support Works

According to LlamaParse documentation:
- The `language` parameter affects **only text extracted from images** (OCR)
- For "layered text" (native PDF text), the original encoding is used
- LlamaParse supports 80+ languages for OCR
- Multiple languages can be specified as comma-separated values
- Language codes follow standard conventions:
  - `en` for English
  - `ch_sim` for Chinese Simplified
  - `ch_tra` for Chinese Traditional
  - `ja` for Japanese
  - `ko` for Korean
  - `ar` for Arabic
  - `hi` for Hindi
  - `th` for Thai
  - `vi` for Vietnamese
  - `fr` for French, `de` for German, `es` for Spanish, etc.

## Supported Languages

The current configuration supports major character-based and script-based languages:

| Language | Code | Script Type |
|----------|------|-------------|
| English | `en` | Latin |
| Chinese (Simplified) | `ch_sim` | Chinese characters |
| Chinese (Traditional) | `ch_tra` | Chinese characters |
| Japanese | `ja` | Kanji/Hiragana/Katakana |
| Korean | `ko` | Hangul |
| Arabic | `ar` | Arabic script |
| Hindi | `hi` | Devanagari |
| Thai | `th` | Thai script |
| Vietnamese | `vi` | Latin with diacritics |

## Benefits

1. **Improved Accuracy**: Documents with character-based languages are now processed with OCR models optimized for their specific scripts
2. **Multi-language Support**: The configuration supports documents that mix multiple languages and scripts
3. **No Breaking Changes**: The change is additive and doesn't affect existing functionality for documents without these specific languages
4. **Consistent Behavior**: All parsing operations (documents, PDFs, spreadsheets) now use the same language configuration
5. **Broad Coverage**: Supports major Asian, Middle Eastern, and South Asian languages

## Alternative Solutions Considered

During research, several alternative OCR APIs were evaluated:

### Google Cloud Vision OCR
- **Pros**: High accuracy for Chinese text, extensive documentation
- **Cons**: Additional cost, requires new API integration
- **Decision**: Not chosen because LlamaParse already supports Chinese with proper configuration

### PaddleOCR
- **Pros**: Open-source, optimized for Chinese text
- **Cons**: Requires separate deployment and integration
- **Decision**: Not chosen because LlamaParse can handle Chinese with proper configuration

### Tesseract OCR
- **Pros**: Open-source, widely supported
- **Cons**: Lower accuracy compared to commercial solutions
- **Decision**: Not chosen because LlamaParse provides better accuracy

## Testing and Verification

### Validation Performed
✅ **Syntax Check**: All modified Python files compile without errors
✅ **Code Review**: Automated review found no issues
✅ **Security Scan**: CodeQL found no vulnerabilities
✅ **Documentation**: Updated README and AGENTS documentation

### No Breaking Changes
- Language parameter is additive
- Existing documents in any language will process normally
- API compatibility is maintained
- No changes to tool interfaces or workflow structure

## Usage Notes

The language configuration is automatically applied to all document parsing operations:
- PDF parsing via ParseTool
- Spreadsheet parsing via SheetsTool
- Any document that goes through LlamaParse

Users don't need to specify languages when using the tools - it's handled automatically at the configuration level.

## Language Code Reference

The implementation uses standard ISO language codes and LlamaParse-specific codes:
- **ISO 639-1 codes**: `en`, `ja`, `ko`, `ar`, `hi`, `th`, `vi` (2-letter codes)
- **LlamaParse-specific**: `ch_sim`, `ch_tra` (for Chinese variants)

These codes are compatible with LlamaParse's OCR engine and provide optimal recognition for their respective scripts.

## References

- [LlamaParse Parsing Options](https://developers.llamaindex.ai/python/cloud/llamaparse/features/parsing_options/)
- [GitHub Issue: OCR struggles with Chinese content](https://github.com/run-llama/llama_cloud_services/issues/365)
- [LlamaParse Multi-language Support Discussion](https://github.com/run-llama/llama_cloud_services/issues/312)

## Future Enhancements

The current implementation includes the most commonly requested character-based languages. If additional language support is needed in the future, simply add more language codes to the `language` parameter:

```python
language="en,ch_sim,ch_tra,ja,ko,ar,hi,th,vi,fr,de,es,ru"  # Add more as needed
```

Common additional language codes:
- `fr` - French
- `de` - German
- `es` - Spanish
- `ru` - Russian
- `pt` - Portuguese
- `it` - Italian
- `nl` - Dutch
- `pl` - Polish
- `tr` - Turkish

Refer to the [LlamaParse documentation](https://developers.llamaindex.ai/python/cloud/llamaparse/features/parsing_options/) for the full list of supported language codes (80+ languages available).
