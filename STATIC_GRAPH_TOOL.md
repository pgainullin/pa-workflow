# Static Graph Tool Documentation

## Overview

The `StaticGraphTool` is a workflow tool that generates static charts and graphs from data and uploads them to LlamaCloud. The generated chart images are accessible via file IDs that can be used by other workflow steps or returned to users as email attachments.

## Features

- **Multiple Chart Types**: Supports line, bar, scatter, pie, and histogram charts
- **Customizable**: Optional parameters for titles, axis labels, and dimensions
- **LlamaCloud Integration**: Automatically uploads generated charts to LlamaCloud
- **High Quality**: Uses matplotlib with 150 DPI for crisp, clear charts

## Supported Chart Types

1. **Line Chart** - For showing trends over time or continuous data
2. **Bar Chart** - For comparing discrete categories
3. **Scatter Plot** - For showing relationships between two variables
4. **Pie Chart** - For showing proportions and percentages
5. **Histogram** - For showing distribution of numerical data

## Usage

### Basic Example

```python
from basic.tools import StaticGraphTool

tool = StaticGraphTool()

# Generate a line chart
result = await tool.execute(
    data={"x": [1, 2, 3, 4, 5], "y": [2, 4, 6, 8, 10]},
    chart_type="line",
    title="Sales Growth",
    xlabel="Month",
    ylabel="Revenue ($)",
)

if result["success"]:
    file_id = result["file_id"]
    # Use file_id in other workflow steps or as email attachment
```

### Data Format by Chart Type

#### Line, Bar, and Scatter Charts

```python
data = {
    "x": [1, 2, 3, 4, 5],      # X-axis values
    "y": [10, 20, 15, 25, 30]   # Y-axis values
}
```

Both `x` and `y` must be provided and have the same length.

#### Pie Chart

```python
data = {
    "values": [30, 25, 20, 15, 10],                    # Slice sizes
    "labels": ["A", "B", "C", "D", "E"]                # Slice labels
}
```

Both `values` and `labels` must be provided and have the same length.
#### Histogram

```python
data = {
    "values": [1, 2, 2, 3, 3, 3, 4, 4, 5]  # Data to plot distribution
}
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `data` | dict | Yes | - | Chart data (format depends on chart_type) |
| `chart_type` | str | Yes | - | Type of chart ('line', 'bar', 'scatter', 'pie', 'histogram') |
| `title` | str | No | "" | Chart title |
| `xlabel` | str | No | "" | X-axis label (not used for pie charts) |
| `ylabel` | str | No | "" | Y-axis label (not used for pie charts) |
| `width` | float | No | 10 | Chart width in inches |
| `height` | float | No | 6 | Chart height in inches |

### Return Value

On success:
```python
{
    "success": True,
    "file_id": "file-abc123",  # LlamaCloud file ID
    "chart_type": "line"        # Type of chart generated
}
```

On error:
```python
{
    "success": False,
    "error": "Error description"
}
```

## Examples

### Line Chart

```python
result = await tool.execute(
    data={
        "x": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "y": [45000, 52000, 48000, 61000, 58000, 67000]
    },
    chart_type="line",
    title="Monthly Sales",
    xlabel="Month",
    ylabel="Sales ($)",
)
```

### Bar Chart

```python
result = await tool.execute(
    data={
        "x": ["Product A", "Product B", "Product C", "Product D"],
        "y": [234, 198, 301, 245]
    },
    chart_type="bar",
    title="Product Comparison",
    xlabel="Product",
    ylabel="Units Sold",
)
```

### Scatter Plot

```python
result = await tool.execute(
    data={
        "x": [5, 7, 8, 7, 2, 17, 2, 9, 4, 11],
        "y": [99, 86, 87, 88, 100, 86, 103, 87, 94, 78]
    },
    chart_type="scatter",
    title="Test Scores vs Study Hours",
    xlabel="Study Hours",
    ylabel="Test Score",
)
```

### Pie Chart

```python
result = await tool.execute(
    data={
        "values": [32, 28, 18, 12, 10],
        "labels": ["Product A", "Product B", "Product C", "Product D", "Others"]
    },
    chart_type="pie",
    title="Market Share",
)
```

### Histogram

```python
result = await tool.execute(
    data={
        "values": [1, 2, 2, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 5]
    },
    chart_type="histogram",
    title="Grade Distribution",
    xlabel="Grade",
    ylabel="Number of Students",
)
```

## Integration with Email Workflow

The static_graph tool can be used by the triage agent to generate charts based on email requests:

### Example Triage Plan

When a user sends an email like "Please create a sales report with a chart showing Q1-Q4 performance", the triage agent might create this plan:

```json
[
  {
    "tool": "static_graph",
    "params": {
      "data": {
        "x": ["Q1", "Q2", "Q3", "Q4"],
        "y": [100000, 120000, 115000, 140000]
      },
      "chart_type": "bar",
      "title": "Quarterly Performance",
      "xlabel": "Quarter",
      "ylabel": "Revenue ($)"
    },
    "description": "Generate quarterly performance chart"
  }
]
```

The generated chart will be uploaded to LlamaCloud and the `file_id` can be included as an attachment in the response email.

## Error Handling

The tool validates input and provides clear error messages:

- **Missing data**: "Missing required parameter: data"
- **Missing chart_type**: "Missing required parameter: chart_type"
- **Invalid chart_type**: "Invalid chart_type: xyz. Must be one of ['line', 'bar', 'scatter', 'pie', 'histogram']"
- **Missing x data**: "line chart requires 'x' in data"
- **Missing y data**: "line chart requires 'y' in data"
- **Length mismatch**: "x and y data must have the same length"
- **Missing values**: "Pie chart requires 'values' in data"
- **Missing labels**: "Pie chart requires 'labels' in data"

## Dependencies

- **matplotlib** >= 3.7.0: Chart generation library
- **numpy**: Automatically installed with matplotlib

## Technical Details

- Charts are rendered at 150 DPI for high quality
- Non-interactive backend (Agg) is used for server environments
- PNG format is used for maximum compatibility
- Layout is automatically adjusted to prevent label cutoff
- Grid lines are added to line/bar/scatter charts for better readability

## Testing

The tool includes comprehensive tests covering:
- All chart types (line, bar, scatter, pie, histogram)
- Error handling (missing parameters, invalid types, data mismatches)
- Custom dimensions
- Integration with LlamaCloud upload

Run tests:
```bash
pytest tests/test_static_graph_tool.py -v
```

## Demo

A demo script is available to test the tool:

```bash
python demo_static_graph.py
```

This demonstrates all chart types and error handling scenarios.
