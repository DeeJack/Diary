import tempfile
import json
from pathlib import Path
from diary.models.dao.notebook_dao import NotebookDAO
from diary.models.notebook import Notebook
from diary.models.page import Page
from diary.models.stroke import Stroke
from diary.models.point import Point


def test_save_and_load_with_nested_objects():
    # Create test points
    point1 = Point(x=10.5, y=20.3, pressure=0.8)
    point2 = Point(x=15.2, y=25.7, pressure=0.9)
    point3 = Point(x=30.1, y=40.6, pressure=0.7)
    point4 = Point(x=35.8, y=45.2, pressure=0.6)

    # Create test strokes with points
    stroke1 = Stroke(points=[point1, point2], color="blue", size=2.5, tool="pen")
    stroke2 = Stroke(points=[point3, point4], color="red", size=1.8, tool="marker")

    # Create test pages with strokes
    page1 = Page(
        strokes=[stroke1], metadata={"title": "Test Page 1", "background": "white"}
    )
    page2 = Page(
        strokes=[stroke2], metadata={"title": "Test Page 2", "background": "yellow"}
    )

    # Create test notebook
    original_notebook = Notebook(
        pages=[page1, page2], metadata={"title": "Test Notebook", "version": "1.0"}
    )

    # Save to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = Path(f.name)

    try:
        # Test save
        NotebookDAO.save(original_notebook, temp_path)

        # Verify file was created and contains nested JSON structure
        assert temp_path.exists()
        with open(temp_path, "r") as f:
            json_data = json.load(f)
            assert "pages" in json_data
            assert "metadata" in json_data
            assert len(json_data["pages"]) == 2
            assert "strokes" in json_data["pages"][0]
            assert "points" in json_data["pages"][0]["strokes"][0]

        # Test load
        loaded_notebook = NotebookDAO.load(temp_path)

        # Verify it returns a Notebook object (not a dict)
        assert isinstance(loaded_notebook, Notebook), (
            f"Expected Notebook, got {type(loaded_notebook)}"
        )

        # Test that we can access attributes with dot notation
        assert hasattr(loaded_notebook, "pages"), "Notebook should have pages attribute"
        assert hasattr(loaded_notebook, "metadata"), (
            "Notebook should have metadata attribute"
        )

        # Verify notebook content
        assert len(loaded_notebook.pages) == 2
        assert loaded_notebook.metadata["title"] == "Test Notebook"
        assert loaded_notebook.metadata["version"] == "1.0"

        # Verify pages are Page objects (not dicts)
        page_1 = loaded_notebook.pages[0]
        page_2 = loaded_notebook.pages[1]

        assert isinstance(page_1, Page), f"Expected Page, got {type(page_1)}"
        assert isinstance(page_2, Page), f"Expected Page, got {type(page_2)}"

        # Test page attribute access
        assert page_1.metadata["title"] == "Test Page 1"
        assert page_1.metadata["background"] == "white"
        assert page_2.metadata["title"] == "Test Page 2"
        assert page_2.metadata["background"] == "yellow"

        # Verify strokes are Stroke objects (not dicts)
        assert len(page_1.strokes) == 1
        assert len(page_2.strokes) == 1

        stroke_1 = page_1.strokes[0]
        stroke_2 = page_2.strokes[0]

        assert isinstance(stroke_1, Stroke), f"Expected Stroke, got {type(stroke_1)}"
        assert isinstance(stroke_2, Stroke), f"Expected Stroke, got {type(stroke_2)}"

        # Test stroke attribute access
        assert stroke_1.color == "blue"
        assert stroke_1.thickness == 2.5  # Note: stored as thickness, not size
        assert stroke_1.tool == "pen"

        assert stroke_2.color == "red"
        assert stroke_2.thickness == 1.8
        assert stroke_2.tool == "marker"

        # Verify points are Point objects (not dicts)
        assert len(stroke_1.points) == 2
        assert len(stroke_2.points) == 2

        loaded_point1 = stroke_1.points[0]
        loaded_point2 = stroke_1.points[1]
        loaded_point3 = stroke_2.points[0]
        loaded_point4 = stroke_2.points[1]

        assert isinstance(loaded_point1, Point), (
            f"Expected Point, got {type(loaded_point1)}"
        )
        assert isinstance(loaded_point2, Point), (
            f"Expected Point, got {type(loaded_point2)}"
        )
        assert isinstance(loaded_point3, Point), (
            f"Expected Point, got {type(loaded_point3)}"
        )
        assert isinstance(loaded_point4, Point), (
            f"Expected Point, got {type(loaded_point4)}"
        )

        # Test point attribute access and values
        assert loaded_point1.x == 10.5
        assert loaded_point1.y == 20.3
        assert loaded_point1.pressure == 0.8

        assert loaded_point2.x == 15.2
        assert loaded_point2.y == 25.7
        assert loaded_point2.pressure == 0.9

        assert loaded_point3.x == 30.1
        assert loaded_point3.y == 40.6
        assert loaded_point3.pressure == 0.7

        assert loaded_point4.x == 35.8
        assert loaded_point4.y == 45.2
        assert loaded_point4.pressure == 0.6

        print(
            "✓ Nested objects test passed - All objects properly deserialized with dot notation access"
        )

    finally:
        # Clean up
        if temp_path.exists():
            temp_path.unlink()


