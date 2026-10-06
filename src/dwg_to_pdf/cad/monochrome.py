"""Apply monochrome intent to True Color on the authorized working copy."""
from ..errors import AppError


def prepare_monochrome(raw, *, max_blocks=64, max_entities=5000) -> None:
    targets = []
    inspected = 0
    def count(collection, maximum):
        value = collection.Count
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError("monochrome traversal limit exceeded")
        return value
    def visit(obj):
        nonlocal inspected
        inspected += 1
        if inspected > max_entities:
            raise ValueError("monochrome aggregate traversal limit exceeded")
        color = obj.TrueColor
        method = color.ColorMethod
        if type(method) is not int or method not in (192, 193, 194, 195, 196, 197, 200):
            raise ValueError("unknown color method")
        if method == 194:  # acColorMethodByRGB
            rgb = (color.Red, color.Green, color.Blue)
            if any(type(channel) is not int or not 0 <= channel <= 255 for channel in rgb):
                raise ValueError("invalid true color")
            # White masks remain white. Other RGB colors use approved CTB
            # index 7; geometry and lineweight are not written.
            if rgb != (255, 255, 255):
                targets.append(obj)
        if bool(getattr(obj, "HasAttributes", False)):
            for attribute in obj.GetAttributes():
                visit(attribute)
            for attribute in obj.GetConstantAttributes():
                visit(attribute)
    def inspect(collection):
        size = count(collection, max_entities)
        if inspected + size > max_entities:
            raise ValueError("monochrome aggregate traversal limit exceeded")
        for index in range(size):
            visit(collection.Item(index))
    try:
        inspect(raw.Layers)
        blocks = raw.Blocks
        for index in range(count(blocks, max_blocks)):
            block = blocks.Item(index)
            # Unknown status is not proof that this is an internal definition.
            if block.IsXRef:
                raise ValueError("external block is not an owned working-copy definition")
            inspect(block)
        # Read and bound all definitions before the first working-copy mutation.
        for obj in targets:
            obj.Color = 7
    except Exception as error:
        raise AppError("E410", "CAD working-copy monochrome preparation failed") from error
