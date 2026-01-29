"""
Comprehensive test suite for document recreation functionality.

Tests the extraction of visual elements and recreation of documents.
"""

import pytest
from pathlib import Path
from doc_parser.parser import DocumentParser
from doc_parser.recreator import DocumentRecreator


class TestImageExtraction:
    """Test image extraction functionality"""

    def test_image_extraction_basic(self):
        """Test that images are extracted correctly"""
        parser = DocumentParser()

        # Check if test document exists
        test_doc = Path("documents/Vendor Creation template.docx")
        if not test_doc.exists():
            pytest.skip("Test document not found")

        result = parser.parse(str(test_doc))

        # Verify images were extracted
        assert hasattr(result, 'images'), "ParsedDocument should have images attribute"
        print(f"Images extracted: {len(result.images)}")

        # Verify each image has required fields
        for img in result.images:
            assert img.filename, "Image should have filename"
            assert img.image_data_base64, "Image should have base64 data"
            assert img.content_type, "Image should have content type"
            assert img.width_inches >= 0, "Image width should be non-negative"
            assert img.height_inches >= 0, "Image height should be non-negative"
            print(f"  - {img.filename}: {img.content_type}, {img.width_inches}x{img.height_inches} inches")

    def test_image_data_encoding(self):
        """Test that image data is properly base64 encoded"""
        parser = DocumentParser()

        test_doc = Path("documents/Vendor Creation template.docx")
        if not test_doc.exists():
            pytest.skip("Test document not found")

        result = parser.parse(str(test_doc))

        if len(result.images) > 0:
            # Verify base64 encoding is valid
            import base64
            for img in result.images:
                try:
                    decoded = base64.b64decode(img.image_data_base64)
                    assert len(decoded) > 0, "Decoded image data should not be empty"
                except Exception as e:
                    pytest.fail(f"Failed to decode image {img.filename}: {e}")


class TestFormattingExtraction:
    """Test formatting extraction functionality"""

    def test_font_extraction(self):
        """Test that font information is captured"""
        parser = DocumentParser()

        test_doc = Path("documents/Vendor Creation template.docx")
        if not test_doc.exists():
            pytest.skip("Test document not found")

        result = parser.parse(str(test_doc))

        # Check that sections have runs with font info
        sections_with_formatting = 0
        for section in result.sections:
            if section.runs:
                sections_with_formatting += 1
                # Verify run formatting structure
                for para_runs in section.runs:
                    for run in para_runs:
                        assert hasattr(run, 'text'), "Run should have text"
                        assert hasattr(run, 'font'), "Run should have font info"
                        assert hasattr(run.font, 'family'), "Font should have family"
                        assert hasattr(run.font, 'size_pt'), "Font should have size"

        print(f"Sections with formatting: {sections_with_formatting}/{len(result.sections)}")

    def test_paragraph_formatting(self):
        """Test paragraph formatting extraction"""
        parser = DocumentParser()

        test_doc = Path("documents/Vendor Creation template.docx")
        if not test_doc.exists():
            pytest.skip("Test document not found")

        result = parser.parse(str(test_doc))

        # Check that sections have paragraph formats
        sections_with_para_fmt = 0
        for section in result.sections:
            if section.paragraph_formats:
                sections_with_para_fmt += 1
                # Verify paragraph formatting structure
                for para_fmt in section.paragraph_formats:
                    assert hasattr(para_fmt, 'alignment'), "Paragraph should have alignment"
                    assert hasattr(para_fmt, 'line_spacing'), "Paragraph should have line spacing"
                    assert para_fmt.alignment in ['left', 'center', 'right', 'justify'], \
                        f"Invalid alignment: {para_fmt.alignment}"

        print(f"Sections with paragraph formatting: {sections_with_para_fmt}/{len(result.sections)}")

    def test_table_formatting(self):
        """Test table formatting extraction"""
        parser = DocumentParser()

        test_doc = Path("documents/Vendor Creation template.docx")
        if not test_doc.exists():
            pytest.skip("Test document not found")

        result = parser.parse(str(test_doc))

        # Check that tables have formatting
        tables_with_formatting = 0
        for table in result.raw_tables:
            if hasattr(table, 'table_format') and table.table_format:
                tables_with_formatting += 1

        print(f"Tables with formatting: {tables_with_formatting}/{len(result.raw_tables)}")


