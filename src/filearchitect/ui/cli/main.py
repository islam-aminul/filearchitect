"""
Main CLI application for FileArchitect.

Command-line interface for file organization and processing.
"""

import sys
import time
from pathlib import Path
from typing import Optional
import click

from filearchitect.core import (
    ProcessingOrchestrator,
    SessionManager,
    SpaceManager,
    setup_logging
)
from filearchitect.config.manager import load_config_from_file, get_config_directory
from filearchitect.database.manager import DatabaseManager
from filearchitect.ui.cli.display import ProgressDisplay


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.pass_context
def cli(ctx, verbose, config):
    """
    FileArchitect - Intelligent file organization and processing.

    A powerful tool for organizing photos, videos, audio, and documents
    with automatic categorization, metadata extraction, and deduplication.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Setup logging
    log_level = 'DEBUG' if verbose else 'INFO'
    setup_logging(level=log_level, log_file=Path('filearchitect.log'))

    # Load configuration
    if config:
        ctx.obj['config'] = load_config_from_file(Path(config))
    else:
        # Try to load default config
        config_dir = get_config_directory()
        default_config = config_dir / 'config.yaml'
        if default_config.exists():
            ctx.obj['config'] = load_config_from_file(default_config)
        else:
            # Use default config
            from filearchitect.config.models import Config
            ctx.obj['config'] = Config()

    ctx.obj['verbose'] = verbose


@cli.command()
@click.argument('source', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.argument('destination', type=click.Path(file_okay=False, dir_okay=True))
@click.option('--dry-run', is_flag=True, help='Simulate without making changes')
@click.option('--workers', '-w', type=int, help='Number of worker threads')
@click.pass_context
def start(ctx, source, destination, dry_run, workers):
    """
    Start processing files from SOURCE to DESTINATION.

    SOURCE: Source directory containing files to organize
    DESTINATION: Destination directory for organized files

    Example:
        filearchitect start /path/to/photos /path/to/organized
    """
    config = ctx.obj['config']
    source_path = Path(source).resolve()
    dest_path = Path(destination).resolve()

    click.echo(f"FileArchitect - Starting file processing")
    click.echo(f"Source: {source_path}")
    click.echo(f"Destination: {dest_path}")

    if dry_run:
        click.echo("DRY RUN MODE - No files will be modified")
        return

    try:
        # Initialize components
        db_manager = DatabaseManager.get_instance()
        session_manager = SessionManager(dest_path, db_manager)
        space_manager = SpaceManager()

        # Create session
        session_id = session_manager.create_session(source_path, dest_path)
        click.echo(f"Created session {session_id}")

        # Check space
        click.echo("\nChecking disk space...")
        space_info = space_manager.get_space_info(dest_path)
        click.echo(f"Available space: {space_info.free_gb:.2f} GB")

        if space_info.free_gb < space_manager.min_free_gb:
            click.secho(
                f"Warning: Low disk space ({space_info.free_gb:.2f} GB). "
                f"Minimum {space_manager.min_free_gb:.2f} GB required.",
                fg='yellow'
            )
            if not click.confirm("Continue anyway?"):
                click.echo("Cancelled.")
                return

        # Create orchestrator
        display = ProgressDisplay(verbose=ctx.obj['verbose'])
        orchestrator = ProcessingOrchestrator(
            config=config,
            source_path=source_path,
            destination_path=dest_path,
            session_id=session_id,
            num_workers=workers,
            progress_callback=display.update,
            session_manager=session_manager
        )

        # Start processing
        click.echo("\nStarting file processing...")
        click.echo("Press Ctrl+C to pause\n")

        try:
            orchestrator.start()

            # Processing completed
            click.echo("\n")
            click.secho("✓ Processing completed successfully!", fg='green')

            # Show statistics
            progress = orchestrator.get_progress()
            click.echo(f"\nStatistics:")
            click.echo(f"  Files processed: {progress.files_processed}")
            click.echo(f"  Files skipped: {progress.files_skipped}")
            click.echo(f"  Duplicates: {progress.files_duplicates}")
            click.echo(f"  Errors: {progress.files_error}")
            click.echo(f"  Data processed: {progress.bytes_processed / (1024**3):.2f} GB")

            if progress.category_counts:
                click.echo(f"\nCategories:")
                for category, count in sorted(progress.category_counts.items()):
                    click.echo(f"  {category}: {count}")

        except KeyboardInterrupt:
            click.echo("\n\nInterrupted by user. Stopping gracefully...")
            orchestrator.stop()
            click.secho("✓ Stopped. Use 'filearchitect resume' to continue.", fg='yellow')

    except Exception as e:
        click.secho(f"✗ Error: {e}", fg='red')
        if ctx.obj['verbose']:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument('destination', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--workers', '-w', type=int, help='Number of worker threads')
@click.pass_context
def resume(ctx, destination, workers):
    """
    Resume incomplete processing session.

    DESTINATION: Destination directory of previous session

    Example:
        filearchitect resume /path/to/organized
    """
    config = ctx.obj['config']
    dest_path = Path(destination).resolve()

    try:
        # Initialize components
        db_manager = DatabaseManager.get_instance()
        session_manager = SessionManager(dest_path, db_manager)

        # Find incomplete session
        session_info = session_manager.find_incomplete_session()

        if not session_info:
            click.secho("No incomplete session found.", fg='yellow')
            return

        session_id = session_info['session_id']
        source_path = Path(session_info['source_path'])

        click.echo(f"Found incomplete session {session_id}")
        click.echo(f"Source: {source_path}")
        click.echo(f"Destination: {dest_path}")

        # Validate session can be resumed
        if not session_manager.can_resume_session(session_id):
            click.secho("Cannot resume session (paths no longer accessible).", fg='red')
            return

        # Load progress
        snapshot = session_manager.load_progress()
        if snapshot:
            click.echo(f"\nPrevious progress:")
            click.echo(f"  Files processed: {snapshot.files_processed}")
            click.echo(f"  Files remaining: {snapshot.files_pending}")

        if not click.confirm("\nResume this session?"):
            click.echo("Cancelled.")
            return

        # Create orchestrator
        display = ProgressDisplay(verbose=ctx.obj['verbose'])
        orchestrator = ProcessingOrchestrator(
            config=config,
            source_path=source_path,
            destination_path=dest_path,
            session_id=session_id,
            num_workers=workers,
            progress_callback=display.update,
            session_manager=session_manager
        )

        # Resume processing
        click.echo("\nResuming processing...")
        click.echo("Press Ctrl+C to pause\n")

        try:
            orchestrator.start()
            click.echo("\n")
            click.secho("✓ Processing completed successfully!", fg='green')

        except KeyboardInterrupt:
            click.echo("\n\nInterrupted by user. Stopping gracefully...")
            orchestrator.stop()
            click.secho("✓ Stopped. Use 'filearchitect resume' to continue.", fg='yellow')

    except Exception as e:
        click.secho(f"✗ Error: {e}", fg='red')
        if ctx.obj['verbose']:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument('destination', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.pass_context
def status(ctx, destination):
    """
    Show status of processing session.

    DESTINATION: Destination directory

    Example:
        filearchitect status /path/to/organized
    """
    dest_path = Path(destination).resolve()

    try:
        # Initialize components
        db_manager = DatabaseManager.get_instance()
        session_manager = SessionManager(dest_path, db_manager)

        # Find incomplete session
        session_info = session_manager.find_incomplete_session()

        if not session_info:
            click.echo("No active session found.")

            # Try to load progress snapshot
            snapshot = session_manager.load_progress()
            if snapshot:
                click.echo("\nLast known progress:")
                click.echo(f"  Session: {snapshot.session_id}")
                click.echo(f"  Status: {snapshot.status}")
                click.echo(f"  Files processed: {snapshot.files_processed}")
                click.echo(f"  Files pending: {snapshot.files_pending}")
            return

        # Show session info
        session_id = session_info['session_id']
        click.echo(f"Active Session: {session_id}")
        click.echo(f"Status: {session_info['status']}")
        click.echo(f"Source: {session_info['source_path']}")
        click.echo(f"Destination: {session_info['destination_path']}")
        click.echo(f"Started: {session_info['started_at']}")

        # Get statistics
        stats = session_manager.get_session_statistics(session_id)
        click.echo(f"\nStatistics:")
        click.echo(f"  Total files: {stats.get('total_files', 0)}")
        click.echo(f"  Completed: {stats.get('completed', 0)}")
        click.echo(f"  Skipped: {stats.get('skipped', 0)}")
        click.echo(f"  Duplicates: {stats.get('duplicates', 0)}")
        click.echo(f"  Errors: {stats.get('errors', 0)}")

        # Load progress snapshot
        snapshot = session_manager.load_progress()
        if snapshot:
            click.echo(f"\nProgress:")
            click.echo(f"  Scanned: {snapshot.files_scanned}")
            click.echo(f"  Processed: {snapshot.files_processed}")
            click.echo(f"  Pending: {snapshot.files_pending}")
            click.echo(f"  Speed: {snapshot.processing_speed:.2f} files/sec")
            if snapshot.eta_seconds:
                eta_min = snapshot.eta_seconds // 60
                click.echo(f"  ETA: {eta_min} minutes")

    except Exception as e:
        click.secho(f"✗ Error: {e}", fg='red')
        sys.exit(1)


@cli.command()
@click.argument('destination', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--session-id', type=int, help='Specific session ID to undo')
@click.option('--dry-run', is_flag=True, help='Preview without actually deleting')
@click.pass_context
def undo(ctx, destination, session_id, dry_run):
    """
    Undo a completed session by removing organized files.

    DESTINATION: Destination directory

    Example:
        filearchitect undo /path/to/organized --dry-run
    """
    dest_path = Path(destination).resolve()

    try:
        # Initialize components
        db_manager = DatabaseManager.get_instance()
        session_manager = SessionManager(dest_path, db_manager)

        if not session_id:
            # Find last completed session
            # For now, ask user for session ID
            click.echo("Please specify --session-id")
            click.echo("\nUse 'filearchitect status' to see available sessions")
            return

        click.echo(f"Undoing session {session_id}")

        if dry_run:
            click.echo("DRY RUN MODE - No files will be deleted\n")
        else:
            click.secho("WARNING: This will delete all files organized by this session!", fg='red')
            if not click.confirm("Are you sure?"):
                click.echo("Cancelled.")
                return

        # Perform undo
        click.echo("\nUndoing session...")
        results = session_manager.undo_session(session_id, dry_run=dry_run)

        # Show results
        click.echo(f"\nResults:")
        click.echo(f"  Files deleted: {results['files_deleted']}")
        click.echo(f"  Files failed: {results['files_failed']}")
        click.echo(f"  Directories removed: {results['dirs_deleted']}")

        if results['errors']:
            click.secho(f"\nErrors:", fg='yellow')
            for error in results['errors'][:10]:  # Show first 10 errors
                click.echo(f"  {error}")
            if len(results['errors']) > 10:
                click.echo(f"  ... and {len(results['errors']) - 10} more errors")

        if dry_run:
            click.secho("\n✓ Dry run complete. No files were modified.", fg='green')
        else:
            click.secho("\n✓ Undo complete.", fg='green')

    except Exception as e:
        click.secho(f"✗ Error: {e}", fg='red')
        if ctx.obj['verbose']:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
def version():
    """Show version information."""
    from filearchitect import __version__
    click.echo(f"FileArchitect version {__version__}")


def main():
    """Entry point for CLI application."""
    cli(obj={})


if __name__ == '__main__':
    main()
