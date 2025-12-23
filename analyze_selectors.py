#!/usr/bin/env python3
"""
Analyze Agoda HTML to test and validate selectors.

This script helps debug selector issues by:
1. Testing selectors against saved HTML files
2. Showing what elements are found
3. Comparing different selector strategies
"""

import re
import sys
import argparse
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Any


def test_selector(soup: BeautifulSoup, tag: str, attrs: Dict[str, Any]) -> int:
    """Test a selector and return count of matches."""
    elements = soup.find_all(tag, attrs=attrs)
    return len(elements)


def analyze_room_containers(html_content: str) -> None:
    """Analyze potential room container elements."""
    soup = BeautifulSoup(html_content, 'lxml')
    
    print("\n" + "="*80)
    print("ROOM CONTAINER ANALYSIS")
    print("="*80)
    
    # Test each selector from the code
    selectors = [
        {'tag': 'div', 'attrs': {'data-selenium': 'room-panel'}, 'name': 'data-selenium=room-panel'},
        {'tag': 'div', 'attrs': {'data-element-name': 'room-item'}, 'name': 'data-element-name=room-item'},
        {'tag': 'div', 'attrs': {'data-selenium': 'room-item'}, 'name': 'data-selenium=room-item'},
        {'tag': 'div', 'attrs': {'class': re.compile(r'MasterRoom', re.I)}, 'name': 'class*=MasterRoom'},
        {'tag': 'div', 'attrs': {'class': re.compile(r'RoomGrid', re.I)}, 'name': 'class*=RoomGrid'},
        {'tag': 'div', 'attrs': {'data-ppapi': re.compile(r'room', re.I)}, 'name': 'data-ppapi*=room'},
        {'tag': 'div', 'attrs': {'class': re.compile(r'ChildRoomsList', re.I)}, 'name': 'class*=ChildRoomsList'},
        {'tag': 'div', 'attrs': {'class': re.compile(r'RoomGridItem', re.I)}, 'name': 'class*=RoomGridItem'},
        {'tag': 'div', 'attrs': {'class': re.compile(r'room-card', re.I)}, 'name': 'class*=room-card'},
        {'tag': 'div', 'attrs': {'data-testid': re.compile(r'room', re.I)}, 'name': 'data-testid*=room'},
    ]
    
    for selector in selectors:
        count = test_selector(soup, selector['tag'], selector['attrs'])
        status = "✓" if count > 0 else "✗"
        print(f"{status} {selector['name']:<35} → {count:3d} elements found")
    
    # Look for any data-selenium attributes
    print("\n--- All data-selenium attributes in document ---")
    data_selenium_elements = soup.find_all(attrs={'data-selenium': True})
    selenium_attrs = set()
    for elem in data_selenium_elements:
        attr_val = elem.get('data-selenium', '')
        if 'room' in attr_val.lower():
            selenium_attrs.add(attr_val)
    
    for attr in sorted(selenium_attrs):
        count = len(soup.find_all(attrs={'data-selenium': attr}))
        print(f"  data-selenium=\"{attr}\" → {count} elements")


def analyze_room_names(html_content: str) -> None:
    """Analyze room name/type extraction."""
    soup = BeautifulSoup(html_content, 'lxml')
    
    print("\n" + "="*80)
    print("ROOM NAME ANALYSIS")
    print("="*80)
    
    selectors = [
        {'tag': 'span', 'attrs': {'data-selenium': 'room-name'}, 'name': 'span[data-selenium=room-name]'},
        {'tag': 'h3', 'attrs': {'data-selenium': 'room-name'}, 'name': 'h3[data-selenium=room-name]'},
        {'tag': 'span', 'attrs': {'data-element-name': 'room-type-name'}, 'name': 'span[data-element-name=room-type-name]'},
        {'tag': 'a', 'attrs': {'class': re.compile(r'room.*name', re.I)}, 'name': 'a[class*=room-name]'},
        {'tag': 'span', 'attrs': {'class': re.compile(r'room.*title', re.I)}, 'name': 'span[class*=room-title]'},
        {'tag': 'div', 'attrs': {'data-selenium': re.compile(r'room.*name', re.I)}, 'name': 'div[data-selenium*=room-name]'},
    ]
    
    for selector in selectors:
        count = test_selector(soup, selector['tag'], selector['attrs'])
        status = "✓" if count > 0 else "✗"
        print(f"{status} {selector['name']:<45} → {count:3d} elements")
        
        # Show first 3 examples
        if count > 0:
            elements = soup.find_all(selector['tag'], attrs=selector['attrs'], limit=3)
            for i, elem in enumerate(elements, 1):
                text = elem.get_text(strip=True)[:60]
                print(f"    Example {i}: \"{text}\"")
    
    # Try to find room names by pattern matching
    print("\n--- Room names found by regex pattern ---")
    text = soup.get_text(' ', strip=True)
    room_pattern = r'\b((?:Deluxe|Standard|Superior|Premium|Classic|Executive|Family|Luxury|Triple|Quad|Single|Double|Twin|Suite|Studio|Villa)[\s\w\-]*(?:Room|Suite|Bed)?)\b'
    matches = re.findall(room_pattern, text, re.I)
    unique_matches = list(set(matches))[:10]
    for match in unique_matches:
        print(f"  - {match}")


