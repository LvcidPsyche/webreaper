#!/usr/bin/env python3
"""
WebReaper Master Control Script
===============================
Main entry point for the WebReaper scraper system.
"""

import sys
import argparse
from pathlib import Path

# Add webreaper to path
sys.path.insert(0, str(Path(__file__).parent))

from webreaper.cli import cli
from webreaper.dashboard import launch_dashboard


def main():
    """Main entry point with subcommands."""
    parser = argparse.ArgumentParser(
        description="WebReaper - Ultimate Web Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  webreaper crawl https://example.com                    # Basic crawl
  webreaper crawl https://example.com --stealth --tor    # Stealth mode
  webreaper security https://example.com                 # Security scan
  webreaper blogwatcher https://blog.example.com         # Generate RSS feed
  webreaper dashboard                                     # Launch UI
  webreaper genres                                       # Show genres
  webreaper init                                         # Create config

For more help: webreaper <command> --help
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Dashboard command
    dashboard_parser = subparsers.add_parser(
        'dashboard',
        help='Launch interactive dashboard'
    )
    
    # Delegate other commands to CLI
    args, remaining = parser.parse_known_args()
    
    if args.command == 'dashboard':
        launch_dashboard()
    elif args.command is None:
        parser.print_help()
    else:
        # Pass to main CLI
        sys.argv = ['webreaper'] + sys.argv[1:]
        cli()


if __name__ == '__main__':
    main()
