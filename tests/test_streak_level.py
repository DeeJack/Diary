import time
from datetime import datetime

from diary.models.notebook import Notebook
from diary.models.page import Page


def test_initial_streak_level():
    """Test that the first page in a notebook has streak level 0"""
    notebook = Notebook()

    # Add first page
    notebook.add_page()

    assert len(notebook.pages) == 1
    assert notebook.pages[0].streak_lvl == 0
    print("✓ Initial streak level test passed - First page has streak_lvl 0")


def test_same_day_streak_level():
    """Test that pages created on the same day maintain the same streak level"""
    notebook = Notebook()

    # Add first page
    notebook.add_page()

    # Add second page on the same day (a few seconds later)
    time.sleep(0.1)  # Small delay to ensure different timestamps
    notebook.add_page()

    assert notebook.pages[0].streak_lvl == 0
    assert notebook.pages[1].streak_lvl == 0
    print("✓ Same day streak level test passed - Same day pages maintain streak_lvl")


def test_consecutive_day_streak():
    """Test that consecutive days increase streak level"""
    notebook = Notebook()

    # Create pages for consecutive days
    base_time = time.time() - (2 * 24 * 60 * 60)  # Start 2 days ago

    # Day 1
    page1 = Page(created_at=base_time)
    notebook.add_page(page1)

    # Day 2 (next day)
    page2 = Page(created_at=base_time + (24 * 60 * 60))
    notebook.add_page(page2)

    # Day 3 (next day)
    page3 = Page(created_at=base_time + (2 * 24 * 60 * 60))
    notebook.add_page(page3)

    assert notebook.pages[0].streak_lvl == 0
    assert notebook.pages[1].streak_lvl == 1
    assert notebook.pages[2].streak_lvl == 2
    print(
        "✓ Consecutive day streak test passed - Streak increases by 1 each consecutive day"
    )


def test_broken_streak():
    """Test that skipping days resets streak to 0"""
    notebook = Notebook()

    base_time = time.time() - (5 * 24 * 60 * 60)  # Start 5 days ago

    # Day 1
    page1 = Page(created_at=base_time)
    notebook.add_page(page1)

    # Day 2 (next day)
    page2 = Page(created_at=base_time + (24 * 60 * 60))
    notebook.add_page(page2)

    # Skip a day, Day 4
    page3 = Page(created_at=base_time + (3 * 24 * 60 * 60))
    notebook.add_page(page3)

    assert notebook.pages[0].streak_lvl == 0
    assert notebook.pages[1].streak_lvl == 1
    assert notebook.pages[2].streak_lvl == 0  # Reset because of gap
    print("✓ Broken streak test passed - Gap in days resets streak_lvl to 0")


def test_different_month_resets_streak():
    """Test that pages in different months reset streak level"""
    notebook = Notebook()

    # Create a page in December 2023
    dec_time = datetime(2023, 12, 31, 12, 0, 0).timestamp()
    page1 = Page(created_at=dec_time)
    notebook.add_page(page1)

    # Create a page in January 2024 (next day but different month/year)
    jan_time = datetime(2024, 1, 1, 12, 0, 0).timestamp()
    page2 = Page(created_at=jan_time)
    notebook.add_page(page2)

    assert notebook.pages[0].streak_lvl == 0
    assert notebook.pages[1].streak_lvl == 0  # Reset because different month/year
    print(
        "✓ Different month reset test passed - Different month/year resets streak_lvl"
    )


def test_different_year_same_month_resets_streak():
    """Test that pages in different years but same month reset streak level"""
    notebook = Notebook()

    # Create a page in March 2023
    mar_2023_time = datetime(2023, 3, 15, 12, 0, 0).timestamp()
    page1 = Page(created_at=mar_2023_time)
    notebook.add_page(page1)

    # Create a page in March 2024 (same month, different year)
    mar_2024_time = datetime(2024, 3, 16, 12, 0, 0).timestamp()
    page2 = Page(created_at=mar_2024_time)
    notebook.add_page(page2)

    assert notebook.pages[0].streak_lvl == 0
    assert notebook.pages[1].streak_lvl == 0  # Reset because different year
    print("✓ Different year reset test passed - Different year resets streak_lvl")


def test_long_streak():
    """Test a longer streak to ensure it works for extended periods"""
    notebook = Notebook()

    base_time = time.time() - (10 * 24 * 60 * 60)  # Start 10 days ago

    # Create pages for 7 consecutive days
    for i in range(7):
        page = Page(created_at=base_time + (i * 24 * 60 * 60))
        notebook.add_page(page)

    # Verify streak levels
    for i, page in enumerate(notebook.pages):
        assert page.streak_lvl == i

    assert notebook.pages[-1].streak_lvl == 6  # 7th day should have streak_lvl 6
    print("✓ Long streak test passed - 7-day streak correctly calculated")