def analyze_prices(html_content: str) -> None:
    """Analyze price extraction."""
    soup = BeautifulSoup(html_content, 'lxml')
    
    print("\n" + "="*80)
    print("PRICE ANALYSIS")
    print("="*80)
    
    selectors = [
        {'tag': 'strong', 'attrs': {'data-ppapi': 'room-price'}, 'name': 'strong[data-ppapi=room-price]'},
        {'tag': 'span', 'attrs': {'data-ppapi': 'room-price'}, 'name': 'span[data-ppapi=room-price]'},
        {'tag': 'span', 'attrs': {'data-selenium': 'display-price'}, 'name': 'span[data-selenium=display-price]'},
        {'tag': 'span', 'attrs': {'class': re.compile(r'price.*amount', re.I)}, 'name': 'span[class*=price-amount]'},
        {'tag': 'div', 'attrs': {'data-element-name': 'final-price'}, 'name': 'div[data-element-name=final-price]'},
    ]
    
    for selector in selectors:
        count = test_selector(soup, selector['tag'], selector['attrs'])
        status = "✓" if count > 0 else "✗"
        print(f"{status} {selector['name']:<45} → {count:3d} elements")
        
        # Show first 3 examples
        if count > 0:
            elements = soup.find_all(selector['tag'], attrs=selector['attrs'], limit=3)
            for i, elem in enumerate(elements, 1):
                text = elem.get_text(strip=True)
                print(f"    Example {i}: \"{text}\"")
    
    # Try to find prices by pattern matching
    print("\n--- Prices found by regex pattern ---")
    text = soup.get_text(' ', strip=True)
    
    price_patterns = [
        (r'R\s*\.?\s*([\d,]+)', 'R . X,XXX format'),
        (r'₹\s*([\d,]+)', '₹X,XXX format'),
        (r'Rs\.?\s*([\d,]+)', 'Rs. X,XXX format'),
        (r'INR\s*([\d,]+)', 'INR XXXX format'),
    ]
    
    for pattern, name in price_patterns:
        matches = re.findall(pattern, text)
        if matches:
            print(f"\n  {name}:")
            for price in matches[:5]:
                print(f"    {price}")


def analyze_html_file(filepath: Path) -> None:
    """Analyze a single HTML file."""
    print(f"\nAnalyzing: {filepath}")
    print(f"File size: {filepath.stat().st_size / 1024:.1f} KB")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        analyze_room_containers(html_content)
        analyze_room_names(html_content)
        analyze_prices(html_content)
        
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print("Review the results above to identify:")
        print("  1. Which selectors are finding elements (✓)")
        print("  2. Which selectors are not working (✗)")
        print("  3. What the actual content looks like (examples)")
        print("  4. Whether room names and prices are being extracted correctly")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"Error analyzing file: {e}")


def find_debug_html_files() -> List[Path]:
    """Find all debug HTML files in the output directory."""
    output_dir = Path("output/debug_html")
    if not output_dir.exists():
        return []
    
    html_files = list(output_dir.rglob("*.html"))
    return html_files


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Agoda HTML to test and validate selectors"
    )
    parser.add_argument(
        'html_file',
        nargs='?',
        type=Path,
        help='Path to HTML file to analyze (optional - will search for debug files if not provided)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available debug HTML files'
    )
    
    args = parser.parse_args()
    
    if args.list:
        html_files = find_debug_html_files()
        if not html_files:
            print("No debug HTML files found in output/debug_html/")
            print("\nTo generate debug HTML files, run the scraper which saves")
            print("HTML to output/debug_html/{session_id}/ for each hotel.")
            return
        
        print(f"\nFound {len(html_files)} debug HTML files:\n")
        for i, filepath in enumerate(html_files, 1):
            print(f"  {i}. {filepath}")
        print(f"\nTo analyze a file, run:")
        print(f"  python analyze_selectors.py <path_to_file>")
        return
    
    if args.html_file:
        if not args.html_file.exists():
            print(f"Error: File not found: {args.html_file}")
            sys.exit(1)
        analyze_html_file(args.html_file)
    else:
        # Try to find and analyze most recent debug file
        html_files = find_debug_html_files()
        if not html_files:
            print("No HTML file specified and no debug files found.")
            print("\nUsage:")
            print("  python analyze_selectors.py <path_to_html_file>")
            print("  python analyze_selectors.py --list")
            print("\nOr save an Agoda hotel page as HTML and analyze it:")
            print("  1. Open Agoda hotel page in browser")
            print("  2. Right-click → Save As → 'Complete Webpage'")
            print("  3. python analyze_selectors.py saved_page.html")
            sys.exit(1)
        
        # Analyze the most recent file
        most_recent = max(html_files, key=lambda p: p.stat().st_mtime)
        print(f"No file specified. Analyzing most recent debug HTML file:")
        analyze_html_file(most_recent)


if __name__ == '__main__':
    main()
