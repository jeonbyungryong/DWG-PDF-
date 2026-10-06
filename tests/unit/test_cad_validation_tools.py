import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).parents[2]

def tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.mark.parametrize('name', ['benchmark_conversion', 'smoke_frozen_bundle'])
@pytest.mark.parametrize('provider,compatible', [('autocad', True), ('gstarcad', False)])
def test_follow_up_pdf_validation_uses_actual_provider(monkeypatch, name, provider, compatible, tmp_path):
    import dwg_to_pdf.pdf_validator as validator
    calls = []
    sentinel = object()
    monkeypatch.setattr(validator, 'validate_pdf', lambda path, **kwargs: calls.append((path, kwargs)) or sentinel)
    path = tmp_path / 'drawing.pdf'
    assert tool(name).validate_output(path, provider) is sentinel
    assert len(calls) == 1 and calls[0][0] == path
    # Omitting the False default also supports pre-AutoCAD baseline revisions.
    assert calls[0][1].get('allow_duplicate_page_mode', False) is compatible

def test_diagnostic_publisher_preserves_validator_and_success_cleanup(tmp_path):
    module = tool('benchmark_conversion')
    temporary = tmp_path / 'temp.pdf';temporary.write_bytes(b'pdf')
    final = tmp_path / 'drawing.pdf';calls=[];validator=object();sentinel=object()
    def original(source, target, **kwargs):
        calls.append((source, target, kwargs))
        return sentinel
    wrapped = module.make_diagnostic_publisher(original, tmp_path / 'run.json')
    assert wrapped(temporary, final, validator=validator) is sentinel
    assert calls == [(temporary, final, {'validator':validator})]
    assert not (tmp_path / 'run-rejected' / 'drawing.pdf').exists()

def test_diagnostic_publisher_retains_rejected_bytes_and_original_error(tmp_path):
    module = tool('benchmark_conversion')
    temporary = tmp_path / 'temp.pdf';temporary.write_bytes(b'bad pdf')
    failure = RuntimeError('reject')
    def original(*args, **kwargs):raise failure
    wrapped = module.make_diagnostic_publisher(original, tmp_path / 'run.json')
    with pytest.raises(RuntimeError) as caught:wrapped(temporary, tmp_path / 'drawing.pdf')
    assert caught.value is failure
    assert (tmp_path / 'run-rejected' / 'drawing.pdf').read_bytes() == b'bad pdf'

@pytest.mark.parametrize('name', ['benchmark_conversion', 'smoke_frozen_bundle'])
def test_actual_autocad_driver_pdf_is_compatible_only_for_autocad(name):
    from dwg_to_pdf.errors import AppError
    path = ROOT / 'validation' / 'autocad-2021-pc-b' / 'pdfs' / 'off' / 'TEMPLETE_1대1.pdf'
    assert tool(name).validate_output(path, 'autocad').page_count == 1
    with pytest.raises(AppError):tool(name).validate_output(path, 'gstarcad')
