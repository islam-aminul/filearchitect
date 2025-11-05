"""
Sidecar file detection and handling for FileArchitect.

Sidecar files are metadata files that accompany media files (e.g., .xmp, .aae, .thm).
"""

from pathlib import Path
from typing import List, Optional, Set

from ..core.constants import SIDECAR_EXTENSIONS


def is_sidecar_file(file_path: Path) -> bool:
    """
    Check if file is a sidecar file based on extension.

    Args:
        file_path: Path to file

    Returns:
        True if file is a sidecar, False otherwise

    Examples:
        >>> is_sidecar_file(Path("photo.jpg.xmp"))
        True
        >>> is_sidecar_file(Path("photo.jpg"))
        False
    """
    extension = file_path.suffix.lower()
    return extension in SIDECAR_EXTENSIONS


def get_base_name(file_path: Path) -> str:
    """
    Get base name of file without any extensions.

    Handles files with multiple extensions like "photo.jpg.xmp".

    Args:
        file_path: Path to file

    Returns:
        Base name without extensions

    Examples:
        >>> get_base_name(Path("photo.jpg.xmp"))
        'photo'
        >>> get_base_name(Path("photo.jpg"))
        'photo'
    """
    name = file_path.name

    # Remove all known extensions
    while True:
        if '.' not in name:
            break

        # Check if last part is an extension
        parts = name.rsplit('.', 1)
        if len(parts) == 2 and parts[1]:
            # Check if it's a known extension or sidecar
            ext = '.' + parts[1].lower()
            name = parts[0]
        else:
            break

    return name


def find_sidecar_files(file_path: Path) -> List[Path]:
    """
    Find all sidecar files for a given file.

    Looks for files with same base name but sidecar extensions.

    Args:
        file_path: Path to main file

    Returns:
        List of sidecar file paths

    Examples:
        >>> sidecars = find_sidecar_files(Path("/photos/photo.jpg"))
        >>> # Returns [Path("/photos/photo.jpg.xmp"), Path("/photos/photo.aae")]
    """
    if not file_path.exists():
        return []

    parent = file_path.parent
    base_name = get_base_name(file_path)
    sidecars = []

    # Look for files with same base name
    try:
        for candidate in parent.glob(f"{base_name}*"):
            if candidate == file_path:
                continue

            if is_sidecar_file(candidate):
                # Verify it's associated with this file
                candidate_base = get_base_name(candidate)
                if candidate_base == base_name or candidate.stem == file_path.name:
                    sidecars.append(candidate)

    except (OSError, PermissionError):
        pass

    return sidecars


def get_main_file_for_sidecar(sidecar_path: Path) -> Optional[Path]:
    """
    Find main file associated with a sidecar file.

    Args:
        sidecar_path: Path to sidecar file

    Returns:
        Path to main file if found, None otherwise

    Examples:
        >>> main = get_main_file_for_sidecar(Path("/photos/photo.jpg.xmp"))
        >>> # Returns Path("/photos/photo.jpg")
    """
    if not is_sidecar_file(sidecar_path):
        return None

    if not sidecar_path.exists():
        return None

    parent = sidecar_path.parent

    # Try removing sidecar extension
    # e.g., "photo.jpg.xmp" -> "photo.jpg"
    stem = sidecar_path.stem
    potential_main = parent / stem

    if potential_main.exists() and potential_main.is_file():
        return potential_main

    # Try with base name
    # e.g., "photo.xmp" -> "photo.*"
    base_name = get_base_name(sidecar_path)

    try:
        for candidate in parent.glob(f"{base_name}.*"):
            if candidate == sidecar_path:
                continue

            if not is_sidecar_file(candidate):
                return candidate

    except (OSError, PermissionError):
        pass

    return None


def pair_files_with_sidecars(file_paths: List[Path]) -> dict[Path, List[Path]]:
    """
    Pair main files with their sidecar files.

    Args:
        file_paths: List of file paths to process

    Returns:
        Dictionary mapping main file path to list of sidecar paths

    Examples:
        >>> files = [Path("photo.jpg"), Path("photo.jpg.xmp"), Path("video.mp4")]
        >>> pairs = pair_files_with_sidecars(files)
        >>> # Returns {Path("photo.jpg"): [Path("photo.jpg.xmp")], Path("video.mp4"): []}
    """
    # Separate main files and sidecars
    main_files = []
    sidecar_files = []

    for path in file_paths:
        if is_sidecar_file(path):
            sidecar_files.append(path)
        else:
            main_files.append(path)

    # Build pairing dictionary
    pairs: dict[Path, List[Path]] = {}

    for main_file in main_files:
        pairs[main_file] = []

        base_name = get_base_name(main_file)
        parent = main_file.parent

        # Find matching sidecars
        for sidecar in sidecar_files:
            if sidecar.parent != parent:
                continue

            # Check if sidecar belongs to this main file
            if sidecar.stem == main_file.name:
                # Direct match: photo.jpg -> photo.jpg.xmp
                pairs[main_file].append(sidecar)
            elif get_base_name(sidecar) == base_name:
                # Base name match: photo.jpg -> photo.xmp
                pairs[main_file].append(sidecar)

    return pairs


