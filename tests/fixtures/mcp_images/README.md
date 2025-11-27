# Test Images for MCP Integration Tests

## 📍 Where to Place Images

Add **2-3 sample images** directly in this folder:

```
tests/fixtures/mcp_images/
  ├── sample1.jpg
  ├── sample2.jpg
  └── sample3.png
```

## 📋 Requirements

- **Format**: JPG, JPEG, or PNG
- **Quantity**: At least 2-3 images
- **Size**: Any reasonable image size (no specific requirements)
- **Content**: Any test images work (can be dummy images)

## 🎯 Purpose

These images are used by MCP integration tests to verify:
- Dataset creation with file uploads
- Dataset upload folder functionality  
- Complete end-to-end workflow tests

## 🔧 How It Works

The CI workflow sets `LABELLERR_TEST_DATA_PATH` to point to this folder.
Tests automatically find and use images from here when running dataset creation tests.

## ✅ Next Steps

1. Copy 2-3 sample images into this folder
2. Commit and push them with your changes
3. CI will automatically use them for integration tests

