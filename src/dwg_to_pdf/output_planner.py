from pathlib import Path


def output_names(source: Path, frame_count: int) -> tuple[str, ...]:
    """Create scale-free PDF names for the frames of one source drawing."""

    if isinstance(frame_count, bool) or not isinstance(frame_count, int):
        raise ValueError("frame_count must be an integer")
    if frame_count < 1:
        return ()
    stem = Path(source).stem
    return tuple(f"{stem}.pdf" if index == 1 else f"{stem}_{index}.pdf" for index in range(1, frame_count + 1))