def group_files_with_sidecars(file_paths: List[Path]) -> List[tuple[Path, List[Path]]]:
    """
    Group files with their sidecars into tuples.

    Args:
        file_paths: List of file paths

    Returns:
        List of (main_file, [sidecars]) tuples

    Examples:
        >>> files = [Path("photo.jpg"), Path("photo.jpg.xmp")]
        >>> groups = group_files_with_sidecars(files)
        >>> # Returns [(Path("photo.jpg"), [Path("photo.jpg.xmp")])]
    """
    pairs = pair_files_with_sidecars(file_paths)
    return [(main, sidecars) for main, sidecars in pairs.items()]


def filter_sidecar_files(file_paths: List[Path]) -> tuple[List[Path], List[Path]]:
    """
    Separate sidecar files from main files.

    Args:
        file_paths: List of file paths

    Returns:
        Tuple of (main_files, sidecar_files)

    Examples:
        >>> files = [Path("photo.jpg"), Path("photo.jpg.xmp"), Path("video.mp4")]
        >>> mains, sidecars = filter_sidecar_files(files)
        >>> # mains = [Path("photo.jpg"), Path("video.mp4")]
        >>> # sidecars = [Path("photo.jpg.xmp")]
    """
    main_files = []
    sidecar_files = []

    for path in file_paths:
        if is_sidecar_file(path):
            sidecar_files.append(path)
        else:
            main_files.append(path)

    return main_files, sidecar_files


def get_sidecar_types(file_path: Path) -> Set[str]:
    """
    Get types of sidecar files for a given file.

    Args:
        file_path: Path to main file

    Returns:
        Set of sidecar file extensions (e.g., {'.xmp', '.aae'})

    Examples:
        >>> types = get_sidecar_types(Path("/photos/photo.jpg"))
        >>> # Returns {'.xmp', '.aae'}
    """
    sidecars = find_sidecar_files(file_path)
    return {sc.suffix.lower() for sc in sidecars}


def has_sidecar_files(file_path: Path) -> bool:
    """
    Check if file has any sidecar files.

    Args:
        file_path: Path to main file

    Returns:
        True if sidecar files exist, False otherwise

    Examples:
        >>> has_sidecar_files(Path("/photos/photo.jpg"))
        True
    """
    return len(find_sidecar_files(file_path)) > 0


def copy_sidecar_files(source_main: Path, dest_main: Path) -> List[Path]:
    """
    Copy sidecar files from source to destination.

    Creates sidecar files at destination with same relative names.

    Args:
        source_main: Source main file path
        dest_main: Destination main file path

    Returns:
        List of created sidecar file paths at destination

    Examples:
        >>> copied = copy_sidecar_files(
        ...     Path("/source/photo.jpg"),
        ...     Path("/dest/photo.jpg")
        ... )
        >>> # Copies /source/photo.jpg.xmp to /dest/photo.jpg.xmp
    """
    import shutil

    sidecars = find_sidecar_files(source_main)
    copied_paths = []

    for sidecar in sidecars:
        # Determine destination path
        if sidecar.stem == source_main.name:
            # Direct association: photo.jpg -> photo.jpg.xmp
            dest_sidecar = dest_main.parent / f"{dest_main.name}{sidecar.suffix}"
        else:
            # Base name association: photo.jpg -> photo.xmp
            dest_sidecar = dest_main.parent / f"{dest_main.stem}{sidecar.suffix}"

        try:
            # Ensure parent directory exists
            dest_sidecar.parent.mkdir(parents=True, exist_ok=True)

            # Copy sidecar file
            shutil.copy2(sidecar, dest_sidecar)
            copied_paths.append(dest_sidecar)

        except (OSError, PermissionError):
            # Skip sidecars we can't copy
            continue

    return copied_paths