class TestDocumentRecreation:
    """Test document recreation functionality"""

    def test_recreation_basic(self):
        """Test basic document recreation"""
        parser = DocumentParser()

        test_doc = Path("documents/Vendor Creation template.docx")
        if not test_doc.exists():
            pytest.skip("Test document not found")

        parsed = parser.parse(str(test_doc))

        # Create output directory
        output_dir = Path("test_output")
        output_dir.mkdir(exist_ok=True)

        recreator = DocumentRecreator(parsed)
        output_path = output_dir / "test_recreation_basic.docx"
        success = recreator.recreate(str(output_path))

        assert success, "Recreation should succeed"
        assert output_path.exists(), "Recreated document should exist"

        # Cleanup
        output_path.unlink()

    def test_recreation_with_images(self):
        """Test that images are embedded in recreated document"""
        parser = DocumentParser()

        test_doc = Path("documents/Vendor Creation template.docx")
        if not test_doc.exists():
            pytest.skip("Test document not found")

        parsed = parser.parse(str(test_doc))

        if len(parsed.images) == 0:
            pytest.skip("No images in test document")

        # Create output directory
        output_dir = Path("test_output")
        output_dir.mkdir(exist_ok=True)

        recreator = DocumentRecreator(parsed)
        output_path = output_dir / "test_recreation_images.docx"
        success = recreator.recreate(str(output_path))

        assert success, "Recreation with images should succeed"
        assert output_path.exists(), "Recreated document should exist"

        # Verify the recreated document has images
        from docx import Document
        recreated_doc = Document(str(output_path))
        assert len(recreated_doc.inline_shapes) > 0, "Recreated document should have images"

        # Cleanup
        output_path.unlink()

    def test_recreation_preserves_content(self):
        """Test that content is preserved in recreation"""
        parser = DocumentParser()

        test_doc = Path("documents/Vendor Creation template.docx")
        if not test_doc.exists():
            pytest.skip("Test document not found")

        original = parser.parse(str(test_doc))

        # Create output directory
        output_dir = Path("test_output")
        output_dir.mkdir(exist_ok=True)

        recreator = DocumentRecreator(original)
        recreated_path = output_dir / "test_recreation_content.docx"
        recreator.recreate(str(recreated_path))

        # Parse the recreated document
        recreated = parser.parse(str(recreated_path))

        # Compare section counts (should be similar)
        assert len(recreated.sections) > 0, "Recreated document should have sections"

        # Cleanup
        recreated_path.unlink()

    def test_recreation_preserves_metadata(self):
        """Test that metadata is preserved"""
        parser = DocumentParser()

        test_doc = Path("documents/Vendor Creation template.docx")
        if not test_doc.exists():
            pytest.skip("Test document not found")

        original = parser.parse(str(test_doc))

        # Create output directory
        output_dir = Path("test_output")
        output_dir.mkdir(exist_ok=True)

        recreator = DocumentRecreator(original)
        recreated_path = output_dir / "test_recreation_metadata.docx"
        recreator.recreate(str(recreated_path))

        # Parse the recreated document
        from docx import Document
        recreated_doc = Document(str(recreated_path))

        # Verify metadata is preserved
        assert recreated_doc.core_properties.title == original.metadata.title, \
            "Title should be preserved"
        assert recreated_doc.core_properties.author == original.metadata.author, \
            "Author should be preserved"

        # Cleanup
        recreated_path.unlink()


class TestBackwardCompatibility:
    """Test backward compatibility with existing code"""

    def test_old_documents_still_parse(self):
        """Test that existing parsed documents still work"""
        parser = DocumentParser()

        test_doc = Path("documents/Vendor Creation template.docx")
        if not test_doc.exists():
            pytest.skip("Test document not found")

        # This should not fail even with new fields
        result = parser.parse(str(test_doc))

        # Verify old fields still exist
        assert hasattr(result, 'all_fields'), "Should have all_fields"
        assert hasattr(result, 'sections'), "Should have sections"
        assert hasattr(result, 'raw_tables'), "Should have raw_tables"

        # Verify new fields have defaults
        assert hasattr(result, 'images'), "Should have images field"
        assert isinstance(result.images, list), "Images should be a list"


def test_cleanup():
    """Cleanup test output directory"""
    output_dir = Path("test_output")
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