def test_load_nonexistent_file():
    # Test loading a file that doesn't exist
    non_existent_path = Path("does_not_exist.json")

    loaded_notebook = NotebookDAO.load(non_existent_path)

    # Should return a default Notebook with one empty page
    assert isinstance(loaded_notebook, Notebook)
    assert len(loaded_notebook.pages) == 1
    assert len(loaded_notebook.pages[0].strokes) == 0

    print("✓ Non-existent file test passed - Returns default Notebook")


def test_empty_structures():
    # Test with empty structures to ensure robustness
    empty_notebook = Notebook(pages=[], metadata={})

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = Path(f.name)

    try:
        # Save empty notebook
        NotebookDAO.save(empty_notebook, temp_path)

        # Load it back
        loaded_notebook = NotebookDAO.load(temp_path)

        assert isinstance(loaded_notebook, Notebook)
        assert len(loaded_notebook.pages) == 0
        assert len(loaded_notebook.metadata) == 0

        print("✓ Empty structures test passed")

    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_malformed_data_robustness():
    # Test with malformed JSON data to ensure graceful handling
    malformed_data = {
        "pages": [
            {
                "strokes": [
                    {
                        "points": [
                            {"x": "invalid", "y": 10},  # Invalid x value
                            {
                                "x": 20,
                                "y": 30,
                                "pressure": "also_invalid",
                            },  # Invalid pressure
                        ],
                        "color": "blue",
                        # Missing other fields
                    }
                ],
                "metadata": "should_be_dict",  # Wrong type
            }
        ],
        "metadata": ["should", "be", "dict"],  # Wrong type
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = Path(f.name)

    try:
        # Write malformed data directly
        with open(temp_path, "w") as f:
            json.dump(malformed_data, f)

        # Try to load it - should still return a Notebook object
        loaded_notebook = NotebookDAO.load(temp_path)
        assert isinstance(loaded_notebook, Notebook)

        print("✓ Malformed data robustness test passed")

    finally:
        if temp_path.exists():
            temp_path.unlink()


if __name__ == "__main__":
    test_save_and_load_with_nested_objects()
    test_load_nonexistent_file()
    test_empty_structures()
    test_malformed_data_robustness()
    print("All tests passed! 🎉")
    print("The save/load functionality now properly handles:")
    print("  ✓ Notebook objects with dot notation access")
    print("  ✓ Page objects with dot notation access")
    print("  ✓ Stroke objects with dot notation access")
    print("  ✓ Point objects with dot notation access")
    print("  ✓ All nested structures are properly deserialized")