def test_multiple_pages_same_day_in_streak():
    """Test that multiple pages on the same day during a streak maintain correct levels"""
    notebook = Notebook()

    base_time = time.time() - (3 * 24 * 60 * 60)  # Start 3 days ago

    # Day 1 - one page
    page1 = Page(created_at=base_time)
    notebook.add_page(page1)

    # Day 2 - two pages
    day2_base = base_time + (24 * 60 * 60)
    page2a = Page(created_at=day2_base)
    notebook.add_page(page2a)

    page2b = Page(created_at=day2_base + 3600)  # 1 hour later same day
    notebook.add_page(page2b)

    # Day 3 - one page
    page3 = Page(created_at=base_time + (2 * 24 * 60 * 60))
    notebook.add_page(page3)

    assert notebook.pages[0].streak_lvl == 0  # Day 1
    assert notebook.pages[1].streak_lvl == 1  # Day 2 first page
    assert notebook.pages[2].streak_lvl == 1  # Day 2 second page (same level)
    assert notebook.pages[3].streak_lvl == 2  # Day 3
    print(
        "✓ Multiple pages same day test passed - Same day pages maintain streak level"
    )


def test_edge_case_midnight_boundary():
    """Test streak calculation around midnight boundary"""
    notebook = Notebook()

    # Create page at 11:59 PM
    late_night = datetime(2024, 1, 15, 23, 59, 0).timestamp()
    page1 = Page(created_at=late_night)
    notebook.add_page(page1)

    # Create page at 12:01 AM next day
    early_morning = datetime(2024, 1, 16, 0, 1, 0).timestamp()
    page2 = Page(created_at=early_morning)
    notebook.add_page(page2)

    assert notebook.pages[0].streak_lvl == 0
    assert notebook.pages[1].streak_lvl == 1
    print(
        "✓ Midnight boundary test passed - Consecutive days across midnight work correctly"
    )


def test_streak_level_with_custom_pages():
    """Test streak calculation with pages that have custom streak levels initially"""
    notebook = Notebook()

    # Create a page with custom initial streak level
    page1 = Page(streak_lvl=5)  # First page keeps its initial streak level
    notebook.add_page(page1)

    # The first page keeps its custom streak level since there are no previous pages
    assert notebook.pages[0].streak_lvl == 5

    # Add second page next day
    time.sleep(0.1)
    next_day_time = time.time() + (24 * 60 * 60)
    page2 = Page(
        created_at=next_day_time, streak_lvl=10
    )  # This should be overwritten based on previous page
    notebook.add_page(page2)

    # Second page gets calculated streak level based on first page (5 + 1 = 6)
    assert notebook.pages[1].streak_lvl == 6
    print(
        "✓ Custom streak level test passed - First page keeps custom level, subsequent pages calculated"
    )


def test_get_creation_date_method():
    """Test that the get_creation_date method works correctly"""
    test_time = datetime(2024, 6, 15, 14, 30, 45).timestamp()
    page = Page(created_at=test_time)

    creation_date = page.get_creation_date()

    assert isinstance(creation_date, datetime)
    assert creation_date.year == 2024
    assert creation_date.month == 6
    assert creation_date.day == 15
    assert creation_date.hour == 14
    assert creation_date.minute == 30
    assert creation_date.second == 45
    print("✓ get_creation_date test passed - Correctly converts timestamp to datetime")


def run_all_streak_tests():
    """Run all streak level tests"""
    print("Running streak level tests...\n")

    test_initial_streak_level()
    test_same_day_streak_level()
    test_consecutive_day_streak()
    test_broken_streak()
    test_different_month_resets_streak()
    test_different_year_same_month_resets_streak()
    test_long_streak()
    test_multiple_pages_same_day_in_streak()
    test_edge_case_midnight_boundary()
    test_streak_level_with_custom_pages()
    test_get_creation_date_method()

    print("\n🎉 All streak level tests passed!")
    print("\nStreak level functionality verified:")
    print("  ✓ First page starts with streak_lvl 0")
    print("  ✓ Same day pages maintain streak level")
    print("  ✓ Consecutive days increment streak level")
    print("  ✓ Gaps in days reset streak to 0")
    print("  ✓ Different months/years reset streak")
    print("  ✓ Long streaks work correctly")
    print("  ✓ Multiple pages per day handled properly")
    print("  ✓ Midnight boundaries work correctly")
    print("  ✓ First page keeps custom streak levels, subsequent calculated")
    print("  ✓ Date conversion methods work correctly")


if __name__ == "__main__":
    run_all_streak_tests()
